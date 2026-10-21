"""전용 가상환경에서 실행: .venv/bin/python sh/run_demo.py

API 키 없는 fake/Ollama 실행. 기존 프로세스나 대화 DB를 삭제하지 않는다.
"""
import os
import argparse
import json
import errno
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description='로컬 장애 진단 에이전트 실행')
    parser.add_argument('--backend', choices=['fake', 'ollama'], default='fake')
    parser.add_argument('--model', default='qwen3.5:2b')
    parser.add_argument('--backend-port', type=int, default=int(os.environ.get('DEMO_BACKEND_PORT', '8110')))
    parser.add_argument('--frontend-port', type=int, default=int(os.environ.get('DEMO_FRONTEND_PORT', '8610')))
    args = parser.parse_args()
    backend_port, frontend_port = args.backend_port, args.frontend_port
    if args.backend == 'ollama':
        base = os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
        try:
            with urlopen(base+'/api/tags', timeout=3) as response:
                installed = {m['name'] for m in json.load(response).get('models', [])}
        except Exception:
            raise SystemExit('Ollama에 연결하지 못했습니다. 별도 터미널에서 ollama serve를 실행하세요.')
        if args.model not in installed:
            raise SystemExit(f'{args.model} 모델이 없습니다. ollama list로 설치된 이름을 확인하세요.')
    if backend_port == frontend_port:
        raise SystemExit('백엔드와 화면 포트는 서로 달라야 합니다.')
    for port in (backend_port, frontend_port):
        try:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', port))
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                raise SystemExit(f'{port}번 포트가 사용 중입니다. 기존 프로그램을 종료하거나 DEMO_*_PORT를 바꾸세요.')
            raise SystemExit(f'{port}번 포트를 열 수 없습니다: {exc}')

    env = {**os.environ, 'LLM_BACKEND': args.backend,
           'OLLAMA_FAST_MODEL': args.model, 'OLLAMA_QUALITY_MODEL': args.model, 'SUPERVISOR_VERSION': 'v2',
           'LANGCHAIN_TRACING_V2': 'false', 'LANGSMITH_TRACING': 'false',
           'AGENT_BACKEND_URL': f'http://127.0.0.1:{backend_port}'}
    processes = []

    def stop(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        for module, port in [('server', backend_port), ('web_demo_server', frontend_port)]:
            processes.append(subprocess.Popen(
                [sys.executable, '-m', 'uvicorn', f'{module}:app', '--host', '127.0.0.1',
                 '--port', str(port), '--log-level', 'warning'], cwd=ROOT, env=env))
            for _ in range(120):
                if any(p.poll() is not None for p in processes):
                    raise RuntimeError('서버가 종료되었습니다. 위 오류 메시지를 확인하세요.')
                try:
                    with urlopen(f'http://127.0.0.1:{port}/health', timeout=1) as r:
                        if r.status == 200:
                            break
                except Exception:
                    time.sleep(0.25)
            else:
                raise RuntimeError('서버 준비 시간을 초과했습니다.')
        print(f'화면: http://127.0.0.1:{frontend_port}', flush=True)
        print('fake: 의도적인 오류 주입 시뮬레이션' if args.backend == 'fake' else f'실제 로컬 모델: {args.model} (외부 API 호출 없음)', flush=True)
        print('종료: Ctrl+C. 이 실행에서 시작한 서버만 종료합니다.', flush=True)
        while all(p.poll() is None for p in processes):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
        for p in reversed(processes):
            try:
                p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()


if __name__ == '__main__':
    main()
