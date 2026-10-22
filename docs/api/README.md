# API 명세

```
앱 (React Native)
   ↓ REST
backend (Spring Boot, :8080)
   ↕ REST
ai (FastAPI, :8000)
```

| 파일 | 누가 구현 | 누가 호출 |
| --- | --- | --- |
| [ai.openapi.json](ai.openapi.json) | ai | backend |
| [backend-tools.openapi.json](backend-tools.openapi.json) | backend | ai |

앱 ↔ backend 사이 API는 backend 쪽에서 따로 정한다.

## 규칙

- 요청·응답은 JSON. 날짜는 `2026-11-03`, 시각은 `13:30`, 일시는 `2026-11-03T13:30:00` (한국 시간)
- 서버 간 호출에는 `X-Internal-Key` 헤더를 붙인다. 값은 각자 `.env`의 `INTERNAL_API_KEY`
- 타임아웃
  - ai → backend 도구 호출: 5초
  - backend → ai `/agent/*` 호출: 60초 (LLM이 여러 번 돎)
- 도구가 실패하면 ai는 가능한 경우 추정값으로 이어간다 (예: 경로 실패 시 직선거리로 이동시간 추정)
- ai의 아직 구현 안 된 API는 `501`을 돌려준다

## 명세 바꾸기

명세는 `ai/app/schemas/tools.py`, `ai/app/tools/registry.py`에서 만들어진다. JSON 파일을 직접 고치지 않는다.

```bash
cd ai
source .venv/bin/activate
python scripts/export_openapi.py
```

결과 JSON까지 같이 커밋한다. 코드와 JSON이 다르면 CI가 실패한다.

## Spring에서 쓰기

`backend-tools.openapi.json`으로 컨트롤러 인터페이스·DTO를, `ai.openapi.json`으로 ai 호출 클라이언트를 생성할 수 있다 (openapi-generator `spring`, `java` 생성기).
