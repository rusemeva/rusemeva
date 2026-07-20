import json, os, sys, urllib.request, time

API = "{}/bot{}".format(
    os.environ.get("TG_API_URL", "http://localhost:8081").rstrip("/"),
    os.environ.get("BOT_TOKEN", ""),
)
CHAT = os.environ.get("CHAT_ID", "")
MSG_FILE = os.environ.get("PROGRESS_MSG_FILE", "/tmp/orvella_progress_msg_id")
FILENAME = os.environ.get("FILENAME", "")
PHASE_LABEL = os.environ.get("PHASE_LABEL", "Encoding HEVC 10-bit")
# State file menyimpan last_pct,last_time agar throttling persist antar pemanggilan
# (progress.py dijalankan sebagai proses baru tiap tick oleh encode.yml)
STATE_FILE = os.environ.get("PROGRESS_STATE_FILE", "/tmp/orvella_progress_state")

# --- Konstanta throttle ---
STEP_PCT = 5        # kirim update tiap naik 5% (-> 20 update maksimal per video)
MIN_INTERVAL = 5    # jeda minimum 5 detik antar edit (anti rate-limit Telegram 1x/detik)
MILESTONE = 100     # selalu kirim saat mencapai 100%


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
    filled = pct // 5
    if filled > 20:
        filled = 20
    empty = 20 - filled
    return "█" * filled + "░" * empty


def read_state():
    try:
        parts = open(STATE_FILE).read().strip().split(",")
        return int(parts[0]), float(parts[1])
    except Exception:
        return -1, 0.0


def write_state(pct, t):
    try:
        open(STATE_FILE, "w").write("{},{}".format(pct, t))
    except Exception:
        pass


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
    write_state(0, time.time())
    print("progress start msg_id={}".format(mid))

elif mode == "progress":
    pct = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    last_pct, last_time = read_state()
    now = time.time()
    send = False
    if pct >= MILESTONE:
        send = True
    elif pct >= last_pct + STEP_PCT:
        send = True
    # jeda minimum agar tidak langgar rate-limit (kecuali 100%)
    if send and pct < MILESTONE and last_pct != -1 and (now - last_time) < MIN_INTERVAL:
        send = False
    if send:
        text = "{} <b>{}</b>\n\n{} {}%\n📦 <code>{}</code>".format(
            ICON, PHASE_LABEL, build_bar(pct), pct, FILENAME)
        edit(text)
        write_state(pct, now)
    else:
        print("progress skip {}% (last={})".format(pct, last_pct))

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
