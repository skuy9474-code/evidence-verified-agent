"""실행 중인 로컬 데모의 실제 FastAPI→LangGraph→MCP 경로 확인."""
import json
import os
from pathlib import Path
import httpx


def main():
    url = os.environ.get('DEMO_URL', 'http://127.0.0.1:8610')
    outputs = []
    with httpx.Client(timeout=60) as client:
        h = client.get(url+'/health')
        h.raise_for_status()
        assert h.json()['llm_backend'] == 'fake', '이 검증은 fake 데모 전용입니다.'
        for query in ['auth-service 장애 진단', 'payments-service와 cache-service 장애 진단',
                      'billing-service 장애 진단']:
            r = client.post(url+'/chat', json={'message': query, 'thread_id': 'http-smoke'})
            r.raise_for_status()
            data = r.json()
            assert data['metadata']['validation_status'] == 'passed', data
            assert data['metadata']['validation_report']['passed']
            if 'billing' in query:
                assert 'billing-service | 상태=unknown | CPU=미확인' in data['reply']
            else:
                assert data['metadata']['validation_attempts'] == 2
                first = next(e for e in data['events'] if e['type'] == 'Validation')
                assert first['status'] == 'retrying'
            outputs.append({'query': query, 'reply': data['reply'], 'metadata': data['metadata']})

        with client.stream('GET', url+'/chat/stream', params={'message': 'auth-service 장애 진단',
                                                              'thread_id': 'stream-smoke'}) as r:
            r.raise_for_status()
            events = [json.loads(line[6:]) for line in r.iter_lines()
                      if line.startswith('data: ') and line != 'data: [DONE]']
        assert not any(e['type'] == 'AnswerToken' for e in events), '검증 전 초안 유출'
        final = next(e for e in events if e['type'] == 'FinalAnswer')
        assert final['validation_status'] == 'passed'
        assert [e['status'] for e in events if e['type'] == 'Validation'] == ['retrying', 'passed']
        outputs.append({'stream_event_types': [e['type'] for e in events], 'final': final})

        r = client.post(url+'/chat', json={'message': '안녕하세요', 'thread_id': 'chat-smoke'})
        r.raise_for_status()
        assert r.json()['metadata']['validation_status'] == 'not_applicable'
    path = Path(__file__).resolve().parents[1]/'reports/http_smoke.json'
    path.write_text(json.dumps(outputs, ensure_ascii=False, indent=2))
    print('실제 MCP 연결 + 단일/복수/미등록 시스템 + SSE 초안 비노출 + 일반 대화: 통과')


if __name__ == '__main__':
    main()
