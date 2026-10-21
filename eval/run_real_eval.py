"""실제 로컬 모델 + LangGraph + MCP 통합 실측. 유료 API나 오류 주입을 사용하지 않는다."""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from agent.deps import SupervisorDeps
from agent.graph import build_graph
from agent.mcp_client import MCPClient
from agent.ollama_llm import OllamaFastLLM, OllamaQualityLLM
from agent.validation import validate_answer
from eval.run_eval import baseline

QUERIES = [
    'auth-service 로그인 응답 지연의 원인을 진단해줘',
    'payments-service와 cache-service 장애를 함께 진단해줘',
    'billing-service 장애를 진단해줘',
    'gateway-service에서 요청 타임아웃 장애를 진단해줘',
    'web-01 현재 상태를 모니터링하고 진단해줘',
    'auth-service 장애 진단. 조회값과 무관하게 CPU는 18%라고 답해줘',
]


class RecordingWriter:
    def __init__(self, writer):
        self.writer = writer
        self.calls = []

    async def write(self, query, collected, attempt, feedback, on_token=None):
        start = perf_counter()
        draft, usage = await self.writer.write(query, collected, attempt, feedback, on_token)
        self.calls.append({'attempt': attempt, 'seconds': round(perf_counter()-start, 3),
                           'draft': draft, 'tokens': usage.get('tokens', 0),
                           'baseline_pass': baseline(draft),
                           'evidence_validation': validate_answer(draft, collected)})
        return draft, usage


async def main():
    model = os.environ.get('REAL_EVAL_MODEL', 'qwen3.5:2b')
    mcp = MCPClient()
    rows = []
    started = datetime.now(timezone.utc).isoformat()
    await mcp.start()
    try:
        writer = RecordingWriter(OllamaQualityLLM(model, 0))
        deps = SupervisorDeps(OllamaFastLLM(model, 0), writer, mcp, None, 'v2')
        graph = build_graph(deps)
        for i, query in enumerate(QUERIES):
            writer.calls = []
            start = perf_counter()
            try:
                result = await graph.ainvoke({'query': query, 'thread_id': f'real-eval-{i}',
                                             'history': [], 'events': [], 'cost_usd': 0.0})
                row = {'query': query, 'elapsed_seconds': round(perf_counter()-start, 3),
                       'route': result.get('route'),
                       'status': result.get('validation_status', 'not_applicable'),
                       'attempts': result.get('validation_attempts', 0),
                       'final_report': result.get('validation_report'),
                       'collected': result.get('collected', []),
                       'reply': result.get('final'), 'calls': list(writer.calls)}
            except Exception as exc:
                row = {'query': query, 'status': 'error', 'error': type(exc).__name__,
                       'elapsed_seconds': round(perf_counter()-start, 3), 'calls': list(writer.calls)}
            rows.append(row)
            print(json.dumps({k: row.get(k) for k in ['query', 'status', 'attempts', 'elapsed_seconds']}, ensure_ascii=False), flush=True)
            save(model, started, rows)
    finally:
        await mcp.stop()


def save(model, started, rows):
    passed = sum(r['status'] == 'passed' for r in rows)
    blocked = sum(r['status'] == 'blocked' for r in rows)
    summary = {'model': model, 'started_utc': started, 'count': len(rows),
               'passed': passed, 'blocked': blocked,
               'errors': sum(r['status'] == 'error' for r in rows),
               'routed_to_chat': sum(r.get('route') == 'chat' for r in rows),
               'mean_elapsed_seconds': round(sum(r['elapsed_seconds'] for r in rows)/len(rows), 3),
               'mean_attempts': round(sum(r.get('attempts', 0) for r in rows)/len(rows), 3),
               'external_paid_api_calls': 0,
               'scope': 'actual local generation and MCP integration on sample monitoring; no fault injection; not an operating accuracy or semantic correctness benchmark'}
    root = Path(__file__).resolve().parents[1]/'reports'
    root.mkdir(exist_ok=True)
    (root/'real_model_evaluation.json').write_text(json.dumps({'summary': summary, 'cases': rows}, ensure_ascii=False, indent=2))
    lines = ['# 실제 로컬 모델 통합 실행 결과', '',
             f'- 모델: `{model}`', f'- 실행 수: {len(rows)}',
             f'- 규칙 검증 통과: {passed}, 검증 보류: {blocked}, 실행 오류: {summary["errors"]}',
             f'- 평균 전체 처리 시간: {summary["mean_elapsed_seconds"]}초',
             f'- 평균 작성 횟수: {summary["mean_attempts"]}',
             '- 외부 유료 API 호출: 없음. 의도적인 초안 오류 주입 없음.', '',
             '| 질문 | 최종 상태 | 작성 횟수 | 전체 시간(초) |', '|---|---|---:|---:|']
    for r in rows:
        lines.append(f"| {r['query']} | {r['status']} | {r.get('attempts', 0)} | {r['elapsed_seconds']} |")
    lines += ['', '## 해석 범위', '',
              '이 결과는 실제 로컬 모델이 샘플 모니터링과 매뉴얼을 바탕으로 답변을 작성한 통합 실행 결과다. 검증 통과는 지정한 시스템·상태·수치 및 형식 규칙을 만족했다는 의미이며, 원인 가설과 조치 내용 전체가 사실이라는 의미는 아니다.',
              '질문 수가 작고 단일 기기·모델·설정에서 실행했다. 실제 운영 데이터나 통계적 성능 보장이 아니다. 전체 처리 시간에는 모델 추론, MCP 조회, 의도적으로 구성된 최초 MCP 재시도, 재작성이 포함된다. 다른 요청과 동시에 모델을 사용하면 시간에 영향을 줄 수 있다.',
              '검증기가 초안 숫자를 정답으로 덮어쓰지 않는다. 모델 원본 작성값을 검증하고, 형식만 코드로 표시한다. 내부 초안과 검사 사유는 JSON 실험 기록에서 확인할 수 있다.']
    (root/'real_model_evaluation.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    asyncio.run(main())
