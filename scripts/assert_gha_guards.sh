#!/usr/bin/env bash
# Fail CI/local if repository_dispatch client_payload exceeds GitHub's hard limit of 10.
# Usage: bash scripts/assert_gha_guards.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MAX_PAYLOAD=10
MAX_EXPR_CHARS=18000   # GitHub hard limit is 21000; keep headroom

fail=0

echo "== encode_policy selftest =="
bash scripts/encode_policy_selftest.sh

echo "== client_payload field count =="
python - <<'PY'
from pathlib import Path
import re, sys
MAX=10
fail=0
for f in Path('.github/workflows').glob('*.yml'):
    t=f.read_text(encoding='utf-8')
    # each dispatches invocation
    for i,m in enumerate(re.finditer(r'dispatches\s*\\[\s\S]{0,2500}?(?:\n\s*(?:&&|\|\|)|$)', t)):
        block=m.group(0)
        n=block.count('client_payload[')
        if n==0:
            continue
        status='OK' if n<=MAX else 'FAIL'
        print(f"  {f.name} dispatch#{i+1}: {n} fields [{status}]")
        if n>MAX:
            fail=1
            print(block[:500])
    # expression budget (whole file)
    exprs=re.findall(r'\$\{\{.*?\}\}', t, re.S)
    total=sum(len(e) for e in exprs)
    print(f"  {f.name} expression_chars={total}")
    if total>18000:
        print(f"  FAIL {f.name} expression budget >18000 (GitHub max 21000)")
        fail=1
    # forbid huge run:| steps that re-embed encode body
    if f.name.endswith('encode.yml') or 'encode' in f.name:
        if 'run_hevc_encode.sh' not in t:
            print(f"  FAIL {f.name} must call scripts/run_hevc_encode.sh")
            fail=1
sys.exit(fail)
PY

echo "== naming guards =="
if grep -n "recording-" src/index.js 2>/dev/null; then
  echo "FAIL: worker still uses recording- prefix"; fail=1
fi
if ! grep -q "Rusemeva-Asset-" src/index.js; then
  echo "FAIL: worker missing Rusemeva-Asset-"; fail=1
fi
if ! grep -q "source scripts/encode_policy.sh\|encode_policy.sh" scripts/run_hevc_encode.sh 2>/dev/null; then
  echo "FAIL: run_hevc_encode must source encode_policy"; fail=1
fi

echo "ALL GHA GUARDS OK"
