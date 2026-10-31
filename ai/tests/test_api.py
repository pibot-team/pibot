from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TRIP = {
    "region": "jeju",
    "start_date": "2026-11-03",
    "end_date": "2026-11-03",
    "days": [{
        "date": "2026-11-03",
        "stops": [
            {"id": "a", "start": "10:00", "end": "11:00",
             "place": {"id": "a", "name": "A", "lat": 33.5, "lng": 126.5,
                       "hours": {"open": "09:00", "close": "18:00"}}},
            {"id": "b", "start": "11:10", "end": "12:00",
             "place": {"id": "b", "name": "B", "lat": 33.4, "lng": 126.9,
                       "hours": {"open": "09:00", "close": "18:00"}}},
        ],
        "legs": [{"minutes": 60}],
    }],
}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_validate_trip_returns_violations():
    res = client.post("/tools/validate-trip", json={"trip": TRIP})
    assert res.status_code == 200
    assert [v["type"] for v in res.json()["violations"]] == ["travel_time"]


def test_plan_trip():
    req = {"region": "jeju", "start_date": "2026-11-03", "end_date": "2026-11-04"}
    res = client.post("/agent/plan-trip", json=req)
    assert res.status_code == 200
    assert len(res.json()["trip"]["days"]) == 2


def test_replan_not_ready_yet():
    req = {"trip": TRIP, "event": {"type": "rain", "at": "2026-11-03T14:00:00",
                                   "location": {"lat": 33.4, "lng": 126.3}}}
    assert client.post("/agent/replan", json=req).status_code == 501
