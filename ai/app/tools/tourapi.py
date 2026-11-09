import asyncio
import datetime as dt
import re

import httpx

from app.config import settings

BASE_URL = "https://apis.data.go.kr/B551011/KorService2"
# 법정동 시도 코드. 예전 areaCode=39 로 찾으면 제주 장소가 일부만 나온다.
JEJU_LDONG_REGN_CD = 50

# 숙박(32)은 일단 뺀다
CONTENT_TYPES = {12: "관광지", 14: "문화시설", 28: "레포츠", 38: "쇼핑", 39: "음식점"}

# detailIntro2 필드 이름이 종류마다 다르다
INTRO_FIELDS = {
    12: {"hours": "usetime", "rest": "restdate", "parking": "parking", "fee": None},
    14: {"hours": "usetimeculture", "rest": "restdateculture", "parking": "parkingculture",
         "fee": "usefee"},
    28: {"hours": "usetimeleports", "rest": "restdateleports", "parking": "parkingleports",
         "fee": "usefeeleports"},
    38: {"hours": "opentime", "rest": "restdateshopping", "parking": "parkingshopping",
         "fee": None},
    39: {"hours": "opentimefood", "rest": "restdatefood", "parking": "parkingfood", "fee": None},
}

KST = dt.timezone(dt.timedelta(hours=9))


def _common() -> dict:
    return {
        "serviceKey": settings.data_go_kr_key,
        "MobileOS": "ETC",
        "MobileApp": "Pibot",
        "_type": "json",
    }


def _retryable(e: Exception) -> bool:
    if isinstance(e, httpx.TimeoutException):
        return True
    return isinstance(e, httpx.HTTPStatusError) and e.response.status_code >= 500


async def _get(op: str, retries: int = 3, **params) -> dict:
    # 공공데이터포털이 가끔 늦게 응답한다. 시간 초과·5xx 만 다시 시도
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                res = await client.get(f"{BASE_URL}/{op}", params=_common() | params)
                res.raise_for_status()
                return res.json()
        except httpx.HTTPError as e:
            if attempt == retries - 1 or not _retryable(e):
                raise
            await asyncio.sleep(2 * (attempt + 1))


def items_of(res: dict) -> list[dict]:
    items = res["response"]["body"]["items"]
    if not items:
        return []
    item = items["item"]
    return item if isinstance(item, list) else [item]


async def area_based_list(regn_cd: int, page: int = 1, rows: int = 100,
                          content_type_id: int | None = None) -> dict:
    params = {"lDongRegnCd": regn_cd, "pageNo": page, "numOfRows": rows}
    if content_type_id:
        params["contentTypeId"] = content_type_id
    return await _get("areaBasedList2", **params)


async def detail_common(content_id: str) -> dict:
    """개요(overview), 홈페이지."""
    return await _get("detailCommon2", contentId=content_id)


async def detail_intro(content_id: str, content_type_id: int) -> dict:
    """이용시간, 쉬는날, 주차 등. 자유 텍스트라 파싱 필요."""
    return await _get("detailIntro2", contentId=content_id, contentTypeId=content_type_id)


def clean_text(value: str | None) -> str | None:
    """<br> 을 줄바꿈으로, 나머지 태그는 지운다. 빈 값은 None."""
    if not value:
        return None
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = re.sub(r"\n{2,}", "\n", text).strip()
    return text or None


def _modified_at(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    return dt.datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=KST)


def place_row(item: dict, common: dict | None, intro: dict | None) -> dict:
    """목록·공통·소개 응답을 places 테이블 한 줄로. 파싱 값은 아직 채우지 않는다."""
    type_id = int(item["contenttypeid"])
    fields = INTRO_FIELDS[type_id]
    intro = intro or {}

    def pick(key: str) -> str | None:
        name = fields[key]
        return clean_text(intro.get(name)) if name else None

    return {
        "id": f"tour:{item['contentid']}",
        "tourapi_id": item["contentid"],
        "name": item["title"],
        "category": CONTENT_TYPES[type_id],
        "cat3": item.get("cat3") or None,
        "lat": float(item["mapy"]),
        "lng": float(item["mapx"]),
        "address": " ".join(filter(None, [item.get("addr1"), item.get("addr2")])) or None,
        "phone": item.get("tel") or None,
        "image_url": item.get("firstimage") or None,
        "overview": clean_text((common or {}).get("overview")),
        "hours_text": pick("hours"),
        "rest_text": pick("rest"),
        "parking_text": pick("parking"),
        "fee_text": pick("fee"),
        "raw": {"list": item, "common": common, "intro": intro or None},
        "source_modified_at": _modified_at(item.get("modifiedtime")),
    }
