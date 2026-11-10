"""일정 규칙 검사기.

LLM 없이 코드로만 검사한다. Planner가 만든 일정이든 여행 중 다시 짠 일정이든
모두 여기를 거친다.
"""

from datetime import time

from app.hours.calendar import closure_on, hours_on
from app.schemas.itinerary import Day, TravelMode, Trip, Violation

MEAL_CATEGORIES = {"음식점", "시장"}
LUNCH_FROM, LUNCH_TO = time(11, 0), time(14, 30)
# 조기 마감 안내가 있는 곳은 닫기 이 시간 안쪽 방문이면 경고
EARLY_CLOSE_MARGIN = 120


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _needs_lunch(day: Day) -> bool:
    if not day.stops:
        return False
    return day.stops[0].start <= time(12, 0) and day.stops[-1].end >= time(14, 0)


def _has_lunch(day: Day) -> bool:
    return any(
        s.place.category in MEAL_CATEGORIES and LUNCH_FROM <= s.start <= LUNCH_TO
        for s in day.stops
    )


def check_day(day: Day, rainy_hours: set[int] | None = None,
              mode: TravelMode = "car") -> list[Violation]:
    violations: list[Violation] = []

    for i, stop in enumerate(day.stops):
        place = stop.place

        if stop.end <= stop.start:
            violations.append(Violation(
                type="invalid_time", date=day.date, stop_id=stop.id,
                message=f"{place.name} 끝나는 시각이 시작보다 빠름",
            ))
        if i > 0 and stop.start < day.stops[i - 1].end:
            violations.append(Violation(
                type="invalid_time", date=day.date, stop_id=stop.id,
                message=f"{day.stops[i - 1].place.name}과(와) {place.name} 시간이 겹침",
            ))

        closure = closure_on(place.closed_weekdays, place.other_closures, day.date)
        today = hours_on(place.hours, day.date)
        if closure:
            violations.append(Violation(
                type="closed_day", severity="error" if closure.certain else "warning",
                date=day.date, stop_id=stop.id,
                message=f"{place.name}은(는) 이날 쉼 ({closure.reason})",
            ))
        elif today is False:
            violations.append(Violation(
                type="closed_day", date=day.date, stop_id=stop.id,
                message=f"{place.name}은(는) 이날 영업하지 않음",
            ))
        elif today is None:
            violations.append(Violation(
                type="hours_unknown", severity="warning", date=day.date, stop_id=stop.id,
                message=f"{place.name} 영업시간 미확인",
            ))
        else:
            if not today.contains(stop.start, stop.end):
                violations.append(Violation(
                    type="outside_hours", date=day.date, stop_id=stop.id,
                    message=(
                        f"{place.name} 영업시간({today.open:%H:%M}~{today.close:%H:%M}) "
                        f"밖에 방문"
                    ),
                ))
            elif today.last_entry and stop.start > today.last_entry:
                violations.append(Violation(
                    type="last_entry", date=day.date, stop_id=stop.id,
                    message=f"{place.name} 입장·주문 마감({today.last_entry:%H:%M}) 뒤에 도착",
                ))
            if (any(n.type == "조기 마감" for n in place.notices)
                    and _minutes(today.close) - _minutes(stop.start) < EARLY_CLOSE_MARGIN):
                violations.append(Violation(
                    type="notice", severity="warning", date=day.date, stop_id=stop.id,
                    message=f"{place.name}은(는) 일찍 닫을 수 있어서 늦은 방문은 위험",
                ))

        stay = range(stop.start.hour, max(stop.end.hour, stop.start.hour + 1))
        raining = bool(rainy_hours) and any(h in rainy_hours for h in stay)
        if raining and place.indoor == "outdoor":
            violations.append(Violation(
                type="rain_outdoor", date=day.date, stop_id=stop.id,
                message=f"{place.name}은(는) 실외인데 비 예보 시간대",
            ))
        weather = next((n for n in place.notices if n.type == "날씨"), None)
        if raining and weather:
            violations.append(Violation(
                type="notice", severity="warning", date=day.date, stop_id=stop.id,
                message=f"{place.name} 비 예보: {weather.text}",
            ))

        if mode == "car" and place.parking is False:
            violations.append(Violation(
                type="no_parking", severity="warning", date=day.date, stop_id=stop.id,
                message=f"{place.name}은(는) 주차장이 없음. 근처 주차장 확인 필요",
            ))

    for i, leg in enumerate(day.legs[: len(day.stops) - 1]):
        prev, nxt = day.stops[i], day.stops[i + 1]
        arrive = _minutes(prev.end) + leg.minutes
        if arrive > _minutes(nxt.start):
            violations.append(Violation(
                type="travel_time", date=day.date, stop_id=nxt.id,
                message=(
                    f"{prev.place.name} → {nxt.place.name} 이동 {leg.minutes}분, "
                    f"{arrive - _minutes(nxt.start)}분 늦게 도착"
                ),
            ))

    if _needs_lunch(day) and not _has_lunch(day):
        violations.append(Violation(
            type="missing_meal", severity="warning", date=day.date,
            message="점심 시간(11:00~14:30)에 식사 일정이 없음",
        ))

    return violations


def check_trip(trip: Trip, rainy_hours_by_date: dict | None = None) -> list[Violation]:
    rainy_hours_by_date = rainy_hours_by_date or {}
    violations: list[Violation] = []

    for day in trip.days:
        violations += check_day(day, rainy_hours_by_date.get(day.date), trip.mode)

    if trip.budget is not None:
        total = sum(stop.cost for day in trip.days for stop in day.stops)
        if total > trip.budget:
            violations.append(Violation(
                type="budget",
                message=f"예산 {trip.budget:,}원 초과 (합계 {total:,}원)",
            ))

    return violations
