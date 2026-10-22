# backend

Spring Boot 백엔드. 담당 sonyeseul63.

- 앱이 호출하는 API, DB, 로그인, 일정·여행 상태 저장, 푸시 알림
- ai 서버가 호출하는 도구 API: [docs/api/backend-tools.openapi.json](../docs/api/backend-tools.openapi.json)
- ai 서버 호출: [docs/api/ai.openapi.json](../docs/api/ai.openapi.json)

포트는 8080. Spring 프로젝트 세팅 후 CI와 `docker-compose.yml`의 backend 항목을 추가한다.
