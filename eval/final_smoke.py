"""실행 중인 최종 Ollama 서버에 수업식 질문·SSE·대화 기억을 확인한다.

사용: python -m eval.final_smoke --base-url http://127.0.0.1:8610
샘플 데이터에 대한 통합 확인이며 의미 전체나 운영 정확도 평가는 아니다.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8610')
    args = parser.parse_args()
    cases = []
    run = 'final-' + uuid4().hex[:10]
    with httpx.Client(base_url=args.base_url, timeout=180) as client:
        health = client.get('/health').json()
        assert health['llm_backend'] == 'ollama', '실제 Ollama 모드에서 실행하세요.'

        def check(name, fn):
            start = perf_counter()
            try:
                details = fn()
                row = {'case': name, 'passed': True, 'details': details}
            except Exception as exc:
                row = {'case': name, 'passed': False, 'error_type': type(exc).__name__, 'error': str(exc)}
            row['seconds'] = round(perf_counter() - start, 3)
            cases.append(row)
            print(json.dumps({k: row[k] for k in ('case', 'passed', 'seconds')}, ensure_ascii=False), flush=True)

        def incident(query, targets):
            response = client.post('/chat', json={'message': query, 'thread_id': run})
            response.raise_for_status()
            data = response.json()
            meta = data['metadata']
            assert meta['route'] == 'incident', data
            assert meta['validation_status'] == 'passed', data
            assert 1 <= meta['validation_attempts'] <= 3
            assert {d['system_name'] for d in meta['monitoring_evidence']} == set(targets), data
            if targets == ['billing-service']:
                assert 'billing-service | 상태=unknown | CPU=미확인 | 메모리=미확인' in data['reply']
            return {'query': query, **data}

        for query, targets in [
            ('로그인 응답이 느려요, 원인 확인해주세요', ['auth-service']),
            ('billing-service 응답이 느려요', ['billing-service']),
            ('payments-service랑 cache-service 둘 다 저하됐는데 공통 원인이 있는지 분석해줘', ['payments-service', 'cache-service']),
            ('web-01 CPU 급증, auth-service 커넥션 풀도 같이 확인해줘', ['web-01', 'auth-service']),
        ]:
            check(query, lambda q=query, t=targets: incident(q, t))

        def stream():
            response = client.get('/chat/stream', params={'message': 'auth-service 장애 진단', 'thread_id': run+'-sse'})
            response.raise_for_status()
            events = [json.loads(line[6:]) for line in response.text.splitlines()
                      if line.startswith('data: ') and line != 'data: [DONE]']
            assert not any(e['type'] == 'AnswerToken' for e in events)
            finals = [e for e in events if e['type'] == 'FinalAnswer']
            assert len(finals) == 1 and finals[0]['validation_status'] == 'passed', events
            assert response.text.endswith('data: [DONE]\n\n')
            return {'events': events}
        check('SSE: 검증 전 초안 비노출·최종 답변 1회·정상 종료', stream)

        def memory():
            replies = []
            for query in ('제 이름은 민수입니다', '제 이름이 뭐였죠?'):
                response = client.post('/chat', json={'message': query, 'thread_id': run+'-memory'})
                response.raise_for_status()
                data = response.json()
                assert data['metadata']['validation_status'] == 'not_applicable'
                replies.append(data['reply'])
            assert '민수' in replies[-1], replies
            return {'replies': replies, 'note': '민수는 대화 기억 확인용 가상 이름'}
        check('일반 대화: 같은 세션 이름 기억', memory)
        final_health = client.get('/health').json()
        assert final_health['instance_id'] == health['instance_id']

    result = {'run_utc': datetime.now(timezone.utc).isoformat(),
              'model': health['quality_llm'], 'count': len(cases),
              'passed': sum(c['passed'] for c in cases),
              'same_agent_instance': True, 'cases': cases}
    target = Path(__file__).resolve().parents[1] / 'reports' / 'final_http_audit.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    if result['passed'] != result['count']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
