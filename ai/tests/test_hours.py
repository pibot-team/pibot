import datetime as dt

import pytest

from app.hours import labels, rules


def t(s: str) -> dt.time:
    return dt.time.fromisoformat(s)


def test_label_rule_with_months_wrapping_year():
    rule = labels.parse_rule("11-2월 09:00~17:00 마감 16:00")
    assert rule.months == [11, 12, 1, 2]
    assert (rule.open, rule.close, rule.last_entry) == (t("09:00"), t("17:00"), t("16:00"))


def test_label_weekday_range_and_closures():
    assert labels.parse_rule("토-월 09:00~21:00").weekdays == [5, 6, 0]
    assert labels.parse_closures("수,목", "명절, 1월 1일").weekly == [2, 3]
    assert labels.parse_closures("없음", "").weekly == []
    assert labels.parse_closures("미확인", "").weekly is None


def test_label_rejects_unknown_format():
    with pytest.raises(ValueError):
        labels.parse_hours("아침 9시부터")


@pytest.mark.parametrize("text,status", [
    ("상시 개방", "always"),
    ("- 입실 14:00- 퇴실 12:00", "unknown"),
    ("※ 방문 시 전화문의 요망", "unknown"),
    ("10:00~20:00", "known"),
])
def test_hours_status(text, status):
    hours, _ = rules.parse_hours(text)
    assert hours.status == status


def test_hours_last_order_and_break_time():
    hours, ok = rules.parse_hours("11:00~19:3014:00~17:00 준비시간18:30 주문 마감")
    assert ok
    assert hours.rules[0].open == t("11:00")
    assert hours.rules[0].close == t("19:30")
    assert hours.rules[0].last_entry == t("18:30")
    assert len(hours.rules) == 1


def test_hours_break_in_parentheses_keeps_main_range():
    hours, _ = rules.parse_hours("09:00~18:00(휴게시간 17:50~17:55)")
    assert [(r.open, r.close) for r in hours.rules] == [(t("09:00"), t("18:00"))]


def test_hours_by_season():
    hours, ok = rules.parse_hours(
        "- 6월~8월 09:00~18:30 (입장 마감 18:00)- 9월~5월 09:00~18:00 (입장 마감 17:30)")
    assert ok
    assert [r.months[0] for r in hours.rules] == [6, 9]
    assert [r.last_entry for r in hours.rules] == [t("18:00"), t("17:30")]


def test_two_zones_is_not_confident():
    hours, ok = rules.parse_hours("[전시실]10:00~18:00[3층]09:30~18:00")
    assert not ok
    assert len(hours.rules) == 1


def test_closures():
    c, _ = rules.parse_closures("매주 일요일 / 매월 둘째, 넷째 월요일")
    assert (c.weekly, c.other) == ([6], ["매달 2·4주 월"])
    c, _ = rules.parse_closures("매주 월요일 / 1월1일 / 설·추석 연휴")
    assert (c.weekly, c.other) == ([0], ["1월 1일", "설 연휴", "추석 연휴"])
    c, _ = rules.parse_closures("연중무휴※ 우천시 휴무 전화문의 요망")
    assert (c.weekly, c.other) == ([], [])
    c, _ = rules.parse_closures("※ 자세한 사항은 전화문의 요망")
    assert c.weekly is None


def test_notices():
    found = rules.find_notices("09:00~18:00 ※ 기상 악화 시 조기 마감", "※ 재료 소진시 조기마감")
    assert [n.type for n in found] == ["날씨", "조기 마감"]
    assert rules.find_notices("상시 개방※ 자세한 사항은 전화문의 요망", None) == []


def _llm_out(**kw):
    from app.hours.llm import LLMOutput
    base = {"hours_status": "known", "rules": [], "weekly_closed": [], "other_closures": [],
            "notices": []}
    return LLMOutput.model_validate(base | kw)


def test_llm_output_with_times_from_text():
    from app.hours.llm import to_parsed
    out = _llm_out(rules=[{"months": None, "weekdays": None, "open": "9:00",
                           "close": "18:00", "last_entry": "17:00"}],
                   weekly_closed=[0], notices=[{"type": "날씨", "text": "우천시 휴무"}])
    parsed = to_parsed(out, "09:00~18:00 (입장 마감 17:00)")
    assert parsed.hours.rules[0].open == t("09:00")
    assert parsed.closures.weekly == [0]
    assert parsed.notices[0].type == "날씨"


def test_llm_made_up_time_becomes_unknown():
    from app.hours.llm import to_parsed
    out = _llm_out(rules=[{"months": None, "weekdays": None, "open": "10:00",
                           "close": "22:00", "last_entry": None}])
    assert to_parsed(out, "※ 방문 전 전화문의").hours.status == "unknown"


@pytest.mark.parametrize("text,expected", [
    ("명절", ["명절"]),
    ("설·추석 당일", ["설 당일", "추석 당일"]),
    ("설날, 추석", ["설 당일", "추석 당일"]),
    ("추석 연휴", ["추석 연휴"]),
])
def test_holidays(text, expected):
    assert sorted(rules.holidays(text)) == expected
