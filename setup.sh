#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ "$(uname -s)" != Linux ]]; then
  echo 'This renderer currently requires Linux. Native macOS/Windows rendering is not supported.' >&2
  exit 1
fi
for tool in git node npm ffmpeg ffprobe espeak-ng bwrap; do
  command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool. See README.md." >&2; exit 1; }
done
node -e 'if(Number(process.versions.node.split(".")[0])<22) process.exit(1)' || { echo 'Node 22+ required.' >&2; exit 1; }
if [[ ! -x .venv/bin/python ]]; then
  if command -v uv >/dev/null; then
    uv venv --seed --python 3.11 .venv
  else
    "${PYTHON_BIN:-python3.11}" -m venv .venv
  fi
fi
if command -v uv >/dev/null; then
  uv pip install --python .venv/bin/python -r requirements.lock.txt
  uv pip install --python .venv/bin/python --no-deps -e .
else
  .venv/bin/python -m pip install -r requirements.lock.txt
  .venv/bin/python -m pip install --no-deps -e .
fi
npm ci --ignore-scripts --no-audit --no-fund
npm run build
.venv/bin/python scripts/bootstrap_sources.py
.venv/bin/python - <<'PY'
from studio.diagnostics import doctor
import json
result = doctor()
print(json.dumps(result, ensure_ascii=False, indent=2))
if not result['ready']:
    raise SystemExit('Install missing prerequisites and run ./setup.sh again; see README.md.')
PY
printf '%s\n' 'Ready. Run .venv/bin/family-studio serve, then open http://127.0.0.1:8765/'
