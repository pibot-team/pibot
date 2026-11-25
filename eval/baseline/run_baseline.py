"""LLM 단독 베이스라인 (#15). 같은 요청 30건을 도구 없이 LLM 에게만 주고, 에이전트와 같은 검사기로 잰다.

    cd ai && python ../eval/baseline/run_baseline.py generate   # LLM 호출 (runs/raw 에 저장, 있으면 건너뜀)
    cd ai && python ../eval/baseline/run_baseline.py match      # 장소 이름 -> DB 매칭, runs/matches.csv
    cd ai && python ../eval/baseline/run_baseline.py score      # LLM 단독 vs 에이전트

- 장소는 LLM 이 자유롭게 고른다. 이름으로 DB 와 맞추고, 못 찾으면 확인 불가로 따로 센다
- 비 예보는 프롬프트에 같이 준다 (에이전트가 아는 것과 같은 정보)
- 에이전트도 샘플 30곳이 아니라 DB 장소로 돌린다
- 채점은 둘 다 같은 함수: 확인된 장소만 검사
- 이동시간: --travel kakao 면 카카오모빌리티 미래 길찾기 (같은 요일·시각, 주차 5분 더함), 아니면 가짜 도구
  에이전트는 일정을 짤 때도 같은 이동시간을 쓴다 (채점 때와 출발 시각·캐시가 같아서 값이 같다)
- 애매한 이름 매칭은 사람이 본 match_review.csv 를 따른다
"""

import argparse
import csv
import datetime as dt
import json
import math
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))

from pydantic import BaseModel

from app.agent.graph import _center, run_planning
from app.agent.validator import check_trip
from app.config import settings
from app.places import load_db_places
from app.schemas import tools as t
from app.schemas.itinerary import Day, Leg, Place, Stop, Trip
from app.tools.mock import MockToolbox

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
RAW = RUNS / "raw"
MODEL = "claude-sonnet-5-5"
REPEATS = 3

WEEKDAYS = "월화수목금토일"
PACE = {"relaxed": "여유롭게 (하루 3곳 정도)", "normal": "보통 (하루 4곳 정도)",
        "packed": "빡빡하게 (하루 5곳 이상)"}
SIDE = {"west": "제주 서쪽 (제주시 서부, 애월, 한림, 한경, 대정, 안덕)",
        "east": "제주 동쪽 (제주시 동부, 조천, 구좌, 성산, 표선, 남원)"}


# ---------------------------------------------------------------- 1. LLM 호출

class LLMStop(BaseModel):
    name: str
    start: str  # HH:MM
    end: str


class LLMDay(BaseModel):
    date: str  # YYYY-MM-DD
    stops: list[LLMStop]


class LLMTrip(BaseModel):
    days: list[LLMDay]


def prompt(req: dict) -> str:
    start, end = dt.date.fromisoformat(req["start_date"]), dt.date.fromisoformat(req["end_date"])
    dates = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    lines = [
        "제주도 렌터카 여행 일정을 짜줘.",
        f"- 날짜: {', '.join(f'{d.isoformat()}({WEEKDAYS[d.weekday()]})' for d in dates)}",
        f"- 일정 강도: {PACE[req['pace']]}",
        f"- 좋아하는 것: {', '.join(req['preferences']) or '없음'}",
        "- 이동: 렌터카, 9시 30분쯤 출발",
    ]
    if req.get("budget"):
        lines.append(f"- 입장료·이용료 예산: 1인 총 {req['budget']:,}원 (식비 제외)")
    for side, hours in (req.get("rain") or {}).items():
        lines.append(f"- 비 예보: 매일 {min(hours)}시~{max(hours) + 1}시 {SIDE[side]}")
    lines += [
        "",
        ("점심 식사도 일정에 넣어줘. 실제로 있는 장소의 정확한 이름을 쓰고, "
         "휴무일·영업시간·이동시간·날씨를 고려해서 방문 시각을 정해줘."),
    ]
    return "\n".join(lines)


def call(req: dict, k: int) -> None:
    path = RAW / MODEL / f"{req['id']}_{k}.json"
    if path.exists():
        return
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)
    res = client.messages.parse(
        model=MODEL, max_tokens=16000,
        messages=[{"role": "user", "content": prompt(req)}],
        output_format=LLMTrip,
    )
    if res.parsed_output is None:
        raise RuntimeError(f"{req['id']}_{k}: {res.stop_reason}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "prompt": prompt(req), "trip": res.parsed_output.model_dump(),
        "usage": {"input": res.usage.input_tokens, "output": res.usage.output_tokens},
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"  {req['id']}_{k}")


