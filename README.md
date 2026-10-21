# Pibot

여행 전에는 일정을 짜 주고, 여행 중에 계획이 틀어지면 고쳐 주고, 일정 사이 빈 시간은 채워 주는 여행 AI 에이전트.

- 서비스 범위: 국내 전체
- MVP 검증 지역: 제주

## 구조

```
backend/   FastAPI + LangGraph 에이전트
  app/schemas/   일정 JSON 스키마 (두 담당이 같이 쓰는 형식)
  app/agent/     Planner, Validator, 재계획 그래프
  app/tools/     TourAPI, 카카오, 기상청 등 외부 API 래퍼
app/       모바일 앱 (Expo / PWA 결정 후 추가)
data/      데이터 수집 스크립트
eval/      평가 데이터셋과 스크립트
docs/      문서
```

## 로컬 실행

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example ../.env   # API 키 채우기
uvicorn app.main:app --reload
```

테스트:

```bash
cd backend
pytest
```
