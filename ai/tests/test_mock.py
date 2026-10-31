import datetime as dt

from app.sample import place_by_id
from app.schemas import tools as t
from app.tools.mock import MockToolbox, side_of

JEJU_CITY = t.LatLng(lat=33.4996, lng=126.5312)
SEOGWIPO = t.LatLng(lat=33.2541, lng=126.5600)
DAY = dt.date(2026, 11, 3)


def test_travel_time_is_symmetric_and_positive():
    tools = MockToolbox()
    there = tools.get_travel_time(t.TravelTimeIn(origin=JEJU_CITY, dest=SEOGWIPO))
    back = tools.get_travel_time(t.TravelTimeIn(origin=SEOGWIPO, dest=JEJU_CITY))
    assert there.minutes == back.minutes > 30
    assert there.source == "estimate"


def test_same_point_is_zero_minutes():
    tools = MockToolbox()
    out = tools.get_travel_time(t.TravelTimeIn(origin=JEJU_CITY, dest=JEJU_CITY))
    assert out.minutes == 0


def test_rain_only_on_given_side():
    tools = MockToolbox(rain={"west": {14, 15}})
    west = t.LatLng(lat=33.39, lng=126.24)
    east = t.LatLng(lat=33.46, lng=126.94)
    assert side_of(west) == "west" and side_of(east) == "east"
    assert tools.rainy_hours(west) == {14, 15}
    assert tools.rainy_hours(east) == set()


def stop(place_id, stay=60, fixed=None):
    return t.RouteStop(place=place_by_id(place_id), stay_minutes=stay, fixed_start=fixed)


def test_route_waits_for_opening_time():
    # 아르떼뮤지엄은 10시에 열어서 9시 반에 출발해도 10시부터 머문다
    out = MockToolbox().optimize_route(t.OptimizeRouteIn(
        date=DAY, start_at=dt.time(9, 30), stops=[stop("jeju-012")],
    ))
    assert out.day.stops[0].start == dt.time(10, 0)


def test_route_keeps_fixed_lunch_time():
    out = MockToolbox().optimize_route(t.OptimizeRouteIn(
        date=DAY, start_at=dt.time(9, 30),
        stops=[stop("jeju-013"), stop("jeju-014"), stop("sample-r05", fixed=dt.time(12, 0))],
    ))
    lunch = next(s for s in out.day.stops if s.id == "sample-r05")
    assert lunch.start == dt.time(12, 0)
    for before, after in zip(out.day.stops, out.day.stops[1:]):
        assert before.end <= after.start


def test_route_reports_places_that_dont_fit():
    # 하루에 다 못 들어가는 양이면 빠진 곳을 알려준다
    many = [stop(f"jeju-0{n:02d}", stay=180) for n in range(1, 10)]
    out = MockToolbox().optimize_route(t.OptimizeRouteIn(
        date=DAY, start_at=dt.time(9, 30), stops=many,
    ))
    assert out.unplaced
    assert len(out.day.stops) + len(out.unplaced) == len(many)
