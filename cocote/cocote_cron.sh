#!/bin/bash
# cocote_cron.sh — capture 720p + kirim Telegram + push GitHub
set -e
cd C:/Users/Administrator/Documents/cocote

echo "=== $(date '+%H:%M:%S') COCOTE CAPTURE ==="

# Step 1: Capture
export CAPTURE_USE_CHROME=1
timeout 80 python m3u8_capture.py 2>&1 | tail -3
echo ""

# Step 2: Kirim ke Telegram
python -c "
import urllib.request, urllib.parse, os
url = open('cocote/live_url.txt').read().strip()
text = '🎬 <b>720p ready</b>\n\n<pre>' + url + '</pre>\n\n📋 /record'
data = urllib.parse.urlencode({
    'chat_id': '2027652715',
    'parse_mode': 'HTML',
    'text': text
}).encode()
r = urllib.request.urlopen(urllib.request.Request(
    'https://api.telegram.org/bot8874514227:AAG9DhuC5rIArQb11mLaNwKbLEOeuzDpMEI/sendMessage',
    data=data, method='POST'))
print(r.read().decode()[:80])
"

# Step 3: Push ke GitHub
git add cocote/captured.m3u8 cocote/live_url.txt
git diff --cached --quiet || {
    git commit -m "chore: refresh [skip ci]"
    git push
}
echo "=== DONE ==="