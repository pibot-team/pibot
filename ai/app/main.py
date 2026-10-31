"""AI 서버. Spring 백엔드가 호출한다."""

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.agent import entry
from app.config import settings
from app.schemas import tools as t


def check_internal_key(x_internal_key: str | None = Header(default=None)):
    if settings.internal_api_key and x_internal_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="invalid internal key")


app = FastAPI(title="Pibot AI", version="0.1.0")


@app.exception_handler(NotImplementedError)
async def not_implemented(_: Request, __: NotImplementedError):
    return JSONResponse(status_code=501, content={"detail": "not implemented yet"})


@app.get("/health")
def health():
    return {"status": "ok"}


internal = [Depends(check_internal_key)]


@app.post("/agent/plan-trip", response_model=t.PlanTripOut, dependencies=internal,
          summary="조건으로 일정을 만든다", operation_id="plan_trip")
def plan_trip(req: t.TripRequest):
    return entry.plan_trip(req)


@app.post("/agent/replan", response_model=t.ReplanOut, dependencies=internal,
          summary="여행 중 상황에 맞춰 남은 일정을 다시 짠다 (선택지 2~3개)", operation_id="replan")
def replan(req: t.ReplanIn):
    return entry.replan(req)


@app.post("/agent/fill-gap", response_model=t.FillGapOut, dependencies=internal,
          summary="남은 시간 안에 다녀올 곳 3개를 추천한다", operation_id="fill_gap")
def fill_gap(req: t.FillGapIn):
    return entry.fill_gap(req)


@app.post("/tools/search-places", response_model=t.SearchPlacesOut, dependencies=internal,
          summary="취향과 조건으로 장소를 찾는다 (RAG)", operation_id="search_places")
def search_places(req: t.SearchPlacesIn):
    return entry.search_places(req)


@app.post("/tools/validate-trip", response_model=t.ValidateTripOut, dependencies=internal,
          summary="일정 규칙 위반을 찾는다", operation_id="validate_trip")
def validate_trip(req: t.ValidateTripIn):
    return entry.validate_trip(req)
