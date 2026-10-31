# Spring 도구 나오기 전까지 쓰는 가짜 도구. 형식은 backend-tools 명세랑 같음

import datetime as dt
import math

from app.sample import load_places, place_by_id
from app.schemas import tools as t
from app.schemas.itinerary import Day, Leg, Place, Stop

ROAD_FACTOR = 1.3
SPEED_KMH = {"car": 40, "transit": 20, "walk": 4.5}
PARKING_MINUTES = {"car": 5, "transit": 10, "walk": 0}
DEFAULT_STAY = 45
DAY_END = dt.time(21, 0)
# 제주 동·서를 나누는 경도 (대략 제주시~서귀포시 중앙)
EAST_WEST_LNG = 126.55


def haversine_km(a: t.LatLng, b: t.LatLng) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a.lat, a.lng, b.lat, b.lng))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


def side_of(point: t.LatLng) -> str:
    return "west" if point.lng < EAST_WEST_LNG else "east"


def _point(place: Place) -> t.LatLng:
    return t.LatLng(lat=place.lat, lng=place.lng)


def _add(time: dt.time, minutes: int) -> dt.time:
    total = time.hour * 60 + time.minute + minutes
    total = min(total, 23 * 60 + 59)
    return dt.time(total // 60, total % 60)


class MockToolbox:
    def __init__(self, rain: dict[str, set[int]] | None = None):
        # 예: {"west": {14, 15, 16}} -> 서쪽에 14~16시 비
        self.rain = rain or {}

    def get_travel_time(self, req: t.TravelTimeIn) -> t.TravelTimeOut:
        km = haversine_km(req.origin, req.dest) * ROAD_FACTOR
        if km < 0.05:
            return t.TravelTimeOut(minutes=0, distance_km=0, source="estimate")
        minutes = math.ceil(km / SPEED_KMH[req.mode] * 60) + PARKING_MINUTES[req.mode]
        return t.TravelTimeOut(minutes=minutes, distance_km=round(km, 1), source="estimate")

    def travel_minutes(self, a: Place | t.LatLng, b: Place | t.LatLng, mode="car") -> int:
        a = _point(a) if isinstance(a, Place) else a
        b = _point(b) if isinstance(b, Place) else b
        return self.get_travel_time(t.TravelTimeIn(origin=a, dest=b, mode=mode)).minutes

    def get_weather(self, req: t.WeatherIn) -> t.WeatherOut:
        rainy = self.rain.get(side_of(req.point), set())
        return t.WeatherOut(hours=[
            t.HourlyWeather(hour=h, rain_prob=80 if h in rainy else 10,
                            rain_mm=3.0 if h in rainy else 0.0)
            for h in range(24)
        ])

    def rainy_hours(self, point: t.LatLng) -> set[int]:
        weather = self.get_weather(t.WeatherIn(point=point, date=dt.date.today()))
        return {h.hour for h in weather.hours if h.rain_prob >= 60 or h.rain_mm >= 1}

    def find_parking(self, req: t.ParkingIn) -> t.ParkingOut:
        return t.ParkingOut(lots=[])

    def get_place_detail(self, req: t.PlaceDetailIn) -> t.PlaceDetail:
        place = place_by_id(req.place_id)
        if place is None:
            raise KeyError(req.place_id)
        return t.PlaceDetail(**place.model_dump())

    def optimize_route(self, req: t.OptimizeRouteIn) -> t.OptimizeRouteOut:
        """가까운 곳부터 방문. 시간이 정해진 방문(예약)은 그 시각에 맞춘다."""
        fixed = sorted((s for s in req.stops if s.fixed_start), key=lambda s: s.fixed_start)
        remaining = [s for s in req.stops if not s.fixed_start]

        pos = req.start_point or (_point(req.stops[0].place) if req.stops else None)
        now = req.start_at
        stops: list[Stop] = []
        legs: list[Leg] = []
        travel_total = 0

        def visit(rs: t.RouteStop, start: dt.time, travel: int):
            nonlocal pos, now, travel_total
            if stops:
                legs.append(Leg(mode=req.mode, minutes=travel))
                travel_total += travel
            end = _add(start, rs.stay_minutes)
            stops.append(Stop(id=rs.place.id, place=rs.place, start=start, end=end,
                              fixed=rs.fixed_start is not None, cost=rs.place.fee or 0))
            pos, now = _point(rs.place), end

        def fits(rs: t.RouteStop) -> tuple[dt.time, int] | None:
            travel = self.travel_minutes(pos, rs.place, req.mode) if stops else 0
            start = _add(now, travel)
            if rs.place.hours and start < rs.place.hours.open:
                start = rs.place.hours.open
            end = _add(start, rs.stay_minutes)
            if end > DAY_END or (rs.place.hours and end > rs.place.hours.close):
                return None
            if fixed:
                nxt = fixed[0]
                back = self.travel_minutes(rs.place, nxt.place, req.mode)
                if _add(end, back) > nxt.fixed_start:
                    return None
            return start, travel

        while remaining or fixed:
            options = [(rs, fit) for rs in remaining if (fit := fits(rs))]
            if options:
                rs, (start, travel) = min(options, key=lambda o: o[1][1])
                remaining.remove(rs)
                visit(rs, start, travel)
            elif fixed:
                rs = fixed.pop(0)
                travel = self.travel_minutes(pos, rs.place, req.mode) if stops else 0
                visit(rs, max(rs.fixed_start, _add(now, travel)), travel)
            else:
                break

        return t.OptimizeRouteOut(
            day=Day(date=req.date, stops=stops, legs=legs),
            total_travel_minutes=travel_total,
            unplaced=[rs.place.id for rs in remaining],
        )

    def all_places(self) -> tuple[Place, ...]:
        return load_places()


def stay_minutes(place: Place) -> int:
    return place.typical_stay_minutes or DEFAULT_STAY
