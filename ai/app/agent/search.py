# 장소 검색. RAG 붙기 전까지는 태그·이름 매칭

import datetime as dt

from app.hours.calendar import HOURS_UNKNOWN, closure_on, hours_on
from app.sample import load_places
from app.schemas import tools as t
from app.schemas.itinerary import Place
from app.tools.mock import haversine_km


def is_open(place: Place, at: dt.datetime) -> bool | None:
    """그 시각에 여는지. 영업시간을 모르면 None."""
    if closure_on(place.closed_weekdays, place.other_closures, at.date()):
        return False
    today = hours_on(place.hours, at.date())
    if today is False:
        return False
    if today is None:
        return None
    return today.contains(at.time(), at.time())


def warnings_for(place: Place) -> list[str]:
    hours = place.hours
    return [HOURS_UNKNOWN] if hours is None or hours.status == "unknown" else []


def filter_and_rank(scored: list[tuple[Place, float]], req: t.SearchPlacesIn) -> t.SearchPlacesOut:
    """조건으로 거르고 점수 순으로. 영업 중 조건이 있으면 영업시간 모르는 곳은 확인된 곳 뒤로."""
    hits = []
    for place, score in scored:
        if place.id in req.exclude_ids:
            continue
        if req.indoor and place.indoor not in req.indoor:
            continue
        opened = is_open(place, req.open_at) if req.open_at else True
        if opened is False:
            continue
        if req.near and req.radius_km is not None:
            here = t.LatLng(lat=place.lat, lng=place.lng)
            if haversine_km(req.near, here) > req.radius_km:
                continue
        hits.append((opened is None, t.PlaceHit(place=place, score=round(score, 4),
                                                 warnings=warnings_for(place))))

    hits.sort(key=lambda h: (h[0], -h[1].score))
    return t.SearchPlacesOut(hits=[h for _, h in hits[: req.limit]])


def _score(place: Place, words: list[str]) -> float:
    text = " ".join([place.name, place.category or "", *place.tags])
    return sum(1 for w in words if w and w in text)


def search_places(req: t.SearchPlacesIn, places: tuple[Place, ...] | None = None
                  ) -> t.SearchPlacesOut:
    """글자 맞추기 검색. DB 가 없을 때(테스트, 샘플)와 일정 만들기 안에서 쓴다."""
    places = places if places is not None else load_places()
    words = req.query.split()
    return filter_and_rank([(p, _score(p, words)) for p in places], req)
