"""Spring 백엔드가 구현할 도구 API의 명세용 앱.

실제로 띄우는 서버가 아니라 OpenAPI 문서를 뽑기 위한 껍데기다.
경로와 형식은 tools/registry.py 에서 가져온다.
"""

from fastapi import FastAPI

from app.tools.registry import TOOLS


def _endpoint(spec):
    def endpoint(body):
        raise NotImplementedError

    endpoint.__annotations__ = {"body": spec.input, "return": spec.output}
    return endpoint


app = FastAPI(
    title="Pibot Backend Tools",
    version="0.1.0",
    description="Spring 백엔드가 구현하고 AI 서버가 호출한다. 요청 헤더에 X-Internal-Key 필요.",
)

for spec in TOOLS:
    if spec.owner == "backend":
        app.add_api_route(
            spec.path,
            _endpoint(spec),
            methods=["POST"],
            response_model=spec.output,
            summary=spec.description,
            operation_id=spec.name,
        )
