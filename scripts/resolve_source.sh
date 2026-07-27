#!/usr/bin/env bash
# resolve_source.sh — Resolve stream source (trans7/sevenhub) to m3u8 URL.
# Exports: RESOLVED_URL, RESOLVED_REFERER
# Usage: source=trans7 WOWZA_SECRET=xxx bash scripts/resolve_source.sh
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
  echo "✅ Trans7 token generated"

elif [ "$SRC" = "sevenhub" ]; then
  RESP=$(curl -fsS --retry 2 --retry-delay 3 \
    -H "User-Agent: Rusemeva/1.0" \
    -H "Origin: https://sevenhub.id" \
    -H "Referer: https://sevenhub.id/live" \
    "https://api.sevenhub.id/api/v1/live-interaction" 2>/dev/null || echo '{}')

  STATUS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status_live',False))" 2>/dev/null || echo "False")
  LIVE_URL=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('url_live',''))" 2>/dev/null || echo "")

  if [ "$STATUS" = "True" ] && [ -n "$LIVE_URL" ]; then
    echo "✅ SevenHub live: $LIVE_URL"
    echo "RESOLVED_URL=$LIVE_URL" >> "$GITHUB_ENV"
    echo "RESOLVED_REFERER=https://sevenhub.id/live" >> "$GITHUB_ENV"
  else
    echo "❌ SevenHub not live (status=$STATUS)"
    CHAT_ID="${chat_id:-}"
    BOT_TOKEN="${BOT_TOKEN:-}"
    if [ -n "$CHAT_ID" ] && [ -n "$BOT_TOKEN" ]; then
      python3 scripts/send_message.py "📺 SevenHub sedang tidak live. Coba lagi nanti."
    fi
    exit 1
  fi

else
  echo "⚠️ Unknown source: $SRC"
fi
