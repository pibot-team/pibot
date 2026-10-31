"""일정 규칙 검사기.

LLM 없이 코드로만 검사한다. Planner가 만든 일정이든 여행 중 다시 짠 일정이든
모두 여기를 거친다.
"""

from datetime import time

from app.schemas.itinerary import Day, TravelMode, Trip, Violation

MEAL_CATEGORIES = {"음식점", "시장"}
LUNCH_FROM, LUNCH_TO = time(11, 0), time(14, 30)


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
    weekday = day.date.weekday()

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

        if weekday in place.closed_weekdays:
            violations.append(Violation(
                type="closed_day", date=day.date, stop_id=stop.id,
                message=f"{place.name}은(는) 이날 휴무",
            ))

        if place.hours is None:
            violations.append(Violation(
                type="hours_unknown", severity="warning", date=day.date, stop_id=stop.id,
                message=f"{place.name} 영업시간 미확인",
            ))
        elif stop.start < place.hours.open or stop.end > place.hours.close:
            violations.append(Violation(
                type="outside_hours", date=day.date, stop_id=stop.id,
                message=(
                    f"{place.name} 영업시간({place.hours.open:%H:%M}~{place.hours.close:%H:%M}) "
                    f"밖에 방문"
                ),
            ))

        if rainy_hours and place.indoor == "outdoor":
            stay = range(stop.start.hour, max(stop.end.hour, stop.start.hour + 1))
            if any(h in rainy_hours for h in stay):
                violations.append(Violation(
                    type="rain_outdoor", date=day.date, stop_id=stop.id,
                    message=f"{place.name}은(는) 실외인데 비 예보 시간대",
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
