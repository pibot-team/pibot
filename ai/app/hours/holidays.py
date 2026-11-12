"""공휴일·명절 날짜. 천문연 특일 정보를 받아 둔 data/holidays.json 을 읽는다.

파일에 없는 해는 모른다(None). 받는 방법은 data/scripts/fetch_holidays.py.
"""

import datetime as dt
import json
from functools import cache
from pathlib import Path

PATH = Path(__file__).resolve().parents[3] / "data" / "holidays.json"


@cache
def _load() -> dict[dt.date, str]:
    if not PATH.exists():
        return {}
    raw = json.loads(PATH.read_text())
    return {dt.date.fromisoformat(d): name for d, name in raw.items()}


def known_years() -> set[int]:
    return {d.year for d in _load()}


def _cluster(day: dt.date, name: str) -> list[dt.date]:
    """같은 이름(설날, 추석)이 이어진 날짜 묶음."""
    days = _load()
    start = day
    while days.get(start - dt.timedelta(days=1)) == name:
        start -= dt.timedelta(days=1)
    out, d = [], start
    while days.get(d) == name:
        out.append(d)
        d += dt.timedelta(days=1)
    return out


def tags(day: dt.date) -> set[str] | None:
    """그날 해당하는 휴무 표현. 그 해 데이터가 없으면 None."""
    if day.year not in known_years():
        return None
    name = _load().get(day)
    if name is None:
        return set()
    out = {"법정공휴일"}
    if "임시" in name:
        out.add("임시공휴일")
    for holiday, label in (("설날", "설"), ("추석", "추석")):
        if name == holiday:
            run = _cluster(day, holiday)
            out |= {f"{label} 연휴", "명절"}
            if day == run[len(run) // 2]:
                out.add(f"{label} 당일")
    return out
