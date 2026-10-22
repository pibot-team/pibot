import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("export_openapi", ROOT / "scripts" / "export_openapi.py")
export_openapi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_openapi)


def test_committed_specs_match_code():
    for name, app in export_openapi.SPECS.items():
        committed = (export_openapi.OUT / name).read_text()
        assert committed == export_openapi.render(app), (
            f"docs/api/{name}가 코드와 다름. `python scripts/export_openapi.py` 실행 후 커밋"
        )


def test_backend_tools_spec_has_every_backend_tool():
    paths = export_openapi.backend_tools_app.openapi()["paths"]
    assert set(paths) == {
        "/internal/tools/travel-time",
        "/internal/tools/optimize-route",
        "/internal/tools/weather",
        "/internal/tools/parking",
        "/internal/tools/place-detail",
    }
