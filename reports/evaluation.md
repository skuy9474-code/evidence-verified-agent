# 검증기 Before / After 실험

고정 합성 답변 23개를 동일하게 입력했습니다. 실제 LLM 생성 품질이나 운영 정확도 결과가 아닙니다.

| 지표 | 기존 | 개선 |
|---|---:|---:|
| 잘못된 답변 탐지 | 1 | 17 |
| 오류 답변 통과 | 16 | 0 |
| 정확한 답변 보류 | 0 | 1 |
| 오류 탐지율 | 5.9% | 100.0% |
| 정답 보류율 | 0.0% | 16.7% |

## 실험 범위와 한계

- 정답 6개, 오류 17개인 소규모 수동 합성 사례입니다. 검증 규칙을 알고 만든 사례라 일반화 성능으로 해석할 수 없습니다.
- 정확한 자유형 답변 1개도 정형 출력 계약에 맞지 않아 개선본에서 보류됩니다. 형식 제약의 비용입니다.
- 기존 검증의 3회 후 강제 통과는 단일 답변 비교에서 제외했습니다. 그래프 테스트에서 별도로 확인합니다.
- 지연은 함수만 측정한 로컬 평균입니다. 모델 호출, MCP, 재작성, 네트워크 지연은 포함하지 않습니다.
- 현재는 규칙 검증입니다. 원인·조치의 의미적 정확성 전체, 매뉴얼 내용의 신뢰성, 실제 서버 상태를 보증하지 않습니다.

## 사례별 결과

| 사례 | 기대 | 기존 | 개선 | 사유 |
|---|---|---|---|---|
| correct_single | 통과 | 통과 | 통과 | - |
| correct_multi | 통과 | 통과 | 통과 | - |
| equivalent_decimal | 통과 | 통과 | 통과 | - |
| correct_unknown | 통과 | 통과 | 통과 | - |
| correct_healthy | 통과 | 통과 | 통과 | - |
| wrong_cpu | 보류 | 통과 | 보류 | metric_mismatch |
| wrong_memory | 보류 | 통과 | 보류 | metric_mismatch |
| wrong_status | 보류 | 통과 | 보류 | status_mismatch |
| swapped_system_values | 보류 | 통과 | 보류 | metric_mismatch, metric_mismatch |
| invented_system | 보류 | 통과 | 보류 | unsupported_system, missing_system |
| missing_system | 보류 | 통과 | 보류 | missing_system |
| duplicate_system | 보류 | 통과 | 보류 | duplicate_system |
| missing_actions | 보류 | 통과 | 보류 | missing_section, section_order |
| empty_limits | 보류 | 통과 | 보류 | missing_section |
| unknown_as_zero | 보류 | 통과 | 보류 | unknown_measurement |
| extra_narrative_number | 보류 | 통과 | 보류 | metric_mismatch |
| normality_contradiction | 보류 | 통과 | 보류 | unsupported_healthy_claim |
| confident_cause | 보류 | 통과 | 보류 | unqualified_cause |
| no_source | 보류 | 통과 | 보류 | missing_evidence, unsupported_system |
| bad_row_format | 보류 | 통과 | 보류 | unparseable_evidence, missing_system |
| infinite_number | 보류 | 통과 | 보류 | unparseable_evidence, missing_system |
| short_draft | 보류 | 보류 | 보류 | unexpected_text, missing_section, missing_section, missing_section, missing_section, section_order, missing_system |
| legacy_correct_content | 통과 | 통과 | 보류 | unexpected_text, missing_section, missing_section, missing_section, missing_section, section_order, missing_system |
