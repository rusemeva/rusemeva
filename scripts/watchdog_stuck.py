#!/usr/bin/env python3
"""
Watchdog: cek GitHub Actions run yang macet >6 jam (stuck in_progress),
lalu cancel + kirim notifikasi ke Telegram.

Jalan via cron (pre-installed python3 + curl). Butuh env:
  GH_TOKEN, GH_OWNER, GH_REPO, BOT_TOKEN, CHAT_ID
"""
import os, json, urllib.request, subprocess, sys
from datetime import datetime, timezone

GH_API = "https://api.github.com"
STUCK_LIMIT_SEC = 6 * 3600  # 6 jam

def gh_get(path):
    out = subprocess.run(
        ["gh", "api", path, "-H", "Accept: application/vnd.github+json"],
        capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except Exception:
        return None

def send_tg(text):
    token = os.environ.get("BOT_TOKEN", "")
    chat = os.environ.get("CHAT_ID", "")
    if not token or not chat:
        return
    try:
        data = json.dumps({"chat_id": chat, "text": text, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30)
    except Exception as e:
        print(f"⚠️ sendTG gagal: {e}")

def main():
    owner = os.environ.get("GH_OWNER", "rusemeva")
    repo = os.environ.get("GH_REPO", "rusemeva")
    data = gh_get(f"repos/{owner}/{repo}/actions/runs?per_page=30")
    if not data or not data.get("workflow_runs"):
        print("ℹ️ Tidak ada run.")
        return
    now = datetime.now(timezone.utc)
    stuck = []
    for r in data["workflow_runs"]:
        if r.get("status") != "in_progress":
            continue
        created = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
        age = (now - created).total_seconds()
        if age > STUCK_LIMIT_SEC:
            stuck.append((r, age))
    if not stuck:
        print("✅ Tidak ada run macet.")
        return
    for r, age in stuck:
        rid = r["id"]
        # Cancel
        subprocess.run(["gh", "api", f"repos/{owner}/{repo}/actions/runs/{rid}/cancel",
                        "-X", "POST"], capture_output=True, text=True, timeout=60)
        hrs = int(age // 3600)
        msg = (f"🐶 <b>Watchdog: run macet dibatalkan</b>\n\n"
               f"⏱ Macet {hrs} jam\n"
               f"📋 {r.get('name','?')}\n"
               f"🔗 {r.get('html_url','')}\n\n"
               f"ℹ️ Rekaman/encode otomatis dibatalkan karena lewat 6 jam.")
        send_tg(msg)
        print(f"🐶 Cancelled stuck run {rid} ({hrs}h)")

if __name__ == "__main__":
    main()
