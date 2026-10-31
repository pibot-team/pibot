"""백엔드 API가 호출하는 에이전트 진입점."""

from app.agent import gap, graph, search
from app.agent.validator import check_trip
from app.schemas import tools as t
from app.tools.mock import MockToolbox


def default_tools() -> MockToolbox:
    # Spring 도구가 준비되면 HTTP로 호출하는 구현으로 바꾼다
    return MockToolbox()


def plan_trip(req: t.TripRequest, tools: MockToolbox | None = None) -> t.PlanTripOut:
    return graph.run_planning(req, tools or default_tools())


def replan(req: t.ReplanIn) -> t.ReplanOut:
    raise NotImplementedError


def fill_gap(req: t.FillGapIn, tools: MockToolbox | None = None) -> t.FillGapOut:
    return gap.fill_gap(req, tools or default_tools())


def search_places(req: t.SearchPlacesIn) -> t.SearchPlacesOut:
    return search.search_places(req)


def validate_trip(req: t.ValidateTripIn) -> t.ValidateTripOut:
    rainy = {d: set(hours) for d, hours in req.rainy_hours_by_date.items()}
    return t.ValidateTripOut(violations=check_trip(req.trip, rainy))
