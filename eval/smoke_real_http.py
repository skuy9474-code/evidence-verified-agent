"""실행 중인 Ollama 모드의 HTTP와 SSE를 점검한다. 결과는 통합 평가와 분리한다."""
import json
from pathlib import Path
import httpx


def main():
    root = 'http://127.0.0.1:8610'
    records = []
    with httpx.Client(timeout=180) as client:
        health = client.get(root+'/health')
        health.raise_for_status()
        assert health.json()['llm_backend'] == 'ollama'
        for query in ['auth-service 장애 진단', 'billing-service 장애 진단']:
            result = client.post(root+'/chat', json={'message': query, 'thread_id': 'real-http'})
            result.raise_for_status()
            data = result.json()
            assert data['metadata']['validation_status'] == 'passed', data
            assert data['metadata']['monitoring_evidence']
            if 'billing' in query:
                assert 'billing-service | 상태=unknown | CPU=미확인' in data['reply']
            records.append(data)
        with client.stream('GET', root+'/chat/stream', params={'message':'web-01 장애 진단', 'thread_id':'real-sse'}) as response:
            response.raise_for_status()
            events = [json.loads(line[6:]) for line in response.iter_lines()
                      if line.startswith('data: ') and line != 'data: [DONE]']
        assert not any(e['type'] == 'AnswerToken' for e in events)
        final = next(e for e in events if e['type'] == 'FinalAnswer')
        assert final['validation_status'] == 'passed'
        records.append({'events':events})
        hello = client.post(root+'/chat', json={'message':'안녕하세요', 'thread_id':'real-hello'})
        hello.raise_for_status()
        assert hello.json()['metadata']['validation_status'] == 'not_applicable'
    Path('reports/real_http_smoke.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
    print('실제 모델 HTTP·미등록 시스템·SSE 초안 비노출·일반 대화: 통과')


if __name__ == '__main__':
    main()
