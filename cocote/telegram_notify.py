"""Kirim link 720p ke Telegram bot."""
import urllib.request, urllib.parse, os

url = open("cocote/live_url.txt").read().strip()
text = "🎬 <b>720p ready</b>\n\n<pre>" + url + "</pre>\n\n📋 /record"

data = urllib.parse.urlencode({
    "chat_id": os.environ["CHAT_ID"],
    "parse_mode": "HTML",
    "text": text
}).encode()

req = urllib.request.Request(
    f"https://api.telegram.org/bot{os.environ['BOT_TOKEN']}/sendMessage",
    data=data, method="POST"
)
r = urllib.request.urlopen(req)
print(r.read().decode()[:100])