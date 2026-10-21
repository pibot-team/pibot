# 브랜치와 PR 규칙

## 브랜치

- `main`: 항상 돌아가는 상태. 직접 push 안 됨, PR로만 머지
- 작업 브랜치: `종류/짧은-설명`
  - `feat/validator-parking` 기능
  - `fix/tourapi-empty-items` 버그
  - `data/jeju-collect` 데이터 수집·정리
  - `docs/setup` 문서
  - `chore/ci-cache` 설정, 의존성

## 작업 흐름

```bash
git switch main
git pull
git switch -c feat/할-일

# 작업, 커밋
git push -u origin feat/할-일
# GitHub에서 PR 열기
```

1. PR을 열면 CI(린트 + 테스트)가 돈다.
2. 상대방이 리뷰하고 Approve 한다.
3. CI 통과 + Approve 1개면 **Squash and merge**.
4. 머지된 브랜치는 지운다.

## 커밋 메시지

한국어로 짧게, 무엇을 했는지.

```
일정 검사기에 주차 규칙 추가
TourAPI 빈 응답 처리
```

## PR 크기

하루 안에 리뷰할 수 있는 크기로. 스키마(`backend/app/schemas/`)를 바꾸는 PR은 따로 올리고 같이 확인한다.
