"""비 올 때 실내·실외 다루기. 확실한 실외만 막고, 애매한 곳은 뒤로 보내며 경고를 붙인다."""

RAIN_MIXED = "일부 야외예요. 비 오면 실내 공간 위주로 둘러보세요"
RAIN_UNKNOWN = "실내외를 확인하지 못했어요"

# 비 올 때 순서. 작을수록 먼저
RAIN_ORDER = {"indoor": 0, "mixed": 1, "unknown": 2, "outdoor": 3}


def rain_warning(indoor: str) -> str | None:
    return {"mixed": RAIN_MIXED, "unknown": RAIN_UNKNOWN}.get(indoor)
