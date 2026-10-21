"""실제 ASGI 요청 경계 검증. 외부 모델·MCP·파일 DB를 쓰지 않는다."""
import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import httpx
from starlette.datastructures import State
import server
from agent.deps import SupervisorDeps
from agent.fake_llm import FastLLM, QualityLLM
from agent.graph import build_graph
from test_graph import LocalMCP, AlwaysWrong


class MemoryStore:
    def __init__(self):
        self.messages = {}

    def load(self, thread):
        return self.messages.get(thread, [])

    def append(self, thread, role, content):
        self.messages.setdefault(thread, []).append({'role': role, 'content': content})


class BrokenGraph:
    async def ainvoke(self, *args, **kwargs):
        raise RuntimeError('private-provider-detail-that-must-not-be-returned')

    async def astream(self, *args, **kwargs):
        raise RuntimeError('private-provider-detail-that-must-not-be-returned')
        yield  # async generator interface


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.state_patch = patch.object(server.app, 'state', State())
        self.state_patch.start()
        self.store = MemoryStore()
        self.deps = SupervisorDeps(FastLLM('test-fast', 0), QualityLLM('test-quality', 0),
                                   LocalMCP(), self.store, 'v2')
        server.app.state.deps = self.deps
        server.app.state.graph = build_graph(self.deps)
        server.app.state.instance_id = 1
        server.app.state.llm_backend = 'fake'
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url='http://test')

    async def asyncTearDown(self):
        await self.client.aclose()
        self.state_patch.stop()

    async def test_post_returns_validated_result_and_same_request_evidence(self):
        response = await self.client.post('/chat', json={'message': 'auth-service 장애 진단', 'thread_id': 'api'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['metadata']['validation_status'], 'passed')
        self.assertEqual(data['metadata']['validation_attempts'], 2)
        self.assertTrue(data['metadata']['monitoring_evidence'])
        self.assertEqual(len(self.store.load('api')), 2)

    async def test_sse_blocked_result_never_exposes_failed_draft(self):
        deps = SimpleNamespace(**vars(self.deps))
        deps.quality_llm = AlwaysWrong('test-wrong', 0)
        server.app.state.graph = build_graph(deps)
        response = await self.client.get('/chat/stream', params={'message': 'auth-service 장애 진단'})
        events = [json.loads(line[6:]) for line in response.text.splitlines()
                  if line.startswith('data: ') and line != 'data: [DONE]']
        self.assertFalse(any(e['type'] == 'AnswerToken' for e in events))
        self.assertEqual([e['status'] for e in events if e['type'] == 'Validation'],
                         ['retrying', 'retrying', 'blocked'])
        final = next(e for e in events if e['type'] == 'FinalAnswer')
        self.assertEqual(final['validation_status'], 'blocked')
        self.assertNotIn('CPU=9.0%', final['reply'])
        self.assertIn('검증 보류', final['reply'])
        self.assertTrue(response.text.endswith('data: [DONE]\n\n'))

    async def test_post_processing_failure_is_explicit_and_does_not_save_success(self):
        server.app.state.graph = BrokenGraph()
        response = await self.client.post('/chat', json={'message': '장애 진단', 'thread_id': 'failure'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error']['code'], 'processing_unavailable')
        self.assertNotIn('private-provider-detail', response.text)
        self.assertFalse(self.store.load('failure'))

    async def test_sse_processing_failure_has_error_and_done_without_final_answer(self):
        server.app.state.graph = BrokenGraph()
        response = await self.client.get('/chat/stream', params={'message': '장애 진단'})
        self.assertIn('"type": "Error"', response.text)
        self.assertNotIn('FinalAnswer', response.text)
        self.assertNotIn('private-provider-detail', response.text)
        self.assertTrue(response.text.endswith('data: [DONE]\n\n'))

    async def test_empty_or_oversized_questions_rejected_on_both_routes(self):
        for message in ('', '   ', 'x' * 4001):
            with self.subTest(message_length=len(message)):
                post = await self.client.post('/chat', json={'message': message})
                stream = await self.client.get('/chat/stream', params={'message': message})
                self.assertEqual(post.status_code, 422)
                self.assertEqual(stream.status_code, 422)


if __name__ == '__main__':
    unittest.main()
