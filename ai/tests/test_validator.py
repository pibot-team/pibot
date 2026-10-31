from datetime import date, time

from app.agent.validator import check_day, check_trip
from app.schemas.itinerary import Day, Leg, OpeningHours, Place, Stop, Trip

# 2026-11-03 = 화요일
TUE = date(2026, 11, 3)


def place(pid, **kw):
    base = {"id": pid, "name": pid, "lat": 33.5, "lng": 126.5,
            "hours": OpeningHours(open=time(9), close=time(18))}
    return Place(**(base | kw))


def stop(sid, start, end, **kw):
    p = kw.pop("place", None) or place(sid)
    return Stop(id=sid, place=p, start=start, end=end, **kw)


def types(violations):
    return [v.type for v in violations]


def test_clean_day_has_no_violations():
    day = Day(date=TUE, stops=[stop("a", time(10), time(11)), stop("b", time(12), time(13))],
              legs=[Leg(minutes=30)])
    assert check_day(day) == []


def test_travel_time_too_short():
    day = Day(date=TUE, stops=[stop("a", time(10), time(11)), stop("b", time(11, 20), time(12))],
              legs=[Leg(minutes=90)])
    assert types(check_day(day)) == ["travel_time"]


def test_closed_weekday():
    day = Day(date=TUE, stops=[stop("a", time(10), time(11), place=place("a", closed_weekdays=[1]))])
    assert types(check_day(day)) == ["closed_day"]


def test_outside_hours():
    day = Day(date=TUE, stops=[stop("a", time(17), time(19))])
    assert types(check_day(day)) == ["outside_hours"]


def test_unknown_hours_is_warning():
    day = Day(date=TUE, stops=[stop("a", time(10), time(11), place=place("a", hours=None))])
    [v] = check_day(day)
    assert v.type == "hours_unknown"
    assert v.severity == "warning"


def test_outdoor_in_rain():
    day = Day(date=TUE, stops=[stop("a", time(14), time(15), place=place("a", indoor="outdoor"))])
    assert types(check_day(day, rainy_hours={14, 15})) == ["rain_outdoor"]
    assert check_day(day, rainy_hours={9}) == []


def test_budget():
    trip = Trip(region="jeju", start_date=TUE, end_date=TUE, budget=10000,
                days=[Day(date=TUE, stops=[stop("a", time(10), time(11), cost=15000)])])
    assert types(check_trip(trip)) == ["budget"]


def test_overlapping_stops():
    day = Day(date=TUE, stops=[stop("a", time(10), time(11)), stop("b", time(10, 30), time(12))])
    assert "invalid_time" in types(check_day(day))


def test_missing_lunch_is_warning():
    day = Day(date=TUE, stops=[stop("a", time(10), time(12)), stop("b", time(13), time(15))],
              legs=[Leg(minutes=10)])
    [v] = check_day(day)
    assert v.type == "missing_meal" and v.severity == "warning"


def test_lunch_at_restaurant_is_fine():
    lunch = place("r", category="음식점")
    day = Day(date=TUE, stops=[stop("a", time(10), time(11)), stop("r", time(12), time(13), place=lunch),
                               stop("b", time(14), time(15))],
              legs=[Leg(minutes=10), Leg(minutes=10)])
    assert check_day(day) == []


def test_no_parking_only_for_car():
    no_lot = place("a", parking=False)
    day = Day(date=TUE, stops=[stop("a", time(10), time(11), place=no_lot)])
    assert types(check_day(day, mode="car")) == ["no_parking"]
    assert check_day(day, mode="walk") == []
