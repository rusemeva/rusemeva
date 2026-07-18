#!/usr/bin/env python3
"""
m3u8_capture.py - Capture playlist .m3u8 dari RDP (Chromium headless).

Alur:
  1. Buka Chromium (channel=chrome di RDP, chromium bawaan di CI)
  2. Navigasi ke embed player (referer otomatis dari embed)
  3. Fetch API -> dapat master playlist -> 200
  4. Parse semua variant (240/480/720) dari master body
  5. Lock 720p kalau ada, fallback ke variant tertinggi
  6. Simpan ke folder cocote/ (captured.m3u8 + live_url.txt)

Catatan: URL berisi token sekali-pakai (rotate 1-2 jam). Bukan link permanen.
"""
import sys, time, os
from playwright.sync_api import sync_playwright

VIDEO_ID = "x8qckyq"
PLAYER_URL = f"https://geo.dailymotion.com/player/x15a7g.html?video={VIDEO_ID}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
OUT_DIR = "cocote"
OUT = os.path.join(OUT_DIR, "captured.m3u8")
LIVE_URL = os.path.join(OUT_DIR, "live_url.txt")
# prioritas resolusi (turun dari tertinggi)
PRIORITY = ["720", "480", "240"]


def pick_variant(master_body):
    """Parse master body, kembalikan (chosen_url, all_variant_lines)."""
    lines = master_body.splitlines()
    variants = []  # list of (name, url)
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            name = ""
            if "NAME=\"" in line:
                name = line.split("NAME=\"")[1].split("\"")[0]
            # baris berikutnya = url
            if i + 1 < len(lines) and lines[i + 1].startswith("https://"):
                url = lines[i + 1].split("#")[0]
                variants.append((name, url))
    # cari berdasarkan priority
    for p in PRIORITY:
        for name, url in variants:
            if name == p or f"live-{p}" in url:
                return url, variants
    # fallback: variant pertama
    if variants:
        return variants[0][1], variants
    return "", []


def main():
    with sync_playwright() as p:
        launch_kwargs = {"headless": True}
        if os.environ.get("CAPTURE_USE_CHROME") == "1":
            launch_kwargs["channel"] = "chrome"
        b = p.chromium.launch(**launch_kwargs)
        ctx = b.new_context(user_agent=UA)
        pg = ctx.new_page()
        print(f"[*] buka {PLAYER_URL}")
        pg.goto(PLAYER_URL, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(6000)
        print("[*] fetch master playlist dari page context...")
        result = pg.evaluate("""async () => {
            const api = 'https://geo.dailymotion.com/video/x8qckyq.json?legacy=true&geo=1&player-id=x15a7g&publisher-id=x2virdk&locale=id&dmV1st=4975e6cb-4f89-8c56-cb06-3e7775a8c1ee&dmTs=' + (Math.floor(Date.now()/1000)%1000000) + '&is_native_app=0&app=idm.internet.download.manager.plus&dmViewId=1jtncqgbk6a3020c78f&parallelCalls=1';
            const d = await (await fetch(api, {credentials:'include'})).json();
            const m3u8 = d.qualities.auto[0].url;
            const r = await fetch(m3u8, {credentials:'include'});
            const t = await r.text();
            return {status: r.status, url: m3u8, body: t};
        }""")
        b.close()

    if not result or result.get("status") != 200 or not result.get("body"):
        print(f"[!] gagal: {str(result)[:200]}")
        sys.exit(1)

    master_url = result["url"]
    master_body = result["body"]
    print(f"[+] MASTER 200 ({master_url[:120]})")
    print(master_body[:1500])

    chosen, variants = pick_variant(master_body)
    if not chosen:
        print("[!] gak ada variant ditemukan di master body")
        sys.exit(1)

    print(f"[+] variant ditemukan: {len(variants)} -> pilih: {chosen[:120]}")

    # simpan master lengkap (semua variant) ke captured.m3u8
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    full = ["#EXTM3U", f"# capture-from: {PLAYER_URL}",
            f"# generated: {ts}", "", master_body.rstrip()]
    full.append("")
    full.append("# all-variants:")
    for name, url in variants:
        full.append(f"#   {name}: {url}")
    out = "\n".join(full) + "\n"
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"[+] disimpan ke {OUT} ({len(out)} bytes)")

    # simpan URL terpilih ke live_url.txt
    # kalau dapet 240p, generate juga URL 720p (token sama, resolusi beda)
    url_720 = chosen
    if "live-240" in url_720:
        url_720 = url_720.replace("live-240", "live-720")
    with open(LIVE_URL, "w", encoding="utf-8") as f:
        f.write(url_720 + "\n")
    print(f"[+] {LIVE_URL} -> {url_720[:120]}")

    # verifikasi isi
    with open(LIVE_URL) as f:
        saved = f.read().strip()
    if "live-720" in saved:
        print("[OK] 720p locked")
    else:
        # cari resolusi dari url
        import re
        m = re.search(r"live-(\d+)", saved)
        print(f"[OK] resolved to {m.group(1) if m else 'unknown'}p")


if __name__ == "__main__":
    main()
