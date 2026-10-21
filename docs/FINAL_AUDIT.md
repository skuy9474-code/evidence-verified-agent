# 설계 대비 최종 검수표

기준: [Day1 계획](DAY1_PLAN.md)의 핵심 개선 목표 5개. 검수일: 2026-10-21.

| 설계 요구사항 | 구현 위치 | 확인 근거 | 판정 |
|---|---|---|---|
| 시스템별 상태·CPU·메모리 일치 | agent/validation.py | 수치·상태·시스템 간 값 교환 및 잘못된 원본 테스트 | 완료 |
| 조회 시스템 누락·추가·중복 | agent/validation.py | missing/unsupported/duplicate 사례·단위 테스트 | 완료 |
| 미확인 값을 측정값과 구분 | agent/answer_schema.py, validation.py | unknown null·0% 거절·billing-service 실제 조회 | 완료 |
| 근거·원인 가설·권장 조치·한계 | agent/answer_schema.py, validation.py | 잘못된 JSON·필드 누락·빈 항목 테스트 | 완료 |
| 구체적 오류 피드백 후 재작성 | agent/graph.py | 1차 수치 오류 반려→2차 통과, 별도 실제 모델 재작성 기록 | 완료 |
| 총 3회 실패 시 보류 | agent/graph.py | AlwaysWrong 그래프·ASGI SSE 테스트 | 완료 |
| 검증 전 진단 초안 비노출 | graph.py, server.py | 그래프 custom 이벤트 및 HTTP SSE의 AnswerToken 부재 | 완료 |
| 검증 사유·최종 결과 화면 | web_chat.html | 실제 브라우저 조작과 최종 화면 캡처 | 완료 |
| 동일 사례 Before/After | eval/run_eval.py | reports/evaluation.json·csv·md 23개 동일 입력 | 완료 |
| 실제 모델 횟수·전체 시간 | eval/run_real_eval.py | 6개 요청, 평균 10.265초·작성 1.0회 | 완료 |
| 모델·조회 실패를 성공과 구분 | server.py, web_chat.html | ASGI 503·SSE Error·성공 저장 없음 | 완료 |
| 실행·제출 안내 | README.md, docs/FINAL_REPORT.md | 실행 서버 확인·셸 문법 검사·Git 주소 준비 | 완료 |

## 이번 수정으로 추가한 회귀 검사

- 같은 줄의 잘못된 현재값이 올바른 조건문 때문에 통과하지 않는지
- CPU 임계값을 메모리 임계값으로 잘못 쓰거나 비교 조건을 바꾸면 거절하는지
- 근거 행과 본문의 명시적 상태가 다르면 거절하는지
- 여러 시스템 중 어느 상태인지 불명확하면 보류하는지
- POST와 SSE 모두 빈 질문·너무 긴 질문을 거절하는지
- 서버 처리 실패 시 최종 답변을 만들지 않고 오류로 종료하는지
- 보류된 초안이 HTTP 최종 답변·SSE 토큰으로 노출되지 않는지

33개 테스트와 실제 모델·MCP 실행은 에이전트가 실행한 검수다. 사용자가 직접 터미널 명령을 완료했다는 의미는 아니다. 모든 자연어를 이해하는 검증기나 운영 수준의 품질 보증이라는 뜻도 아니다.

## 범위 밖 또는 미실행

| 항목 | 상태 |
|---|---|
| 원인·조치 전체의 사실성 검증, 시스템별 RAG | 이번 설계 범위 밖 |
| 실제 서버 모니터링·자동 복구 | 샘플 조회·권장 안내만 구현 |
| 실제 OpenAI API 속도·비용 비교 | 키 없이 미실행 |
| 신규 기기 설치·장시간 부하·동시 사용자 성능 | 미실행 |
| Google 스프레드시트 최종 등록·제출 | 등록용 내용·주소 준비, 직접 제출은 미실행 |

세부 결과와 해석: [최종 결과 보고서](FINAL_REPORT.md).