def generate(requests: list[dict], workers: int) -> None:
    jobs = [(r, k) for r in requests for k in range(REPEATS)]
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(lambda j: call(*j), jobs))
    usage = [json.loads(p.read_text())["usage"] for p in (RAW / MODEL).glob("*.json")]
    print(f"{len(usage)}개  입력 {sum(u['input'] for u in usage):,}  출력 {sum(u['output'] for u in usage):,} 토큰")


# ---------------------------------------------------------------- 2. 이름 매칭

def norm(name: str) -> str:
    # "점심 - 우진해장국", "한림칼국수 - 점심", "점심 식사: 명진전복" 같은 꼬리표를 뗀다
    name = re.sub(r"^\s*(점심|저녁|아침)[^-:]*[-:]\s*|\s*-\s*(점심|저녁)\s*$", "", name)
    name = re.sub(r"\(.*?\)|\[.*?\]", "", name)
    return re.sub(r"[\s·,.'\"&-]", "", name).lower()


def match_name(name: str, index: dict[str, list[Place]]) -> tuple[Place | None, str]:
    key = norm(name)
    if key in index:
        return index[key][0], "exact" if len(index[key]) == 1 else "exact_dup"
    # 한쪽이 다른 쪽을 품으면 길이 차이가 가장 작은 곳
    hits = [(abs(len(k) - len(key)), k) for k in index
            if len(k) >= 3 and len(key) >= 3 and (k in key or key in k)]
    if not hits:
        return None, "none"
    hits.sort()
    best = hits[0]
    method = "contains" if len(hits) == 1 or hits[1][0] > best[0] else "contains_dup"
    return index[best[1]][0], method


def match(places: tuple[Place, ...]) -> None:
    index: dict[str, list[Place]] = {}
    # 이름이 같은 곳이 여럿이면 영업시간 정보가 있는 곳을 앞에
    for p in sorted(places, key=lambda p: p.hours is None):
        index.setdefault(norm(p.name), []).append(p)
    rows = []
    for path in sorted((RAW / MODEL).glob("*.json")):
        trip = json.loads(path.read_text())["trip"]
        for day in trip["days"]:
            for s in day["stops"]:
                place, method = match_name(s["name"], index)
                rows.append({"run": path.stem, "date": day["date"], "llm_name": s["name"],
                             "place_id": place.id if place else "", "db_name": place.name if place else "",
                             "method": method, "ok": ""})
    with (RUNS / "matches.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)}개  {dict(Counter(r['method'] for r in rows))}")
    print("runs/matches.csv 의 ok 칸: 맞으면 비워 두고, 틀리면 x, 다른 곳이면 그 place_id")


# ---------------------------------------------------------------- 3. 채점

def _time(s: str) -> dt.time:
    h, m = map(int, s.split(":"))
    return dt.time(min(h, 23), m)


def baseline_trip(req: dict, run: dict, by_id: dict[str, Place], matches: dict) -> tuple[Trip, int, int]:
    """LLM 답 -> Trip. 확인된 장소만 담는다. (trip, 전체 장소 수, 확인 불가 수)"""
    days, total, unknown = [], 0, 0
    for i, day in enumerate(run["trip"]["days"]):
        stops = []
        for s in day["stops"]:
            total += 1
            pid = matches.get((run["key"], day["date"], s["name"]))
            if not pid:
                unknown += 1
                continue
            place = by_id[pid]
            stops.append(Stop(id=f"{i}-{len(stops)}", place=place, start=_time(s["start"]),
                              end=_time(s["end"]), cost=place.fee or 0))
        days.append(Day(date=dt.date.fromisoformat(day["date"]), stops=stops))
    trip = Trip(region="jeju", start_date=req["start_date"], end_date=req["end_date"],
                budget=req.get("budget"), days=days)
    return trip, total, unknown


PARKING_MINUTES = 5
KAKAO_FUTURE = "https://apis-navi.kakaomobility.com/v1/future/directions"


