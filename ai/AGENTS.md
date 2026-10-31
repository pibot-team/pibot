# ai/

Pibot AI 서버. FastAPI + LangGraph. 담당 Gwakgarin.

## 작업 범위

- ai/, docs/ 만 고친다
- backend/, app/ 은 sonyeseul63 담당. 읽기만 하고 고치지 않는다
- docs/api/*.json 은 직접 고치지 않는다. scripts/export_openapi.py 로 만든다
- app/schemas/ 를 바꾸는 PR은 sonyeseul63 에게 리뷰 요청

## 명령

```bash
cd ai
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,agent]"

pytest
ruff check .
python scripts/export_openapi.py   # 스키마 바꿨을 때
uvicorn app.main:app --reload
```

PR 올리기 전에 pytest, ruff 통과. 스키마 바꿨으면 명세도 다시 뽑아서 같이 커밋.

## 구조

```
app/schemas/   일정·도구 입출력 형식 (명세의 원본)
app/agent/     graph 일정 만들기 / validator 검사 / gap 빈틈 채우기 / search 장소 검색 / entry 진입점
app/tools/     mock 가짜 도구 / backend_client Spring 도구 호출 / registry 도구 목록
app/sample/    제주 샘플 장소
tests/
```

## 규칙

- 시간 계산, 영업시간·휴무 판단, 예산은 코드로 한다. LLM에 맡기지 않는다
- LLM은 장소 고르기, 의도 분류, 추천 이유 문장 같은 판단에만 쓴다
- 백엔드 도구는 MockToolbox 로 개발·테스트한다. 테스트는 API 키나 네트워크 없이 돌아야 한다
- 데이터에 없는 값(영업시간 등)은 추측해서 채우지 않는다. None 으로 두고 "미확인" 처리
- 새 기능은 테스트와 같이 올린다
- 주석은 필요한 곳만 짧게

## Git

- 브랜치: feat/ fix/ data/ docs/ chore/ + 짧은 설명
- main 에 직접 push 하지 않는다. PR → CI 통과 → squash merge
- 커밋 메시지는 한국어로 짧게. 사람이 쓴 것처럼, Co-Authored-By 같은 표시는 넣지 않는다
- 커밋 메일은 레포 설정(noreply) 그대로 쓴다
- 키·토큰은 .env 에만 둔다. 코드나 문서에 넣지 않는다
- force push, 히스토리 수정 금지

## 작업 단위

- 이슈 하나 = 브랜치 하나 = PR 하나
- 이슈에 적힌 완료 조건(테스트)이 통과하면 끝
- 이슈 범위 밖 파일은 고치지 않는다. 필요하면 이슈에 메모만 남긴다
