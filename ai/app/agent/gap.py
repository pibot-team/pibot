# 빈틈 채우기: 다음 일정까지 남은 시간 안에 다녀올 수 있는 곳 추천

import datetime as dt

from app.agent.search import is_open
from app.schemas import tools as t
from app.tools.mock import MockToolbox, haversine_km, stay_minutes

BUFFER_MINUTES = 5
MIN_STAY = 15
# 식당 웨이팅 중에 다른 식당을 추천하지 않는다
SKIP_CATEGORIES = {"음식점"}
# 이 거리 안의 장소는 지금 있는 곳으로 보고 추천하지 않는다
HERE_RADIUS_KM = 0.2


def _minutes_between(a: dt.datetime, b: dt.datetime) -> int:
    return int((b - a).total_seconds() // 60)


def fill_gap(req: t.FillGapIn, tools: MockToolbox) -> t.FillGapOut:
    available = _minutes_between(req.now, req.until)
    raining = req.now.hour in tools.rainy_hours(req.location)
    next_place = req.next_stop.place if req.next_stop else None
    exclude = set(req.exclude_ids) | ({next_place.id} if next_place else set())

    scored = []
    for place in tools.all_places():
        if place.id in exclude or place.category in SKIP_CATEGORIES:
            continue
        if haversine_km(req.location, t.LatLng(lat=place.lat, lng=place.lng)) <= HERE_RADIUS_KM:
            continue
        if raining and place.indoor == "outdoor":
            continue

        go = tools.travel_minutes(req.location, place, req.mode)
        back = tools.travel_minutes(place, next_place, req.mode) if next_place else 0
        stay = min(stay_minutes(place), available - go - back - BUFFER_MINUTES)
        if stay < MIN_STAY:
            continue

        arrive = req.now + dt.timedelta(minutes=go)
        leave = arrive + dt.timedelta(minutes=stay)
        if not (is_open(place, arrive) and is_open(place, leave)):
            continue

        match = sum(1 for p in req.preferences if p in " ".join([*place.tags, place.name]))
        indoor_bonus = 2 if raining and place.indoor in ("indoor", "mixed") else 0
        score = match * 3 + indoor_bonus - go / 10
        slack = available - go - stay - back
        scored.append((score, place, go, stay, slack))

    scored.sort(key=lambda s: s[0], reverse=True)
    suggestions = []
    for _, place, go, stay, slack in scored[:3]:
        where = "바로 근처" if go <= 1 else f"{go}분 거리"
        reason = f"{where}, {stay}분 머물러도 다음 일정까지 {slack}분 여유"
        if raining and place.indoor == "indoor":
            reason += ", 실내라 비 걱정 없음"
        elif raining and place.indoor == "mixed":
            reason += ", 실내 공간 있음"
        suggestions.append(t.GapSuggestion(place=place, travel_minutes=go,
                                           stay_minutes=stay, reason=reason))
    return t.FillGapOut(suggestions=suggestions)
