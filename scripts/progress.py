import json, os, sys, urllib.request, time
from datetime import datetime, timedelta

API = "{}/bot{}".format(
    os.environ.get("TG_API_URL", "http://localhost:8081").rstrip("/"),
    os.environ.get("BOT_TOKEN", ""),
)
CHAT = os.environ.get("CHAT_ID", "")
MSG_FILE = os.environ.get("PROGRESS_MSG_FILE", "/tmp/orvella_progress_msg_id")
FILENAME = os.environ.get("FILENAME", "")
PHASE_LABEL = os.environ.get("PHASE_LABEL", "Encoding HEVC 10-bit")
# State file menyimpan: start_epoch,last_pct,last_epoch
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


def fmt_dur(secs):
    if secs is None or secs <= 0:
        return None
    secs = int(secs)
    h = secs // 3600
    m = (secs % 3600) // 60
    if h:
        return "{}j{}m".format(h, m)
    return "{}m".format(m)


def fmt_clock(secs_from_now):
    if secs_from_now is None or secs_from_now <= 0:
        return None
    # WIB = UTC+7
    t = datetime.utcnow() + timedelta(seconds=secs_from_now + 7 * 3600)
    return t.strftime("%H:%M") + " WIB"


def read_state():
    # returns (start_epoch, last_pct, last_epoch)
    try:
        parts = open(STATE_FILE).read().strip().split(",")
        return float(parts[0]), int(parts[1]), float(parts[2])
    except Exception:
        return 0.0, -1, 0.0


def write_state(start_epoch, pct, epoch):
    try:
        open(STATE_FILE, "w").write("{},{},{}".format(start_epoch, pct, epoch))
    except Exception:
        pass


def estimate_eta(pct, now, start_epoch):
    """Hitung sisa waktu + prediksi selesai dari progress riil.
    Return (eta_sisa_str, selesai_clock_str) atau (None, None) kalau belum cukup data.
    """
    if pct <= 0:
        return None, None
    # butuh minimal 2 titik (pct >= STEP_PCT) supaya garis lurus stabil
    if pct < STEP_PCT:
        return None, None
    if start_epoch <= 0:
        return None, None
    elapsed = now - start_epoch
    if elapsed <= 0:
        return None, None
    rate_pct_per_sec = pct / elapsed          # % per detik
    if rate_pct_per_sec <= 0:
        return None, None
    sisa_pct = 100 - pct
    eta_sisa_secs = sisa_pct / rate_pct_per_sec
    # sanity: tolak estimasi gak wajar (<1m atau >12j)
    if eta_sisa_secs < 60 or eta_sisa_secs > 12 * 3600:
        return None, None
    return fmt_dur(eta_sisa_secs), fmt_clock(eta_sisa_secs)


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
    write_state(time.time(), 0, time.time())
    print("progress start msg_id={}".format(mid))

elif mode == "progress":
    pct = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    start_epoch, last_pct, last_epoch = read_state()
    now = time.time()
    send = False
    if pct >= MILESTONE:
        send = True
    elif pct >= last_pct + STEP_PCT:
        send = True
    # jeda minimum agar tidak langgar rate-limit (kecuali 100%)
    if send and pct < MILESTONE and last_pct != -1 and (now - last_epoch) < MIN_INTERVAL:
        send = False
    if send:
        eta_sisa, selesai = estimate_eta(pct, now, start_epoch)
        eta_line = ""
        if eta_sisa and selesai:
            eta_line = "\n⏳ Sisa ~{} · selesai ~{}".format(eta_sisa, selesai)
        text = "{} <b>{}</b>\n\n{} {}%{}\n📦 <code>{}</code>".format(
            ICON, PHASE_LABEL, build_bar(pct), pct, eta_line, FILENAME)
        edit(text)
        write_state(start_epoch, pct, now)
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
