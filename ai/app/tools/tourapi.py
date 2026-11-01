import httpx

from app.config import settings

# 엔드포인트·파라미터 이름은 키 발급 후 공공데이터포털 문서로 한 번 더 확인
BASE_URL = "https://apis.data.go.kr/B551011/KorService2"
JEJU_AREA_CODE = 39


def _common() -> dict:
    return {
        "serviceKey": settings.data_go_kr_key,
        "MobileOS": "ETC",
        "MobileApp": "Pibot",
        "_type": "json",
    }


async def area_based_list(area_code: int, page: int = 1, rows: int = 100,
                          content_type_id: int | None = None) -> dict:
    params = _common() | {"areaCode": area_code, "pageNo": page, "numOfRows": rows}
    if content_type_id:
        params["contentTypeId"] = content_type_id
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.get(f"{BASE_URL}/areaBasedList2", params=params)
        res.raise_for_status()
        return res.json()


async def detail_intro(content_id: str, content_type_id: int) -> dict:
    """이용시간, 쉬는날, 주차 등. 자유 텍스트라 파싱 필요."""
    params = _common() | {"contentId": content_id, "contentTypeId": content_type_id}
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.get(f"{BASE_URL}/detailIntro2", params=params)
        res.raise_for_status()
        return res.json()
