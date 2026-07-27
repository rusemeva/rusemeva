#!/usr/bin/env bash
# resolve_source.sh — Resolve stream source (trans7/sevenhub) to m3u8 URL.
# Exports: RESOLVED_URL, RESOLVED_REFERER to GITHUB_ENV
set -euo pipefail

SRC="${source:-}"
if [ -z "$SRC" ]; then
  echo "ℹ️ No source — using provided m3u8_url"
  exit 0
fi

echo "🔗 Resolving source: $SRC"

if [ "$SRC" = "trans7" ]; then
  SECRET="${WOWZA_SECRET:-}"
  if [ -z "$SECRET" ]; then
    echo "❌ WOWZA_SECRET not set"
    exit 1
  fi
  python3 scripts/gen_token_gha.py "$SECRET"

elif [ "$SRC" = "sevenhub" ]; then
  echo "📺 Installing Playwright..."
  pip install playwright -q 2>/dev/null || true
  playwright install chromium -q 2>/dev/null || true
  echo "📺 Resolving sevenhub m3u8 via browser..."
  python3 scripts/resolve_sevenhub.py

else
  echo "⚠️ Unknown source: $SRC"
fi
