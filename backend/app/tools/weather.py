import httpx

from app.config import settings

# 기상청 단기예보. 위경도를 격자(nx, ny)로 바꿔서 요청해야 함
FORECAST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"


async def short_forecast(nx: int, ny: int, base_date: str, base_time: str) -> dict:
    params = {
        "serviceKey": settings.kma_api_key,
        "dataType": "JSON",
        "numOfRows": 1000,
        "pageNo": 1,
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.get(FORECAST_URL, params=params)
        res.raise_for_status()
        return res.json()
