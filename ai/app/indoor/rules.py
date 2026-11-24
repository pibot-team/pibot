"""규칙으로 실내·실외를 정한다. 기준: 비 오는 날 즐길 수 있나, 실내 = 건축물 안.

확실하지 않으면 confident=False 로 돌려준다. 규칙+LLM 방식은 이때만 LLM 에 넘긴다.
"""

from typing import Literal

Indoor = Literal["indoor", "outdoor", "mixed", "unknown"]

# 이름에 들어 있으면 거의 확실한 말. 위에서부터 먼저 맞는 것을 쓴다
NAME_RULES: list[tuple[str, Indoor]] = [
    ("박물관", "indoor"), ("미술관", "indoor"), ("기념관", "indoor"), ("전시관", "indoor"),
    ("갤러리", "indoor"), ("아쿠아리움", "indoor"), ("책방", "indoor"), ("서점", "indoor"),
    ("시장", "indoor"), ("오일장", "indoor"), ("사찰", "indoor"),
    ("오름", "outdoor"), ("해수욕장", "outdoor"), ("해변", "outdoor"), ("포구", "outdoor"),
    ("폭포", "outdoor"), ("올레", "outdoor"), ("둘레길", "outdoor"), ("숲길", "outdoor"),
    ("동굴", "outdoor"), ("해안도로", "outdoor"), ("농장", "outdoor"), ("정원", "outdoor"),
    ("공원", "outdoor"), ("캠핑", "outdoor"), ("카약", "outdoor"), ("요트", "outdoor"),
]
TAG_RULES: list[tuple[str, Indoor]] = [
    ("실내관광지", "indoor"), ("실내", "indoor"), ("미술/박물관", "indoor"),
    ("오름", "outdoor"), ("해변", "outdoor"), ("걷기/등산", "outdoor"), ("숲", "outdoor"),
    ("올레", "outdoor"), ("자연경관", "outdoor"),
]
# 분류만으로 정하는 기본값. 관광지는 섞여 있어서 기본값이 없다
CATEGORY_DEFAULT: dict[str, Indoor] = {
    "음식점": "indoor", "쇼핑": "indoor", "문화시설": "indoor", "레포츠": "outdoor",
}


def classify(name: str, category: str, tags: list[str]) -> tuple[Indoor, bool]:
    for word, value in NAME_RULES:
        if word in name:
            return value, True
    for word, value in TAG_RULES:
        if word in tags:
            return value, True
    if category in CATEGORY_DEFAULT:
        return CATEGORY_DEFAULT[category], True
    return "unknown", False