class KakaoTravel:
    """카카오모빌리티 미래 길찾기. 여행 날짜가 지났으니 다가오는 같은 요일·시각으로 묻는다. runs/kakao_cache.json 에 저장."""

    def __init__(self):
        from dotenv import dotenv_values

        self.key = dotenv_values(ROOT / ".env").get("KAKAO_REST_API_KEY") or ""
        if not self.key:
            sys.exit(".env 에 KAKAO_REST_API_KEY 가 없음")
        self.path = RUNS / "kakao_cache.json"
        self.cache = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.calls = 0
        # 도로를 못 찾은 구간은 가짜 도구 값으로 대신한다 (failed 로 센다)
        self.mock = MockToolbox()

    @staticmethod
    def departure(date: dt.date, at: dt.time) -> dt.datetime:
        today = dt.date.today()
        ahead = (date.weekday() - today.weekday()) % 7 or 7
        minute = at.minute // 10 * 10
        return dt.datetime.combine(today + dt.timedelta(days=ahead), dt.time(at.hour, minute))

    def route_key(self, a, b, date: dt.date, at: dt.time) -> str:
        dep = self.departure(date, at)
        return f"{a.lng:.5f},{a.lat:.5f}>{b.lng:.5f},{b.lat:.5f}@{dep:%a%H%M}"

    def failed(self, trip: Trip) -> int:
        """일정 안에서 길찾기 실패로 가짜 값을 쓴 구간 수"""
        return sum(self.cache.get(self.route_key(a.place, b.place, d.date, a.end), 0) is None
                   for d in trip.days for a, b in zip(d.stops, d.stops[1:]))

    def minutes(self, a, b, date: dt.date, at: dt.time) -> int:
        dep = self.departure(date, at)
        key = self.route_key(a, b, date, at)
        if key not in self.cache:
            import httpx

            res = httpx.get(KAKAO_FUTURE, timeout=10, headers={"Authorization": f"KakaoAK {self.key}"},
                            params={"origin": f"{a.lng},{a.lat}", "destination": f"{b.lng},{b.lat}",
                                    "departure_time": dep.strftime("%Y%m%d%H%M")})
            res.raise_for_status()
            route = res.json()["routes"][0]
            # 104 = 출발지와 도착지가 5m 이내
            self.cache[key] = route["summary"]["duration"] if route["result_code"] == 0 else (
                0 if route["result_code"] == 104 else None)
            self.calls += 1
            if self.calls % 50 == 0:
                self.save()
        sec = self.cache[key]
        if sec is None:
            return self.mock.travel_minutes(a, b)
        return math.ceil(sec / 60) + (PARKING_MINUTES if sec else 0)

    def save(self):
        self.path.write_text(json.dumps(self.cache, ensure_ascii=False))


class KakaoToolbox(MockToolbox):
    """에이전트가 일정을 짤 때 카카오 이동시간을 쓰게 한다. 출발 시각을 모르는 호출은 가짜 도구 값"""

    def __init__(self, kakao: KakaoTravel, **kw):
        super().__init__(**kw)
        self.kakao = kakao

    def travel_minutes(self, a, b, mode="car", date=None, at=None) -> int:
        if mode != "car" or date is None or at is None:
            return super().travel_minutes(a, b, mode)
        return self.kakao.minutes(a, b, date, at)


def with_legs(trip: Trip, tools: MockToolbox, kakao: "KakaoTravel | None" = None) -> Trip:
    for day in trip.days:
        day.legs = [Leg(minutes=kakao.minutes(a.place, b.place, day.date, a.end) if kakao
                        else tools.travel_minutes(a.place, b.place))
                    for a, b in zip(day.stops, day.stops[1:])]
    return trip


def score_trip(trip: Trip, tools: MockToolbox) -> list:
    rainy = {d.date: tools.rainy_hours(_center([s.place for s in d.stops])) for d in trip.days if d.stops}
    return check_trip(trip, rainy)


def summarize(results: list[dict]) -> dict:
    days = sum(r["days"] for r in results)
    bad = sum(r["days_with_error"] for r in results)
    stops = sum(r["stops"] for r in results)
    errors, warnings = Counter(), Counter()
    for r in results:
        errors.update(r["errors"])
        warnings.update(r["warnings"])
    return {
        "runs": len(results), "days": days, "days_with_error": bad,
        "violation_rate": round(bad / days, 3) if days else None,
        "stops_per_day": round(stops / days, 2) if days else None,
        "thin_days": sum(r["thin_days"] for r in results),
        "unverified_rate": round(sum(r["unknown"] for r in results) / max(1, sum(r["total"] for r in results)), 3),
        "over_budget": sum(r["over_budget"] for r in results),
        "errors_by_type": dict(errors.most_common()), "warnings_by_type": dict(warnings.most_common()),
    }


def one(trip: Trip, violations: list, total: int, unknown: int) -> dict:
    err_dates = {v.date for v in violations if v.severity == "error" and v.date}
    return {
        "days": len(trip.days), "days_with_error": sum(d.date in err_dates for d in trip.days),
        "stops": sum(len(d.stops) for d in trip.days),
        "thin_days": sum(len(d.stops) <= 2 for d in trip.days),
        "total": total, "unknown": unknown,
        "over_budget": int(any(v.type == "budget" for v in violations)),
        "errors": Counter(v.type for v in violations if v.severity == "error"),
        "warnings": Counter(v.type for v in violations if v.severity == "warning"),
    }


