from app.indoor import rules


def test_name_and_tag_rules():
    assert rules.classify("본태박물관", "문화시설", []) == ("indoor", True)
    assert rules.classify("도두봉 오름", "관광지", []) == ("outdoor", True)
    assert rules.classify("동문재래시장", "쇼핑", []) == ("indoor", True)
    assert rules.classify("만장굴", "관광지", ["동굴"]) == ("unknown", False)
    assert rules.classify("어딘가", "관광지", ["실내관광지"]) == ("indoor", True)


def test_category_default_and_unknown():
    assert rules.classify("어느 식당", "음식점", []) == ("indoor", True)
    assert rules.classify("어느 체험장", "레포츠", []) == ("outdoor", True)
    assert rules.classify("섭지코지", "관광지", []) == ("unknown", False)
