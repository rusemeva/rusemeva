#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/encode_policy.sh
t=$(target_bytes 14400 5904438776)
[ "$t" = "2610000000" ]
[ "$(accept_hevc 2000000000 2610000000 2000000)" = "NEED_SMALLER" ]
[ "$(accept_hevc 2000000000 2610000000 1300000)" = "OK" ]
[ "$(accept_hevc 1000000000 2610000000 1000000)" = "NEED_BETTER" ]
[ "$(accept_hevc 1000 2610000000 "")" = "UNKNOWN" ]
# 10m target
t2=$(target_bytes 600 999999999999)
[ "$t2" = "108750000" ]
echo "encode_policy_selftest OK"
