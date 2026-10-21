from fastapi import FastAPI

from app.agent.validator import check_trip
from app.schemas.itinerary import Trip, Violation

app = FastAPI(title="Pibot")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/validate", response_model=list[Violation])
def validate(trip: Trip):
    return check_trip(trip)
