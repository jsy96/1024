#!/bin/bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")" && pwd)"
cd "$project_dir"
python3 -c 'import sys; assert sys.version_info >= (3,9), "需要 Python 3.9 或更新版本"'
if [ ! -x .venv-mac/bin/python ]; then python3 -m venv .venv-mac; fi
if ! .venv-mac/bin/python -c 'import flask,requests,PIL' >/dev/null 2>&1; then
  .venv-mac/bin/python -m pip install -r requirements.txt
fi
export CARE_DB="$project_dir/data/care-mac-demo.db"
export TZ=Asia/Shanghai
exec .venv-mac/bin/python server.py
