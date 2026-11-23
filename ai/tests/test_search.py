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