def load_review(places: tuple[Place, ...]) -> dict[str, str | None]:
    """match_review.csv -> {정규화한 LLM 이름: place_id 또는 None(확인 불가)}. 맞음이면 키가 없다."""
    by_name: dict[str, str] = {}
    for p in sorted(places, key=lambda p: p.hours is None):
        by_name.setdefault(p.name, p.id)
    out: dict[str, str | None] = {}
    with (HERE / "match_review.csv").open() as f:
        for r in csv.DictReader(f):
            d = r["decision"].strip()
            if d.lower() == "x":
                out[norm(r["llm_name"])] = None
            elif d.startswith("다른 곳:"):
                name = d.split(":", 1)[1].strip()
                if name not in by_name:
                    raise KeyError(f"match_review.csv: DB 에 없는 이름 {name}")
                out[norm(r["llm_name"])] = by_name[name]
    return out


def load_matches(places: tuple[Place, ...]) -> dict:
    review = load_review(places)
    out = {}
    with (RUNS / "matches.csv").open() as f:
        for r in csv.DictReader(f):
            key = norm(r["llm_name"])
            out[(r["run"], r["date"], r["llm_name"])] = (
                review[key] if key in review else r["place_id"]) or ""
    return out


def score(requests: list[dict], places: tuple[Place, ...], travel: str) -> None:
    by_id = {p.id: p for p in places}
    matches = load_matches(places)
    kakao = KakaoTravel() if travel == "kakao" else None
    base, agent = [], []
    failed = {"llm_only": 0, "agent": 0}
    for req in requests:
        rain = {k: set(v) for k, v in (req.get("rain") or {}).items()}
        tools = MockToolbox(rain=rain, places=places)
        for k in range(REPEATS):
            path = RAW / MODEL / f"{req['id']}_{k}.json"
            run = json.loads(path.read_text()) | {"key": path.stem}
            trip, total, unknown = baseline_trip(req, run, by_id, matches)
            trip = with_legs(trip, tools, kakao)
            base.append(one(trip, score_trip(trip, tools), total, unknown))
            failed["llm_only"] += kakao.failed(trip) if kakao else 0
        treq = t.TripRequest(**{k: v for k, v in req.items() if k not in ("id", "rain")})
        # 에이전트는 채점과 같은 이동시간으로 일정을 짠다. 일정의 legs 를 그대로 채점
        planner = KakaoToolbox(kakao, rain=rain, places=places) if kakao else tools
        trip = run_planning(treq, planner).trip
        n = sum(len(d.stops) for d in trip.days)
        agent.append(one(trip, score_trip(trip, tools), n, 0))
        failed["agent"] += kakao.failed(trip) if kakao else 0
        if kakao:
            print(f"  {req['id']}  카카오 호출 누적 {kakao.calls}")

    if kakao:
        kakao.save()
        print(f"카카오 호출 {kakao.calls}번, 길찾기 실패로 가짜 도구 사용 {failed}구간")
    result = {"date": dt.date.today().isoformat(), "model": MODEL, "travel": travel,
              "kakao_fallback_legs": failed if kakao else None,
              "llm_only": summarize(base), "agent": summarize(agent)}
    out = RUNS / f"score_{result['date']}_{travel}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    for name in ("llm_only", "agent"):
        s = result[name]
        print(f"\n[{name}] {s['runs']}회  위반률 {s['violation_rate']}  ({s['days_with_error']}/{s['days']}일)"
              f"  하루 {s['stops_per_day']}곳  2곳 이하 날 {s['thin_days']}  확인 불가 {s['unverified_rate']}"
              f"  예산 초과 {s['over_budget']}")
        print(f"  오류 {s['errors_by_type']}")
        print(f"  경고 {s['warnings_by_type']}")
    print(f"\nwrote {out.relative_to(ROOT)}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("step", choices=["generate", "match", "score"])
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--only", help="요청 id 몇 개만 (쉼표)")
    p.add_argument("--travel", choices=["mock", "kakao"], default="kakao")
    a = p.parse_args()
    requests = json.loads((ROOT / "eval" / "requests.json").read_text())
    if a.only:
        requests = [r for r in requests if r["id"] in a.only.split(",")]
    if a.step == "generate":
        generate(requests, a.workers)
        return
    places = load_db_places()
    if places is None:
        sys.exit("DB 연결 안 됨")
    if a.step == "match":
        match(places)
    else:
        score(requests, places, a.travel)


if __name__ == "__main__":
    main()
