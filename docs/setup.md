# 로컬 세팅

## 준비물

- Python 3.11 이상
- Git

## 처음 한 번

```bash
git clone https://github.com/pibot-team/pibot.git
cd pibot

cp .env.example .env    # 받은 API 키 채우기 (.env는 git에 안 올라감)

cd backend
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

에이전트(LangGraph, Anthropic SDK)까지 쓸 때는 `pip install -e ".[dev,agent]"`.

## 서버 실행

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

http://localhost:8000/docs 에서 API를 바로 눌러볼 수 있다.

## 테스트와 린트

```bash
cd backend
pytest
ruff check .
```

PR을 올리면 CI에서 같은 걸 돌린다. 둘 다 통과해야 머지할 수 있다.

## 제주 데이터 수집

`.env`에 `TOUR_API_KEY`를 넣은 뒤:

```bash
cd backend
source .venv/bin/activate
python ../data/scripts/collect_tourapi.py
```

결과는 `data/raw/jeju_places.json`에 저장되고, 필드별 빈 값 비율이 출력된다.

## API 키

| 변수 | 어디서 |
| --- | --- |
| `TOUR_API_KEY` | 공공데이터포털 - 한국관광공사 국문 관광정보 서비스 |
| `KMA_API_KEY` | 공공데이터포털 - 기상청 단기예보 조회서비스 |
| `KAKAO_REST_API_KEY` | 카카오 개발자 - 내 애플리케이션 - REST API 키 |
| `ANTHROPIC_API_KEY` | Anthropic Console |
| `DATABASE_URL` | Supabase 프로젝트 설정 |

키는 단톡방이나 코드에 붙이지 말고 각자 `.env`에만 둔다.
