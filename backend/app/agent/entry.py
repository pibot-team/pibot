"""백엔드 API가 호출하는 에이전트 진입점."""

from app.agent.validator import check_trip
from app.schemas import tools as t


def plan_trip(req: t.TripRequest) -> t.PlanTripOut:
    raise NotImplementedError


def replan(req: t.ReplanIn) -> t.ReplanOut:
    raise NotImplementedError


def fill_gap(req: t.FillGapIn) -> t.FillGapOut:
    raise NotImplementedError


def validate_trip(req: t.ValidateTripIn) -> t.ValidateTripOut:
    rainy = {d: set(hours) for d, hours in req.rainy_hours_by_date.items()}
    return t.ValidateTripOut(violations=check_trip(req.trip, rainy))
