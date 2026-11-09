from app.tools.tourapi import clean_text, place_row

ITEM = {
    "contentid": "123", "contenttypeid": "39", "title": "샘플 식당",
    "mapx": "126.5", "mapy": "33.5", "addr1": "제주시 어딘가", "addr2": "",
    "tel": "", "firstimage": "", "cat3": "A05020100", "modifiedtime": "20261101093000",
}


def test_clean_text_turns_br_into_lines():
    assert clean_text("- 평일 09:00~18:00<br>\n- 주말 10:00~17:00 ") == (
        "- 평일 09:00~18:00\n- 주말 10:00~17:00"
    )
    assert clean_text("") is None
    assert clean_text("<br>") is None


def test_place_row_picks_intro_fields_by_type():
    intro = {"opentimefood": "11:00~20:00", "restdatefood": "매주 화요일",
             "parkingfood": "가능"}
    row = place_row(ITEM, {"overview": "바다 앞<br>식당"}, intro)
    assert row["id"] == "tour:123"
    assert row["category"] == "음식점"
    assert (row["lat"], row["lng"]) == (33.5, 126.5)
    assert row["hours_text"] == "11:00~20:00"
    assert row["rest_text"] == "매주 화요일"
    assert row["fee_text"] is None
    assert row["overview"] == "바다 앞\n식당"
    assert row["phone"] is None
    assert row["source_modified_at"].hour == 9


def test_place_row_without_details():
    row = place_row(ITEM, None, None)
    assert row["hours_text"] is None
    assert row["raw"]["intro"] is None
