#!/usr/bin/env python3
"""Resolve sevenhub m3u8 URL via Playwright browser automation.
Opens the Dailymotion embed, intercepts LIVE video m3u8 network request.
Exports RESOLVED_URL and RESOLVED_REFERER to GITHUB_ENV.
"""
import os, sys, time

def main():
    github_env = os.environ.get("GITHUB_ENV", "")

    from playwright.sync_api import sync_playwright

    VIDEO_ID = "x8qckyq"
    PLAYER_URL = f"https://geo.dailymotion.com/player/x15a7g.html?video={VIDEO_ID}"

    live_urls = []   # Actual live video m3u8 (cdndirector)
    other_urls = []  # Other m3u8 (ads, manifests)

    def handle_response(response):
        url = response.url
        if ".m3u8" not in url:
            return
        # Filter: actual live video stream (cdndirector domain)
        if "cdndirector" in url and "/live/" in url:
            live_urls.append(url)
            print(f"🎯 LIVE m3u8: {url[:100]}", flush=True)
        else:
            other_urls.append(url)

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
            locale="id-ID"
        )
        pg = ctx.new_page()
        pg.on("response", handle_response)

        print(f"[*] Opening {PLAYER_URL}", flush=True)
        pg.goto(PLAYER_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        # Try clicking play
        for sel in ['[aria-label="Play"]', 'button[class*="play"]', '.play-button', 'video']:
            try:
                el = pg.query_selector(sel)
                if el:
                    el.click(timeout=3000)
                    print(f"[*] Clicked: {sel}", flush=True)
                    break
            except:
                pass

        # JS play fallback
        try:
            pg.evaluate("() => { const v=document.querySelector('video'); if(v) v.play().catch(()=>{}); }")
        except:
            pass

        # Wait for live m3u8 (up to 45s)
        for i in range(45):
            if live_urls:
                break
            time.sleep(1)
            if i % 10 == 9:
                print(f"[*] Waiting... ({i+1}s, live={len(live_urls)}, other={len(other_urls)})", flush=True)

        b.close()

    if not live_urls:
        print("❌ No live m3u8 captured")
        if other_urls:
            print(f"Other m3u8 found ({len(other_urls)}):")
            for u in other_urls[:5]:
                print(f"  {u[:120]}")
        sys.exit(1)

    url = live_urls[0]
    print(f"✅ Resolved: {url[:80]}...")

    if github_env:
        with open(github_env, "a") as f:
            f.write(f"RESOLVED_URL={url}\n")
            f.write(f"RESOLVED_REFERER=https://sevenhub.id/live\n")
        print("✅ Exported to GITHUB_ENV")

if __name__ == "__main__":
    main()
