import unittest
from agent.deps import SupervisorDeps
from agent.fake_llm import FastLLM, QualityLLM
from agent.graph import build_graph
from agent.validation import demo_answer
from eval.cases import record


class LocalMCP:
    """그래프 동작만 분리해서 시험하는 테스트 대역. 실제 MCP는 smoke에서 확인한다."""
    async def find_prompt(self, name):
        return 'ops'

    async def get_prompt(self, *args, **kwargs):
        return '상태와 매뉴얼을 조사하세요.'

    async def call_tool(self, name, arguments):
        return record(arguments['system_name'])['data']

    async def find_resource_template(self, name):
        return 'ops', 'runbook://incident-response/{incident_type}'

    async def read_resource(self, *args, **kwargs):
        return '# 점검 매뉴얼\n1. 로그를 확인하세요.\n2. 담당자와 원인을 조사하세요.'


class AlwaysWrong(QualityLLM):
    async def write(self, query, collected, attempt, feedback, on_token=None):
        draft = demo_answer(collected).replace('CPU=78.0%', 'CPU=9.0%')
        return draft, {'usd': 0.0}


def graph(quality):
    deps = SupervisorDeps(FastLLM('fake-fast', 0), quality, LocalMCP(), None, 'v2')
    return build_graph(deps)


class GraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_incorrect_number_is_rewritten_with_feedback(self):
        result = await graph(QualityLLM('fake-quality', 0)).ainvoke(
            {'query': 'auth-service 장애 진단', 'thread_id': 'test', 'events': []})
        self.assertEqual(result['validation_status'], 'passed')
        self.assertEqual(result['validation_attempts'], 2)
        self.assertFalse(result['validation_history'][0]['report']['passed'])
        self.assertEqual(result['validation_history'][0]['report']['issues'][0]['code'], 'metric_mismatch')
        self.assertIn('CPU=78.0%', result['final'])
        self.assertNotIn('CPU=88.0%', result['final'])

    async def test_three_failures_are_blocked_not_approved(self):
        result = await graph(AlwaysWrong('wrong', 0)).ainvoke(
            {'query': 'auth-service 장애 진단', 'thread_id': 'test', 'events': []})
        self.assertEqual(result['validation_status'], 'blocked')
        self.assertEqual(result['validation_attempts'], 3)
        self.assertFalse(result['validation_report']['passed'])
        self.assertIn('검증 보류', result['final'])
        self.assertNotIn('CPU=9.0%', result['final'])

    async def test_incident_stream_never_exposes_unvalidated_draft(self):
        updates = []
        async for mode, payload in graph(QualityLLM('fake-quality', 0)).astream(
                {'query': 'auth-service 장애 진단', 'events': [], 'thread_id': 'test'},
                stream_mode=['updates', 'custom']):
            updates.append((mode, payload))
        self.assertFalse(any(mode == 'custom' and p.get('type') == 'AnswerToken' for mode, p in updates))
        self.assertTrue(any(mode == 'updates' and 'finalize' in p for mode, p in updates))

    async def test_chat_remains_outside_incident_validation(self):
        result = await graph(QualityLLM('fake-quality', 0)).ainvoke(
            {'query': '안녕하세요', 'thread_id': 'test', 'events': []})
        self.assertEqual(result['route'], 'chat')
        self.assertNotIn('validation_report', result)


if __name__ == '__main__':
    unittest.main()
