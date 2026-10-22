"""docs/api/ 에 OpenAPI 명세를 다시 뽑는다.

    cd ai && python scripts/export_openapi.py

형식(schemas/tools.py)을 바꾸면 이걸 돌리고 결과도 같이 커밋한다.
CI에서 명세가 코드와 다르면 실패한다.
"""

import json
from pathlib import Path

from app.main import app as ai_app
from app.spec.backend_tools import app as backend_tools_app

ROOT = Path(__file__).resolve().parents[1]

OUT = ROOT.parent / "docs" / "api"

SPECS = {
    "ai.openapi.json": ai_app,
    "backend-tools.openapi.json": backend_tools_app,
}


def render(app) -> str:
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, app in SPECS.items():
        (OUT / name).write_text(render(app))
        print(f"wrote docs/api/{name}")


if __name__ == "__main__":
    main()
