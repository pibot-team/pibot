"""에이전트 그래프 (LangGraph).

여행 전:  조건 입력 -> plan -> validate -> (위반 있으면) replan, 최대 3번 -> 확정
여행 중:  상황 입력 -> 상태 갱신(지난 일정 고정) -> 남은 구간 plan -> validate -> 변경 비교

같은 plan / validate 노드를 두 흐름이 같이 쓴다.
"""

MAX_REPLAN = 3


def build_planning_graph():
    raise NotImplementedError


def build_in_trip_graph():
    raise NotImplementedError
