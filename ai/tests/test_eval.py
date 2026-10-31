import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_eval", ROOT / "scripts" / "run_eval.py")
run_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_eval)


def test_datasets_size():
    assert len(run_eval.load("requests.json")) == 30
    assert len(run_eval.load("gap_requests.json")) == 20


def test_run_small_set(tmp_path):
    result = run_eval.run(run_eval.load("requests.json")[:3],
                          run_eval.load("gap_requests.json")[:3])
    trips, gaps = result["trips"], result["gaps"]

    assert trips["requests"] == 3
    assert {"days", "violation_rate", "errors_by_type", "warnings_by_type",
            "over_budget"} <= set(trips)
    assert 0 <= trips["violation_rate"] <= 1
    assert gaps["cases"] == 3
    assert {"on_time_rate", "empty_cases"} <= set(gaps)
    assert 0 <= gaps["on_time_rate"] <= 1

    path = run_eval.save(result, tmp_path)
    assert path.parent == tmp_path
    assert run_eval.report(result)
