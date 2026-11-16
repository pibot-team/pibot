# select -> arrange -> validate -> (오류 있으면) fix -> select, 최대 3번
# select는 지금 규칙으로 고름. 나중에 LLM 붙일 자리

import datetime as dt
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent.search import search_places
from app.agent.validator import check_trip
from app.schemas import tools as t
from app.schemas.itinerary import Place, Trip, Violation
from app.tools.mock import MockToolbox, stay_minutes

MAX_REPLAN = 3
DAY_START = dt.time(9, 30)
LUNCH_AT = dt.time(12, 0)
SIGHTS_PER_DAY = {"relaxed": 3, "normal": 4, "packed": 5}
MEAL_CATEGORIES = {"음식점"}
AREA_ORDER = ["west", "east", "south", "city"]


def area_of(place: Place) -> str:
    if place.lng < 126.40:
        return "west"
    if place.lng > 126.75:
        return "east"
    if place.lat < 33.33:
        return "south"
    return "city"


def _dates(req: t.TripRequest) -> list[dt.date]:
    days = (req.end_date - req.start_date).days + 1
    return [req.start_date + dt.timedelta(days=i) for i in range(days)]


def _center(places: list[Place]) -> t.LatLng:
    return t.LatLng(lat=sum(p.lat for p in places) / len(places),
                    lng=sum(p.lng for p in places) / len(places))


class PlanState(TypedDict):
    req: t.TripRequest
    picks: dict[dt.date, list[Place]]
    excluded: set[str]
    trip: Trip | None
    violations: list[Violation]
    attempts: int
    free_only: bool  # 예산 넘은 뒤로는 무료 장소로만 다시 채운다


def build_planning_graph(tools: MockToolbox):
    places = tools.all_places()

    def candidates(req, area, used, excluded, meal, free_only=False):
        query = " ".join(req.preferences)
        hits = search_places(t.SearchPlacesIn(query=query, limit=len(places)), places).hits
        return [
            h.place for h in hits
            if area_of(h.place) == area
            and h.place.id not in used | excluded
            and (h.place.category in MEAL_CATEGORIES) == meal
            and not (free_only and h.place.fee)
        ]

    def select(state: PlanState) -> dict:
        req, excluded = state["req"], state["excluded"]
        picks = dict(state["picks"])
        used = {p.id for ps in picks.values() for p in ps}
        n = SIGHTS_PER_DAY[req.pace]

        for i, date in enumerate(_dates(req)):
            area = AREA_ORDER[i % len(AREA_ORDER)]
            day = [p for p in picks.get(date, []) if p.id not in excluded]
            sights = [p for p in day if p.category not in MEAL_CATEGORIES]
            meals = [p for p in day if p.category in MEAL_CATEGORIES]
            more = candidates(req, area, used, excluded, meal=False,
                              free_only=state["free_only"])
            for p in more[: n - len(sights)]:
                sights.append(p)
                used.add(p.id)
            if not meals:
                meals = candidates(req, area, used, excluded, meal=True)[:1]
                used.update(p.id for p in meals)
            picks[date] = sights + meals
        return {"picks": picks}

    def arrange(state: PlanState) -> dict:
        req = state["req"]
        days = []
        for date, chosen in state["picks"].items():
            stops = [
                t.RouteStop(place=p, stay_minutes=stay_minutes(p),
                            fixed_start=LUNCH_AT if p.category in MEAL_CATEGORIES else None)
                for p in chosen
            ]
            out = tools.optimize_route(t.OptimizeRouteIn(
                date=date, start_at=DAY_START, start_point=req.start_point,
                mode=req.mode, stops=stops,
            ))
            days.append(out.day)
        trip = Trip(region=req.region, start_date=req.start_date, end_date=req.end_date,
                    mode=req.mode, budget=req.budget, days=days)
        return {"trip": trip}

    def validate(state: PlanState) -> dict:
        trip = state["trip"]
        rainy = {
            day.date: tools.rainy_hours(_center([s.place for s in day.stops]))
            for day in trip.days if day.stops
        }
        return {"violations": check_trip(trip, rainy)}

    def fix(state: PlanState) -> dict:
        excluded = set(state["excluded"])
        picks = dict(state["picks"])
        free_only = state["free_only"]
        for v in state["violations"]:
            if v.severity != "error":
                continue
            if v.stop_id:
                excluded.add(v.stop_id)
            elif v.type == "budget":
                free_only = True
                # 식당은 구역마다 하나뿐이라 빼면 점심을 다시 못 채움. 식당 말고 비싼 곳을 뺀다
                chosen = [p for ps in picks.values() for p in ps]
                over = sum(p.fee or 0 for p in chosen) - state["req"].budget
                paid = sorted((p for p in chosen
                               if p.category not in MEAL_CATEGORIES and (p.fee or 0) > 0),
                              key=lambda p: p.fee, reverse=True)
                for p in paid:
                    if over <= 0:
                        break
                    excluded.add(p.id)
                    over -= p.fee
        picks = {d: [p for p in ps if p.id not in excluded] for d, ps in picks.items()}
        return {"picks": picks, "excluded": excluded, "free_only": free_only,
                "attempts": state["attempts"] + 1}

    def route(state: PlanState) -> str:
        errors = [v for v in state["violations"] if v.severity == "error"]
        if not errors or state["attempts"] >= MAX_REPLAN:
            return END
        return "fix"

    graph = StateGraph(PlanState)
    graph.add_node("select", select)
    graph.add_node("arrange", arrange)
    graph.add_node("validate", validate)
    graph.add_node("fix", fix)
    graph.add_edge(START, "select")
    graph.add_edge("select", "arrange")
    graph.add_edge("arrange", "validate")
    graph.add_conditional_edges("validate", route, ["fix", END])
    graph.add_edge("fix", "select")
    return graph.compile()


def run_planning(req: t.TripRequest, tools: MockToolbox) -> t.PlanTripOut:
    graph = build_planning_graph(tools)
    state = graph.invoke({
        "req": req, "picks": {}, "excluded": set(), "trip": None,
        "violations": [], "attempts": 0, "free_only": False,
    })
    return t.PlanTripOut(trip=state["trip"], violations=state["violations"])


def build_in_trip_graph():
    raise NotImplementedError
