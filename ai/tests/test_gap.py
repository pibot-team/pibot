import datetime as dt

from app.agent.gap import BUFFER_MINUTES, fill_gap
from app.sample import place_by_id
from app.schemas import tools as t
from app.schemas.itinerary import Stop
from app.tools.mock import MockToolbox

HALLIM = t.LatLng(lat=33.3893, lng=126.2393)
NOW = dt.datetime(2026, 11, 4, 12, 10)


def ask(minutes, tools=None, next_place_id=None, **kw):
    next_stop = None
    if next_place_id:
        place = place_by_id(next_place_id)
        next_stop = Stop(id=place.id, place=place, start=dt.time(13, 30), end=dt.time(14, 30))
    req = t.FillGapIn(location=HALLIM, now=NOW, until=NOW + dt.timedelta(minutes=minutes),
                      next_stop=next_stop, **kw)
    return fill_gap(req, tools or MockToolbox())


def test_at_most_three():
    assert len(ask(120).suggestions) <= 3


def test_suggestions_fit_in_time():
    tools = MockToolbox()
    out = ask(60, tools, next_place_id="sample-r05")
    nxt = place_by_id("sample-r05")
    assert out.suggestions
    for s in out.suggestions:
        back = tools.travel_minutes(s.place, nxt)
        assert s.travel_minutes + s.stay_minutes + back + BUFFER_MINUTES <= 60


def test_no_outdoor_when_raining():
    rainy = MockToolbox(rain={"west": set(range(24))})
    out = ask(90, rainy)
    assert out.suggestions
    assert all(s.place.indoor != "outdoor" for s in out.suggestions)


def test_no_restaurant_and_no_next_place():
    out = ask(90, next_place_id="sample-r05")
    for s in out.suggestions:
        assert s.place.category != "음식점"
        assert s.place.id != "sample-r05"


def test_too_little_time_gives_nothing():
    assert ask(10).suggestions == []


def test_preference_comes_first():
    out = ask(90, preferences=["카페"])
    assert "카페" in out.suggestions[0].place.tags


def test_current_place_not_suggested():
    seongsan = place_by_id("jeju-001")
    here = t.LatLng(lat=seongsan.lat, lng=seongsan.lng)
    req = t.FillGapIn(location=here, now=dt.datetime(2026, 11, 5, 10, 30),
                      until=dt.datetime(2026, 11, 5, 12, 30))
    out = fill_gap(req, MockToolbox())
    assert out.suggestions
    assert all(s.place.id != "jeju-001" for s in out.suggestions)
