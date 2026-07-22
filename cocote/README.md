# Cocote — HLS/m3u8 Capture & Browser Automation Scripts

Companion project untuk **Rusemeva Vault** (`rusemeva/rusemeva`) — kumpulan script
capture m3u8/HLS, ekstraksi token DRM, dan automation browser (Chrome/CDP).

## Isi
Script capture & browser-only. File runtime sensitif (cookie DRM, live URL,
session data) **sengaja tidak di-include** — lihat `.gitignore`.

## Bot / Chat
Script notifikasi menggunakan bot Telegram project: `@BackupRelpay_bot`
(token di-set via GitHub Secrets / env `BOT_TOKEN`, chat owner `2027652715`).

## Setup
```bash
pip install -r requirements.txt   # bila ada
export BOT_TOKEN="..."            # untuk telegram_notify.py
python m3u8_capture.py
```
