import datetime as dt
import json

import pytest

from app.agent.validator import check_day
from app.hours import calendar, holidays
from app.hours.model import Hours, HoursRule, Notice
from app.schemas.itinerary import Day, Place, Stop

T = dt.time


def hours(*rules, status="known"):
    return Hours(status=status, rules=list(rules))


def test_season_and_weekday_rules():
    h = hours(HoursRule(months=[3, 4, 5, 6, 7, 8, 9, 10], open=T(9), close=T(18), last_entry=T(17)),
              HoursRule(months=[11, 12, 1, 2], open=T(9), close=T(17)))
    assert calendar.hours_on(h, dt.date(2026, 7, 1)).close == T(18)
    assert calendar.hours_on(h, dt.date(2026, 12, 1)).close == T(17)
    weekend = hours(HoursRule(weekdays=[1, 2, 3, 4, 5, 6], open=T(10), close=T(19)))
    assert calendar.hours_on(weekend, dt.date(2026, 11, 9)) is False  # 월요일은 규칙에 없음
    assert calendar.hours_on(None, dt.date(2026, 11, 9)) is None
    assert calendar.hours_on(hours(status="always"), dt.date(2026, 11, 9)).open == T(0)


def test_overnight_hours():
    late = calendar.DayHours(T(18), T(2))
    assert late.contains(T(23), T(23, 30))
    assert not late.contains(T(15), T(16))


def test_closures_without_holiday_data():
    nov3 = dt.date(2026, 11, 3)  # 화요일, 첫째 주
    assert calendar.closure_on([1], [], nov3).reason == "매주 화요일 휴무"
    assert calendar.closure_on([], ["매달 1주 화"], nov3)
    assert not calendar.closure_on([], ["매달 2·4주 화"], nov3)
    assert calendar.closure_on([], ["1월 1일"], dt.date(2027, 1, 1))
    assert calendar.closure_on([], ["2월~8월"], dt.date(2026, 3, 1))
    assert not calendar.closure_on([], ["2월~8월"], nov3)
    assert not calendar.closure_on(None, [], nov3)


@pytest.fixture
def chuseok(tmp_path, monkeypatch):
    path = tmp_path / "holidays.json"
    path.write_text(json.dumps({"2026-09-24": "추석", "2026-09-25": "추석", "2026-09-26": "추석",
                                "2026-10-03": "개천절"}))
    monkeypatch.setattr(holidays, "PATH", path)
    holidays._load.cache_clear()
    yield
    holidays._load.cache_clear()


def test_holiday_closures(chuseok):
    eve, day = dt.date(2026, 9, 24), dt.date(2026, 9, 25)
    assert holidays.tags(day) >= {"추석 당일", "추석 연휴", "명절", "법정공휴일"}
    assert "추석 당일" not in holidays.tags(eve)
    assert calendar.closure_on([], ["추석 당일"], day)
    assert not calendar.closure_on([], ["추석 당일"], eve)
    assert calendar.closure_on([], ["추석 연휴"], eve)
    assert not calendar.closure_on([], ["명절"], eve).certain
    assert calendar.closure_on([], ["법정공휴일"], dt.date(2026, 10, 3))
    assert holidays.tags(dt.date(2030, 1, 1)) is None


def _day(place, start, end, date=dt.date(2026, 11, 10)):
    return Day(date=date, stops=[Stop(id="a", place=place, start=start, end=end)])


def _place(**kw):
    return Place(**({"id": "a", "name": "가", "lat": 33.5, "lng": 126.5,
                     "hours": hours(HoursRule(open=T(10), close=T(18), last_entry=T(17)))} | kw))


def types(vs):
    return [v.type for v in vs]


def test_validator_last_entry_and_notices():
    assert types(check_day(_day(_place(), T(17, 30), T(17, 50)))) == ["last_entry"]
    early = _place(notices=[Notice(type="조기 마감", text="재료 소진시 조기마감")])
    assert types(check_day(_day(early, T(16, 10), T(16, 40)))) == ["notice"]
    assert types(check_day(_day(early, T(12), T(13)))) == []
    rainy = _place(indoor="outdoor", notices=[Notice(type="날씨", text="우천시 휴무")])
    assert types(check_day(_day(rainy, T(11), T(12)), rainy_hours={11})) == ["rain_outdoor", "notice"]
