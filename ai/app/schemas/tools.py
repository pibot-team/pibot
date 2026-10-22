"""도구와 에이전트 진입점의 입출력 형식.

- 백엔드 도구: 결과가 항상 같은 계산. 에이전트가 골라서 호출한다.
- AI 도구: RAG 검색, 일정 검사.
- 진입점: 백엔드 API가 에이전트를 부를 때 쓰는 형식.

여기 있는 모델이 그대로 LLM 도구 설명(JSON 스키마)이 된다.
필드를 바꿀 때는 PR에서 서로 확인한다.
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.itinerary import Day, Indoor, Place, Stop, TravelMode, Trip, Violation


class LatLng(BaseModel):
    lat: float
    lng: float


# ---------------------------------------------------------------- 백엔드 도구


class TravelTimeIn(BaseModel):
    """두 지점 사이 이동시간."""

    origin: LatLng
    dest: LatLng
    mode: TravelMode = "car"
    depart_at: dt.datetime | None = None


class TravelTimeOut(BaseModel):
    minutes: int
    distance_km: float
    # estimate = API 실패 시 직선거리로 추정한 값
    source: Literal["api", "cache", "estimate"]


class RouteStop(BaseModel):
    place: Place
    stay_minutes: int
    # 예약처럼 시간이 정해진 방문. 최적화할 때 이 시각은 움직이지 않는다.
    fixed_start: dt.time | None = None


class OptimizeRouteIn(BaseModel):
    """고른 장소들의 방문 순서와 도착 시각을 정한다."""

    date: dt.date
    start_at: dt.time
    start_point: LatLng | None = None
    end_point: LatLng | None = None
    mode: TravelMode = "car"
    stops: list[RouteStop]


class OptimizeRouteOut(BaseModel):
    day: Day
    total_travel_minutes: int
    # 시간이 모자라 넣지 못한 장소 id
    unplaced: list[str] = Field(default_factory=list)


class WeatherIn(BaseModel):
    point: LatLng
    date: dt.date


class HourlyWeather(BaseModel):
    hour: int
    rain_prob: int
    rain_mm: float
    temp_c: float | None = None


class WeatherOut(BaseModel):
    hours: list[HourlyWeather]


class ParkingIn(BaseModel):
    point: LatLng
    radius_m: int = 500


class ParkingLot(BaseModel):
    name: str
    lat: float
    lng: float
    walk_minutes: int | None = None
    fee: str | None = None
    hours: str | None = None


class ParkingOut(BaseModel):
    lots: list[ParkingLot]


class PlaceDetailIn(BaseModel):
    place_id: str


class PlaceDetail(Place):
    overview: str | None = None
    # TourAPI 원문 (이용시간, 쉬는날 등). hours 파싱 결과와 같이 둔다.
    usage_text: str | None = None
    phone: str | None = None


# ---------------------------------------------------------------- AI 도구


class SearchPlacesIn(BaseModel):
    """취향·조건으로 장소 찾기 (RAG)."""

    query: str
    near: LatLng | None = None
    radius_km: float | None = None
    open_at: dt.datetime | None = None
    indoor: list[Indoor] | None = None
    exclude_ids: list[str] = Field(default_factory=list)
    limit: int = 10


class PlaceHit(BaseModel):
    place: Place
    score: float


class SearchPlacesOut(BaseModel):
    hits: list[PlaceHit]


class ValidateTripIn(BaseModel):
    trip: Trip
    rainy_hours_by_date: dict[dt.date, list[int]] = Field(default_factory=dict)


class ValidateTripOut(BaseModel):
    violations: list[Violation]


# ---------------------------------------------------------------- 진입점 (백엔드 -> 에이전트)


class TripRequest(BaseModel):
    region: str
    start_date: dt.date
    end_date: dt.date
    mode: TravelMode = "car"
    travelers: int = 1
    budget: int | None = None
    preferences: list[str] = Field(default_factory=list)
    pace: Literal["relaxed", "normal", "packed"] = "normal"
    start_point: LatLng | None = None


class PlanTripOut(BaseModel):
    trip: Trip
    # 재계획 후에도 남은 위반 (경고 포함)
    violations: list[Violation] = Field(default_factory=list)


EventType = Literal["rain", "waiting", "delay", "tired", "closed", "free_time"]


class TripEvent(BaseModel):
    type: EventType
    at: dt.datetime
    location: LatLng
    # 웨이팅·지연 시간
    minutes: int | None = None
    # 휴무를 발견한 장소
    place_id: str | None = None
    # 사용자가 한 말 그대로
    message: str | None = None


class ReplanIn(BaseModel):
    trip: Trip
    event: TripEvent


class ReplanOption(BaseModel):
    label: str
    trip: Trip
    changed_stop_ids: list[str]
    violations: list[Violation] = Field(default_factory=list)


class ReplanOut(BaseModel):
    # 2~3개. 사용자가 고른다.
    options: list[ReplanOption]


class FillGapIn(BaseModel):
    location: LatLng
    now: dt.datetime
    # 다음 고정 일정 시작 시각
    until: dt.datetime
    next_stop: Stop | None = None
    mode: TravelMode = "car"
    preferences: list[str] = Field(default_factory=list)
    exclude_ids: list[str] = Field(default_factory=list)


class GapSuggestion(BaseModel):
    place: Place
    travel_minutes: int
    stay_minutes: int
    reason: str


class FillGapOut(BaseModel):
    suggestions: list[GapSuggestion]
