import datetime as dt

from app.agent.search import is_open, search_places
from app.hours.calendar import HOURS_UNKNOWN
from app.sample import load_places
from app.schemas import tools as t

MON_NOON = dt.datetime(2026, 11, 9, 12, 0)


def _places():
    places = load_places()
    unknown = places[0].model_copy(update={"id": "unknown", "hours": None})
    return places, unknown


def test_is_open_unknown_is_none():
    places, unknown = _places()
    assert is_open(unknown, MON_NOON) is None
    assert is_open(places[0], MON_NOON) in (True, False)


def test_unknown_hours_after_known_with_warning():
    places, unknown = _places()
    pool = (unknown, *places)
    out = search_places(t.SearchPlacesIn(query="오름 바다", open_at=MON_NOON, limit=50), pool)
    ids = [h.place.id for h in out.hits]
    assert ids[-1] == "unknown"
    assert out.hits[-1].warnings == [HOURS_UNKNOWN]
    assert all(h.warnings == [] for h in out.hits[:-1])


def test_warning_without_open_at_too():
    _, unknown = _places()
    out = search_places(t.SearchPlacesIn(query="오름", limit=50), (unknown,))
    assert out.hits[0].warnings == [HOURS_UNKNOWN]



def test_indoor_filter_orders_and_warns():
    from app.agent.rain import RAIN_MIXED, RAIN_UNKNOWN
    base = load_places()[0]
    pool = tuple(base.model_copy(update={"id": v, "indoor": v}) for v in ("unknown", "mixed", "indoor"))
    out = search_places(t.SearchPlacesIn(query="", indoor=["indoor", "mixed", "unknown"]), pool)
    assert [h.place.id for h in out.hits] == ["indoor", "mixed", "unknown"]
    assert RAIN_MIXED in out.hits[1].warnings and RAIN_UNKNOWN in out.hits[2].warnings
    assert all(RAIN_MIXED not in w and RAIN_UNKNOWN not in w for w in [out.hits[0].warnings])
