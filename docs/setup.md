# 로컬 세팅

```
app/       React Native (Expo)
backend/   Spring Boot  :8080
ai/        FastAPI      :8000
db         Postgres + pgvector :5432 (docker)
```

서버끼리 주고받는 형식은 [docs/api](api/README.md) 참고.

## 처음 한 번

```bash
git clone https://github.com/pibot-team/pibot.git
cd pibot
cp .env.example .env    # 받은 API 키 채우기 (.env는 git에 안 올라감)
```

## 한 번에 띄우기 (docker)

```bash
docker compose up --build
```

db와 ai가 뜬다. backend는 Spring 세팅 후 `docker-compose.yml`에서 주석을 풀면 같이 뜬다.

## ai 서버만 직접 띄우기

Python 3.11 이상.

```bash
cd ai
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"      # 에이전트까지 쓰면 ".[dev,agent]"
uvicorn app.main:app --reload
```

http://localhost:8000/docs 에서 API를 바로 눌러볼 수 있다.

테스트와 린트:

```bash
cd ai
pytest
ruff check .
```

PR을 올리면 CI에서 같은 걸 돌린다. 둘 다 통과해야 머지할 수 있다.

## backend

[backend/README.md](../backend/README.md) 참고.

## 제주 데이터 빈 값 확인

`.env`에 `TOUR_API_KEY`를 넣은 뒤:

```bash
cd ai
source .venv/bin/activate
python ../data/scripts/collect_tourapi.py
```

결과는 `data/raw/jeju_places.json`에 저장되고, 필드별 빈 값 비율이 출력된다.

## API 키

| 변수 | 어디서 | 쓰는 곳 |
| --- | --- | --- |
| `TOUR_API_KEY` | 공공데이터포털 - 한국관광공사 국문 관광정보 서비스 | backend, ai(빈 값 확인) |
| `KMA_API_KEY` | 공공데이터포털 - 기상청 단기예보 조회서비스 | backend |
| `KAKAO_REST_API_KEY` | 카카오 개발자 - 내 애플리케이션 - REST API 키 | backend |
| `ANTHROPIC_API_KEY` | Anthropic Console | ai |
| `INTERNAL_API_KEY` | 아무 긴 문자열. 둘이 같은 값 | backend, ai |

키는 단톡방이나 코드에 붙이지 말고 각자 `.env`에만 둔다.
