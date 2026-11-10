"""어떤 날짜에 장소가 여는지, 몇 시부터 몇 시까지인지.

일정 검사, 장소 검색, 경로 최적화가 같이 쓴다.
"""

import datetime as dt
import re
from dataclasses import dataclass

from app.hours import holidays
from app.hours.model import WEEKDAYS, Hours

ALL_DAY = (dt.time(0, 0), dt.time(23, 59))


@dataclass(frozen=True)
class DayHours:
    open: dt.time
    close: dt.time
    last_entry: dt.time | None = None

    def contains(self, start: dt.time, end: dt.time) -> bool:
        if self.close <= self.open:  # 자정을 넘긴다
            return start >= self.open or end <= self.close
        return self.open <= start and end <= self.close


@dataclass(frozen=True)
class Closure:
    reason: str
    # 명절처럼 원문이 어느 날인지 확실하지 않으면 경고로만
    certain: bool = True


def hours_on(hours: Hours | None, day: dt.date) -> DayHours | None | bool:
    """그날 영업시간. 모르면 None, 규칙에 그날이 없으면 False(쉬는 날)."""
    if hours is None or hours.status == "unknown":
        return None
    if hours.status == "always":
        return DayHours(*ALL_DAY)
    matches = [
        r for r in hours.rules
        if (r.months is None or day.month in r.months)
        and (r.weekdays is None or day.weekday() in r.weekdays)
    ]
    if not matches:
        return False
    # 조건이 더 자세한 규칙을 먼저
    rule = max(matches, key=lambda r: (r.months is not None) + (r.weekdays is not None))
    return DayHours(rule.open, rule.close, rule.last_entry)


def _nth_weekday(day: dt.date) -> tuple[int, bool]:
    """그 달 몇 번째 같은 요일인지, 마지막인지."""
    nth = (day.day - 1) // 7 + 1
    last = (day + dt.timedelta(days=7)).month != day.month
    return nth, last


def _monthly(rule: str, day: dt.date) -> bool:
    m = re.fullmatch(rf"매달 ([\d·마지막]+)주 ([{WEEKDAYS}])", rule)
    if not m or WEEKDAYS.index(m[2]) != day.weekday():
        return False
    nth, last = _nth_weekday(day)
    weeks = m[1].split("·")
    return str(nth) in weeks or ("마지막" in weeks and last)


def _date(rule: str, day: dt.date) -> bool:
    m = re.fullmatch(r"(\d{1,2})월 (\d{1,2})일", rule)
    return bool(m) and (int(m[1]), int(m[2])) == (day.month, day.day)


def _season(rule: str, day: dt.date) -> bool:
    m = re.fullmatch(r"(\d{1,2})월\s*~\s*(\d{1,2})월", rule)
    if not m:
        return False
    a, b = int(m[1]), int(m[2])
    return a <= day.month <= b if a <= b else day.month >= a or day.month <= b


HOLIDAY_RULES = {"설 당일", "설 연휴", "추석 당일", "추석 연휴", "명절", "법정공휴일", "임시공휴일"}


def closure_on(weekly: list[int] | None, other: list[str], day: dt.date) -> Closure | None:
    if weekly and day.weekday() in weekly:
        return Closure(f"매주 {WEEKDAYS[day.weekday()]}요일 휴무")
    tags = holidays.tags(day)
    for rule in other:
        if _date(rule, day) or _monthly(rule, day) or _season(rule, day):
            return Closure(f"{rule} 휴무")
        if rule in HOLIDAY_RULES:
            if tags is None:
                continue  # 그 해 공휴일 데이터가 없으면 판단하지 않는다
            if rule in tags:
                # "명절"은 당일만 쉬는지 연휴 내내 쉬는지 원문에 없다
                return Closure(f"{rule} 휴무", certain=rule != "명절")
    return None
