#!/usr/bin/env bash
#
# 이 프로젝트 전용 .venv를 만들고 검증된 고정 버전 의존성을 설치한다.
#
# 실행 스크립트는 준비된 가상환경을 사용하므로, 이 파일이 최초 설치를 담당한다.
# 깨끗한 환경에서 이 폴더를 처음 받았다면(학생 배포 등) 가장 먼저 이걸 실행한다.
#
# ⚠️ 이 머신은 plain python3/pip가 alias로 엉뚱한 경로를 가리켜, venv를 만들어도
# 그 안에 설치되는 게 아니라 시스템 전역에 설치돼버리는 경우가 실제로 있었다.
# 그래서 설치 단계는 반드시 "activate" 대신 .venv 안의 python3 바이너리를
# 절대/상대 경로로 직접 호출한다(아래 ./.venv/bin/python3 -m pip ...).
#
# 실행:
#   bash sh/setup_venv.sh
#
set -euo pipefail
cd "$(dirname "$0")/.."

command -v python3 >/dev/null 2>&1 \
    || { echo "ERROR: python3가 설치되어 있지 않습니다."; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
    || { echo "ERROR: Python 3.11 이상이 필요합니다. README의 uv 설치 방법을 참고하세요."; exit 1; }

# ── 1) .venv 생성 (이미 있으면 건너뜀) ──────────────────────────────────
if [ -x ".venv/bin/python3" ]; then
    echo ".venv가 이미 있습니다 — 생성은 건너뛰고 설치만 다시 확인합니다."
else
    echo "python3 -m venv .venv 로 가상환경을 새로 만듭니다..."
    python3 -m venv .venv
fi

# ── 2) 의존성 설치 — activate 대신 .venv의 python3를 직접 호출 ─────────
#    (plain pip/python3가 alias로 다른 경로를 가리키는 머신에서도 항상
#     .venv 안에 정확히 설치되도록 보장한다)
echo "requirements-lock.txt 설치 중..."
./.venv/bin/python3 -m pip --version >/dev/null 2>&1 || ./.venv/bin/python3 -m ensurepip --upgrade
./.venv/bin/python3 -m pip install -r requirements-lock.txt

echo
echo "설치 확인:"
./.venv/bin/python3 -c "import fastapi, uvicorn, langgraph, langsmith, fastmcp, mcp, httpx, dotenv; print('  필요 패키지 전부 import 성공')"

cat <<EOF

################################################################
 .venv 준비 완료
################################################################

별도 터미널에서 Ollama를 실행하고 설치된 모델을 확인하세요:
  ollama serve
  ollama list

실제 로컬 모델 실행:
  .venv/bin/python sh/run_demo.py --backend ollama

모델 없이 재작성 흐름만 시연:
  .venv/bin/python sh/run_demo.py --backend fake

접속: http://127.0.0.1:8610
EOF
