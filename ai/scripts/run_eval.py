"""eval/ 요청 세트로 일정 생성·빈틈 채우기 지표를 잰다.

    cd ai && python scripts/run_eval.py

결과는 eval/results/<날짜>.json 에 남는다. API 키나 네트워크 없이 돈다.
"""

import datetime as dt
import json
import unicodedata
from collections import Counter
from pathlib import Path

from app.agent.gap import BUFFER_MINUTES, fill_gap
from app.agent.graph import run_planning
from app.sample import place_by_id
from app.schemas import tools as t
from app.schemas.itinerary import Stop
from app.tools.mock import MockToolbox

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT.parent / "eval"
RESULTS_DIR = EVAL_DIR / "results"


def load(name: str) -> list[dict]:
    return json.loads((EVAL_DIR / name).read_text())


def toolbox(rain: dict | None) -> MockToolbox:
    return MockToolbox(rain={side: set(hours) for side, hours in (rain or {}).items()})


def _rate(n: int, total: int) -> float | None:
    return round(n / total, 3) if total else None


def eval_trips(requests: list[dict]) -> dict:
    days = days_with_error = over_budget = budgeted = 0
    errors: Counter = Counter()
    warnings: Counter = Counter()
    per_request = []

    for raw in requests:
        req = t.TripRequest(**{k: v for k, v in raw.items() if k not in ("id", "rain")})
        out = run_planning(req, toolbox(raw.get("rain")))

        error_dates = {v.date for v in out.violations if v.severity == "error" and v.date}
        days += len(out.trip.days)
        days_with_error += sum(1 for d in out.trip.days if d.date in error_dates)
        for v in out.violations:
            (errors if v.severity == "error" else warnings)[v.type] += 1

        cost = sum(s.cost for d in out.trip.days for s in d.stops)
        if req.budget is not None:
            budgeted += 1
            over_budget += cost > req.budget

        per_request.append({
            "id": raw["id"],
            "days": len(out.trip.days),
            "stops": sum(len(d.stops) for d in out.trip.days),
            "cost": cost,
            "errors": sum(1 for v in out.violations if v.severity == "error"),
            "warnings": sum(1 for v in out.violations if v.severity == "warning"),
        })

    return {
        "requests": len(requests),
        "days": days,
        "days_with_error": days_with_error,
        "stops_per_day": round(sum(r["stops"] for r in per_request) / days, 2) if days else None,
        "violation_rate": _rate(days_with_error, days),
        "errors_by_type": dict(errors.most_common()),
        "warnings_by_type": dict(warnings.most_common()),
        "budget_requests": budgeted,
        "over_budget": over_budget,
        "per_request": per_request,
    }


def _gap_request(raw: dict) -> t.FillGapIn:
    now = dt.datetime.fromisoformat(raw["now"])
    until = now + dt.timedelta(minutes=raw["minutes"])
    next_stop = None
    if raw.get("next_place_id"):
        place = place_by_id(raw["next_place_id"])
        end = (until + dt.timedelta(hours=1)).time()
        next_stop = Stop(id=place.id, place=place, start=until.time(), end=end)
    return t.FillGapIn(location=t.LatLng(**raw["location"]), now=now, until=until,
                       next_stop=next_stop, preferences=raw.get("preferences", []))


def eval_gaps(cases: list[dict]) -> dict:
    suggestions = on_time = empty = 0
    per_case = []

    for raw in cases:
        tools = toolbox(raw.get("rain"))
        req = _gap_request(raw)
        out = fill_gap(req, tools)
        nxt = req.next_stop.place if req.next_stop else None

        fits = 0
        for s in out.suggestions:
            back = tools.travel_minutes(s.place, nxt) if nxt else 0
            fits += s.travel_minutes + s.stay_minutes + back + BUFFER_MINUTES <= raw["minutes"]
        suggestions += len(out.suggestions)
        on_time += fits
        empty += not out.suggestions
        per_case.append({"id": raw["id"], "suggestions": len(out.suggestions),
                         "on_time": fits, "place_ids": [s.place.id for s in out.suggestions]})

    return {
        "cases": len(cases),
        "suggestions": suggestions,
        "on_time": on_time,
        "on_time_rate": _rate(on_time, suggestions),
        "empty_cases": empty,
        "per_case": per_case,
    }


def run(requests: list[dict], gaps: list[dict]) -> dict:
    return {
        "date": dt.date.today().isoformat(),
        "trips": eval_trips(requests),
        "gaps": eval_gaps(gaps),
    }


def save(result: dict, out_dir: Path = RESULTS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result['date']}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return path


# 한글은 터미널에서 두 칸
def _width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def _counts(counter: dict) -> str:
    return ", ".join(f"{k} {v}" for k, v in counter.items()) or "-"


def report(result: dict) -> str:
    trips, gaps = result["trips"], result["gaps"]
    rows = [
        ("일정 요청", trips["requests"]),
        ("일수", trips["days"]),
        ("하루 평균 장소", trips["stops_per_day"]),
        ("오류 있는 날", trips["days_with_error"]),
        ("위반률", trips["violation_rate"]),
        ("오류 유형", _counts(trips["errors_by_type"])),
        ("경고 유형", _counts(trips["warnings_by_type"])),
        ("예산 초과", f"{trips['over_budget']} / {trips['budget_requests']}"),
        ("빈틈 케이스", gaps["cases"]),
        ("추천 수", gaps["suggestions"]),
        ("정시율", gaps["on_time_rate"]),
        ("추천 0건", gaps["empty_cases"]),
    ]
    width = max(_width(name) for name, _ in rows) + 2
    return "\n".join(name + " " * (width - _width(name)) + str(value) for name, value in rows)


def main():
    result = run(load("requests.json"), load("gap_requests.json"))
    print(report(result))
    path = save(result)
    print(f"\nwrote {path.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    main()
