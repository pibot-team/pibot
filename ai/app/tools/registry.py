"""에이전트가 쓸 도구 목록.

이름, 설명, 입출력 형식을 한곳에 모아 LLM 도구 정의와 API 명세로 쓴다.
backend 도구는 Spring이 `path`로 제공하고, AI는 HTTP로 호출한다.
"""

from dataclasses import dataclass

from pydantic import BaseModel

from app.schemas import tools as t


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input: type[BaseModel]
    output: type[BaseModel]
    owner: str
    path: str

    def llm_definition(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input.model_json_schema(),
        }


TOOLS = [
    ToolSpec("get_travel_time", "두 지점 사이 이동시간과 거리",
             t.TravelTimeIn, t.TravelTimeOut, "backend", "/internal/tools/travel-time"),
    ToolSpec("optimize_route", "고른 장소들의 방문 순서와 도착 시각을 정한다",
             t.OptimizeRouteIn, t.OptimizeRouteOut, "backend", "/internal/tools/optimize-route"),
    ToolSpec("get_weather", "시간대별 강수확률과 강수량",
             t.WeatherIn, t.WeatherOut, "backend", "/internal/tools/weather"),
    ToolSpec("find_parking", "근처 주차장과 걸어가는 시간",
             t.ParkingIn, t.ParkingOut, "backend", "/internal/tools/parking"),
    ToolSpec("get_place_detail", "장소 상세: 영업시간, 휴무, 주차, 설명",
             t.PlaceDetailIn, t.PlaceDetail, "backend", "/internal/tools/place-detail"),
    ToolSpec("search_places", "취향과 조건으로 장소를 찾는다",
             t.SearchPlacesIn, t.SearchPlacesOut, "ai", "/tools/search-places"),
    ToolSpec("validate_trip", "일정의 휴무·영업시간·이동시간·날씨·예산 위반을 찾는다",
             t.ValidateTripIn, t.ValidateTripOut, "ai", "/tools/validate-trip"),
]

BY_NAME = {tool.name: tool for tool in TOOLS}
