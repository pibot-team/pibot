import datetime as dt

from app.agent.graph import run_planning
from app.schemas import tools as t
from app.tools.mock import MockToolbox

START = dt.date(2026, 11, 3)


def plan(days=3, tools=None, **kw):
    req = t.TripRequest(region="jeju", start_date=START,
                        end_date=START + dt.timedelta(days=days - 1), **kw)
    return run_planning(req, tools or MockToolbox())


def errors(out):
    return [v for v in out.violations if v.severity == "error"]


def test_makes_one_day_per_date_with_lunch():
    out = plan(3, preferences=["바다"])
    assert len(out.trip.days) == 3
    for day in out.trip.days:
        assert day.stops
        assert any(s.place.category == "음식점" for s in day.stops)


def test_no_errors_on_normal_day():
    assert errors(plan(3)) == []


def test_no_place_twice():
    ids = [s.place.id for d in plan(3).trip.days for s in d.stops]
    assert len(ids) == len(set(ids))


def test_rain_on_west_moves_away_from_outdoor():
    out = plan(1, MockToolbox(rain={"west": set(range(9, 20))}))
    assert errors(out) == []
    assert all(s.place.indoor != "outdoor" for s in out.trip.days[0].stops)


def test_stays_in_budget():
    out = plan(2, budget=60000)
    total = sum(s.cost for d in out.trip.days for s in d.stops)
    assert total <= 60000 or errors(out)
