"""백엔드 API가 호출하는 에이전트 진입점."""

import logging

from app.agent import gap, graph, search
from app.agent.validator import check_trip
from app.config import settings
from app.places import all_places
from app.schemas import tools as t
from app.tools.mock import MockToolbox

log = logging.getLogger(__name__)


def default_tools() -> MockToolbox:
    # Spring 도구가 준비되면 HTTP로 호출하는 구현으로 바꾼다
    return MockToolbox(places=all_places())


def plan_trip(req: t.TripRequest, tools: MockToolbox | None = None) -> t.PlanTripOut:
    return graph.run_planning(req, tools or default_tools())


def replan(req: t.ReplanIn) -> t.ReplanOut:
    raise NotImplementedError


def fill_gap(req: t.FillGapIn, tools: MockToolbox | None = None) -> t.FillGapOut:
    return gap.fill_gap(req, tools or default_tools())


def search_places(req: t.SearchPlacesIn) -> t.SearchPlacesOut:
    if settings.database_url and settings.gemini_api_key:
        try:
            import psycopg

            from app.rag import search as rag
            from app.rag.embedders import get_embedder

            with psycopg.connect(settings.database_url, connect_timeout=3) as conn:
                return rag.search(req, conn, get_embedder("gemini-embedding-001"))
        except Exception as e:  # noqa: BLE001  DB·임베딩이 안 되면 글자 맞추기로
            log.warning("벡터 검색 실패, 글자 맞추기로 대신: %s", type(e).__name__)
    return search.search_places(req, all_places())


def validate_trip(req: t.ValidateTripIn) -> t.ValidateTripOut:
    rainy = {d: set(hours) for d, hours in req.rainy_hours_by_date.items()}
    return t.ValidateTripOut(violations=check_trip(req.trip, rainy))
