# 장소 검색. RAG 붙기 전까지는 태그·이름 매칭

import datetime as dt

from app.sample import load_places
from app.schemas import tools as t
from app.schemas.itinerary import Place
from app.tools.mock import haversine_km


def is_open(place: Place, at: dt.datetime) -> bool:
    if at.weekday() in place.closed_weekdays:
        return False
    if place.hours is None:
        return True
    return place.hours.open <= at.time() <= place.hours.close


def _score(place: Place, words: list[str]) -> float:
    text = " ".join([place.name, place.category or "", *place.tags])
    return sum(1 for w in words if w and w in text)


def search_places(req: t.SearchPlacesIn, places: tuple[Place, ...] | None = None
                  ) -> t.SearchPlacesOut:
    places = places if places is not None else load_places()
    words = req.query.split()
    hits = []
    for place in places:
        if place.id in req.exclude_ids:
            continue
        if req.indoor and place.indoor not in req.indoor:
            continue
        if req.open_at and not is_open(place, req.open_at):
            continue
        if req.near and req.radius_km is not None:
            here = t.LatLng(lat=place.lat, lng=place.lng)
            if haversine_km(req.near, here) > req.radius_km:
                continue
        hits.append(t.PlaceHit(place=place, score=_score(place, words)))

    hits.sort(key=lambda h: h.score, reverse=True)
    return t.SearchPlacesOut(hits=hits[: req.limit])
