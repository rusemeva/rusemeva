import json, os, sys, urllib.request

API = "{}/bot{}".format(
    os.environ.get("TG_API_URL", "http://localhost:8081").rstrip("/"),
    os.environ.get("BOT_TOKEN", ""),
)
CHAT = os.environ.get("CHAT_ID", "")
MSG_FILE = os.environ.get("PROGRESS_MSG_FILE", "/tmp/orvella_progress_msg_id")
FILENAME = os.environ.get("FILENAME", "")


def req(method, payload):
    data = json.dumps(payload).encode()
    r = urllib.request.Request(
        "{}/{}".format(API, method),
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print("⚠️ {} gagal: {}".format(method, e))
        return {}


def get_mid():
    try:
        return int(open(MSG_FILE).read().strip())
    except Exception:
        return None


def edit(text):
    mid = get_mid()
    if mid:
        req("editMessageText", {
            "chat_id": CHAT,
            "message_id": mid,
            "text": text,
            "parse_mode": "HTML",
        })
        print("progress edit -> msg_id={}".format(mid))


def build_bar(pct):
    filled = pct // 10
    empty = 10 - filled
    return "█" * filled + "░" * empty


if len(sys.argv) < 2:
    print("usage: progress.py start|progress N|done [text]")
    sys.exit(1)

mode = sys.argv[1]

if mode == "start":
    text = "🔄 <b>Encoding HEVC 10-bit</b>\n\n{} 0%\n📦 <code>{}</code>".format(
        build_bar(0), FILENAME)
    r = req("sendMessage", {"chat_id": CHAT, "text": text, "parse_mode": "HTML"})
    mid = r.get("result", {}).get("message_id")
    if mid:
        open(MSG_FILE, "w").write(str(mid))
    print("progress start msg_id={}".format(mid))

elif mode == "progress":
    pct = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    text = "🔄 <b>Encoding HEVC 10-bit</b>\n\n{} {}%\n📦 <code>{}</code>".format(
        build_bar(pct), pct, FILENAME)
    edit(text)

elif mode == "done":
    text = sys.argv[2].replace("\\n", "\n") if len(sys.argv) > 2 else "✅ <b>Encode HEVC 10-bit selesai!</b>\n\n⬆️ Mengupload ke release..."
    edit(text)

else:
    print("unknown mode: {}".format(mode))
    sys.exit(1)
