from app.schemas import tools as t
from app.tools.registry import TOOLS


def test_tool_names_are_unique():
    names = [tool.name for tool in TOOLS]
    assert len(names) == len(set(names))


def test_every_tool_has_json_schema():
    for tool in TOOLS:
        definition = tool.llm_definition()
        assert definition["input_schema"]["type"] == "object"
        tool.output.model_json_schema()


def test_replan_input_example():
    req = t.ReplanIn.model_validate({
        "trip": {
            "region": "jeju",
            "start_date": "2026-11-03",
            "end_date": "2026-11-03",
            "days": [{"date": "2026-11-03", "stops": []}],
        },
        "event": {
            "type": "waiting",
            "at": "2026-11-03T12:10:00",
            "location": {"lat": 33.25, "lng": 126.41},
            "minutes": 40,
            "message": "웨이팅 40분",
        },
    })
    assert req.event.minutes == 40
