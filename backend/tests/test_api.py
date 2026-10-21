from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_validate_returns_violations():
    trip = {
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
    res = client.post("/validate", json=trip)
    assert res.status_code == 200
    assert [v["type"] for v in res.json()] == ["travel_time"]
