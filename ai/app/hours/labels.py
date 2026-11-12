"""라벨링 시트에 쓴 정답 문법을 읽는다.

    09:00~18:00 / 화-금 09:00~19:00 / 6-8월 09:00~18:30 마감 18:00 / 24시간 / 미확인
"""

import datetime as dt
import re

from app.hours.model import WEEKDAYS, Closures, Hours, HoursRule

TIME = r"(\d{1,2}):(\d{2})"
RULE = re.compile(
    rf"^(?:(?P<m1>\d{{1,2}})-(?P<m2>\d{{1,2}})월\s+)?"
    rf"(?:(?P<w1>[{WEEKDAYS}])(?:-(?P<w2>[{WEEKDAYS}]))?\s+)?"
    rf"{TIME}~{TIME}(?:\s+마감\s+{TIME})?$"
)


def to_time(h: str, m: str) -> dt.time:
    return dt.time(int(h) % 24, int(m))


def span(start: int, end: int, size: int, base: int = 0) -> list[int]:
    """3-10월, 토-월 처럼 끝이 앞보다 작으면 한 바퀴 돈다."""
    out, i = [], start
    while True:
        out.append(i + base)
        if i == end:
            return out
        i = (i + 1) % size


def parse_rule(line: str) -> HoursRule:
    m = RULE.match(line.strip())
    if not m:
        raise ValueError(f"영업시간 형식이 아님: {line!r}")
    g = m.groups()
    months = span(int(g[0]) - 1, int(g[1]) - 1, 12, base=1) if g[0] else None
    weekdays = None
    if g[2]:
        a = WEEKDAYS.index(g[2])
        weekdays = span(a, WEEKDAYS.index(g[3]), 7) if g[3] else [a]
    return HoursRule(
        months=months, weekdays=weekdays,
        open=to_time(g[4], g[5]), close=to_time(g[6], g[7]),
        last_entry=to_time(g[8], g[9]) if g[8] else None,
    )


def parse_hours(text: str) -> Hours:
    text = (text or "").strip()
    if text in ("", "미확인"):
        return Hours(status="unknown")
    if text == "24시간":
        return Hours(status="always")
    return Hours(status="known", rules=[parse_rule(line) for line in text.splitlines()
                                        if line.strip()])


def parse_closures(weekly: str, other: str) -> Closures:
    weekly = (weekly or "").strip()
    if weekly in ("", "미확인"):
        days = None
    elif weekly == "없음":
        days = []
    else:
        days = sorted(WEEKDAYS.index(d.strip()) for d in weekly.split(","))
    return Closures(weekly=days, other=split_list(other))


def split_list(text: str) -> list[str]:
    return sorted({t.strip() for t in (text or "").split(",") if t.strip()})
