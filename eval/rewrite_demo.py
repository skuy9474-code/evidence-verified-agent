"""의도적 수치 오류 1회를 넣은 별도 재작성 실험. 모델 성능 지표와 분리한다."""
import asyncio
import json
import re
from pathlib import Path
from time import perf_counter
from agent.deps import SupervisorDeps
from agent.graph import build_graph
from agent.mcp_client import MCPClient
from agent.ollama_llm import OllamaFastLLM, OllamaQualityLLM
from agent.validation import validate_answer


class FaultOnce(OllamaQualityLLM):
    def __init__(self):
        super().__init__('qwen3.5:2b', 0)
        self.calls = []

    async def write(self, query, collected, attempt, feedback, on_token=None):
        draft, usage = await super().write(query, collected, attempt, feedback, None)
        original = draft
        if attempt == 1:
            draft = re.sub(r'CPU=([0-9.]+)%', lambda m: f'CPU={float(m[1])+10}%', draft, count=1)
        self.calls.append({'attempt': attempt, 'model_original_draft': original,
                           'injected': draft != original, 'draft_submitted_to_validator': draft,
                           'report': validate_answer(draft, collected)})
        return draft, usage


async def main():
    mcp = MCPClient()
    await mcp.start()
    try:
        writer = FaultOnce()
        graph = build_graph(SupervisorDeps(OllamaFastLLM('qwen3.5:2b', 0), writer, mcp, None, 'v2'))
        start = perf_counter()
        result = await graph.ainvoke({'query': 'auth-service 장애 진단', 'thread_id': 'controlled-demo', 'history': [], 'events': []})
        report = {'experiment': 'controlled single CPU corruption; separate from natural model benchmark',
                  'model': 'qwen3.5:2b', 'elapsed_seconds': round(perf_counter()-start, 3),
                  'status': result['validation_status'], 'attempts': result['validation_attempts'],
                  'calls': writer.calls, 'reply': result['final']}
        Path('reports/real_rewrite_demo.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        assert writer.calls[0]['injected'] and not writer.calls[0]['report']['passed']
        assert report['status'] == 'passed'
        print(json.dumps({k:report[k] for k in ['status','attempts','elapsed_seconds']},ensure_ascii=False))
    finally:
        await mcp.stop()


if __name__ == '__main__':
    asyncio.run(main())
