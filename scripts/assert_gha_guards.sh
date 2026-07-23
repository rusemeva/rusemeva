#!/usr/bin/env bash
# Fail if GitHub Actions hard limits would be violated again.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== encode_policy selftest =="
bash scripts/encode_policy_selftest.sh

echo "== client_payload field count (max 10 per dispatch) =="
python - <<'PY2'
from pathlib import Path
import sys
MAX = 10
fail = 0
for f in sorted(Path(".github/workflows").glob("*.yml")):
    lines = f.read_text(encoding="utf-8").splitlines()
    i = 0
    block = 0
    while i < len(lines):
        if "dispatches" in lines[i] and ("gh api" in lines[i] or (i > 0 and "gh api" in lines[i-1])):
            # collect following -f client_payload lines
            n = 0
            j = i
            while j < len(lines) and j < i + 40:
                if "client_payload[" in lines[j]:
                    n += 1
                # end of dispatch command
                if j > i and not lines[j].strip().endswith("\\") and "client_payload" not in lines[j] and "event_type" not in lines[j] and "dispatches" not in lines[j]:
                    if n:
                        break
                if j > i and ("&&" in lines[j] or "|| true" in lines[j] or lines[j].strip().startswith("echo")) and n:
                    break
                j += 1
            if n:
                block += 1
                ok = n <= MAX
                print(f"  {f.name} dispatch#{block}: {n} fields [{'OK' if ok else 'FAIL'}]")
                if not ok:
                    fail = 1
            i = j
        else:
            i += 1
    # expression budget
    import re
    t = f.read_text(encoding="utf-8")
    total = sum(len(x) for x in re.findall(r"\$\{\{.*?\}\}", t, re.S))
    print(f"  {f.name} expression_chars={total}")
    if total > 18000:
        print(f"  FAIL {f.name} expression budget >18000")
        fail = 1
    if "encode" in f.name and "ci-policy" not in f.name:
        if "run_hevc_encode.sh" not in t:
            print(f"  FAIL {f.name} must call scripts/run_hevc_encode.sh")
            fail = 1
sys.exit(fail)
PY2

echo "== naming guards =="
if grep -n "recording-" src/index.js 2>/dev/null; then
  echo "FAIL: worker still uses recording- prefix"; exit 1
fi
if ! grep -q "Rusemeva-Asset-" src/index.js; then
  echo "FAIL: worker missing Rusemeva-Asset-"; exit 1
fi
if ! grep -q "encode_policy" scripts/run_hevc_encode.sh; then
  echo "FAIL: run_hevc_encode must use encode_policy"; exit 1
fi

echo "ALL GHA GUARDS OK"
