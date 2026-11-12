# 영업시간 파서 비교

TourAPI 이용시간·휴무 원문을 영업시간 규칙, 매주 휴무 요일, 기타 휴무, 안내로 바꾸는 방식 비교 (#16).

## 데이터

- 제주 TourAPI 300곳 중 원문이 있는 곳에서 종류별 30곳씩 무작위로 150곳 (seed 20261109)
- 개발용 50곳: 파서와 지시문을 만들 때 본 데이터
- 시험용 100곳: 파서를 고정한 뒤 한 번만 측정
- 정답: 개발용·시험용 모두 LLM 초안을 사람이 한 건씩 검토해 확정 (시험용은 2건 수정). 기준은 `split.csv`, `labels_*.csv` 와 라벨링 시트의 기준 탭
- 원문은 레포에 넣지 않는다. 로컬 DB `places` 에서 id 로 읽는다

## 실행

```bash
cd ai
python ../eval/hours/run_eval.py --split test --method rules
python ../eval/hours/run_eval.py --split test --method llm:claude
python ../eval/hours/run_eval.py --split test --method hybrid:gemini
python ../eval/hours/compare.py --split test
```

## 결과 (시험용 100곳, 2026-11-10)

네 항목(영업시간, 휴무 요일, 기타 휴무, 안내 유형)이 모두 맞아야 정답.

| 방식 | 전체 일치 | 95% 구간 | 100곳 비용 |
| --- | --- | --- | --- |
| Claude Haiku 5.5만 | 88% | 80~93% | $0.028 |
| 규칙 + Gemini 3.5 Flash-Lite | 79% | 70~86% | 무료 등급 |
| 규칙만 | 78% | 69~85% | 0 |
| 규칙 + Claude Haiku 5.5 | 78% | 69~85% | $0.001 |
| Gemini 3.5 Flash-Lite만 | 70% | 60~78% | 무료 등급 |

McNemar (같은 곳에서 한쪽만 맞힌 수): Claude만 vs 규칙만 12 / 2 (p=0.013), Claude만 vs Gemini만 20 / 2 (p<0.001)

- 규칙은 개발용 100% → 시험용 78%. 개발용에 없던 표현(일부 통제, 유동적, 매표 마감, 둘째주)을 놓쳤다
- 규칙 + LLM 은 규칙이 확신 없다고 한 5곳만 LLM 에 넘겨서 거의 차이가 없었다. 틀린 곳 대부분은 규칙이 확신하면서 틀렸다
- 규칙 오류 22곳 중 7곳은 오름의 "통제될 수 있으므로 전화문의" 를 안내(변동 가능)로 본 라벨 기준 때문
- 정답 초안을 LLM 이 만들어서 LLM 쪽이 조금 유리할 수 있다. 다만 같은 LLM 끼리도 Claude 와 Gemini 가 18%p 차이 났다

결론: 운영은 Claude Haiku 5.5. 규칙 파서는 검증과 API 장애 때 대체용으로 둔다.
