import httpx

from app.config import settings

LOCAL_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
DIRECTIONS_URL = "https://apis-navi.kakaomobility.com/v1/directions"


def _headers() -> dict:
    return {"Authorization": f"KakaoAK {settings.kakao_rest_api_key}"}


async def search_places(query: str, x: float | None = None, y: float | None = None,
                        radius: int | None = None) -> dict:
    params = {"query": query}
    if x is not None and y is not None:
        params |= {"x": x, "y": y}
        if radius:
            params["radius"] = radius
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(LOCAL_URL, params=params, headers=_headers())
        res.raise_for_status()
        return res.json()


async def car_directions(origin: tuple[float, float], dest: tuple[float, float]) -> dict:
    """origin, dest = (lng, lat)"""
    params = {"origin": f"{origin[0]},{origin[1]}", "destination": f"{dest[0]},{dest[1]}"}
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(DIRECTIONS_URL, params=params, headers=_headers())
        res.raise_for_status()
        return res.json()
