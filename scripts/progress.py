import json, os, sys, urllib.request

API = "{}/bot{}".format(
    os.environ.get("TG_API_URL", "http://localhost:8081").rstrip("/"),
    os.environ.get("BOT_TOKEN", ""),
)
CHAT = os.environ.get("CHAT_ID", "")
MSG_FILE = os.environ.get("PROGRESS_MSG_FILE", "/tmp/orvella_progress_msg_id")
FILENAME = os.environ.get("FILENAME", "")
# Label fase: "Rekam" atau "Encoding HEVC 10-bit" (default HEVC biar kompatibel)
PHASE_LABEL = os.environ.get("PHASE_LABEL", "Encoding HEVC 10-bit")


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
    print("usage: progress.py start|progress N|done|fail [text]")
    sys.exit(1)

mode = sys.argv[1]

ICON = "🔄" if mode in ("start", "progress") else "✅"

if mode == "start":
    text = "{} <b>{}</b>\n\n{} 0%\n📦 <code>{}</code>".format(
        ICON, PHASE_LABEL, build_bar(0), FILENAME)
    r = req("sendMessage", {"chat_id": CHAT, "text": text, "parse_mode": "HTML"})
    mid = r.get("result", {}).get("message_id")
    if mid:
        open(MSG_FILE, "w").write(str(mid))
    print("progress start msg_id={}".format(mid))

elif mode == "progress":
    pct = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    text = "{} <b>{}</b>\n\n{} {}%\n📦 <code>{}</code>".format(
        ICON, PHASE_LABEL, build_bar(pct), pct, FILENAME)
    edit(text)

elif mode == "done":
    text = sys.argv[2].replace("\\n", "\n") if len(sys.argv) > 2 else \
        "✅ <b>{} selesai!</b>\n\n⬆️ Mengupload ke release...".format(PHASE_LABEL)
    edit(text)

elif mode == "fail":
    text = sys.argv[2].replace("\\n", "\n") if len(sys.argv) > 2 else \
        "❌ <b>{} gagal.</b>\n\n🔗 Cek log run.".format(PHASE_LABEL)
    edit(text)

else:
    print("unknown mode: {}".format(mode))
    sys.exit(1)
