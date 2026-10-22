"""Spring 백엔드가 제공하는 도구를 HTTP로 호출한다."""

import httpx
from pydantic import BaseModel

from app.config import settings
from app.tools.registry import BY_NAME

TIMEOUT_SECONDS = 5


class ToolCallError(Exception):
    pass


async def call_tool(name: str, payload: BaseModel) -> BaseModel:
    spec = BY_NAME[name]
    if spec.owner != "backend":
        raise ValueError(f"{name}은(는) backend 도구가 아님")

    headers = {"X-Internal-Key": settings.internal_api_key}
    try:
        async with httpx.AsyncClient(base_url=settings.backend_url, timeout=TIMEOUT_SECONDS) as c:
            res = await c.post(spec.path, json=payload.model_dump(mode="json"), headers=headers)
            res.raise_for_status()
    except httpx.HTTPError as e:
        raise ToolCallError(f"{name} 호출 실패: {e}") from e

    return spec.output.model_validate(res.json())
