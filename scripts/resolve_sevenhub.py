#!/usr/bin/env python3
"""Resolve sevenhub m3u8 URL via Playwright browser automation.
Opens the Dailymotion embed, intercepts m3u8 network request.
Exports RESOLVED_URL and RESOLVED_REFERER to GITHUB_ENV.
"""
import os, sys, time

def main():
    github_env = os.environ.get("GITHUB_ENV", "")

    from playwright.sync_api import sync_playwright

    VIDEO_ID = "x8qckyq"
    PLAYER_URL = f"https://geo.dailymotion.com/player/x15a7g.html?video={VIDEO_ID}"

    m3u8_urls = []
    all_urls = []

    def handle_response(response):
        url = response.url
        if ".m3u8" in url:
            m3u8_urls.append(url)
            print(f"🎯 m3u8: {url[:100]}", flush=True)
        # Also capture any hls/live related requests
        if "hls" in url or "live" in url or "cdn" in url:
            if url not in all_urls and ".ts" not in url and ".js" not in url:
                all_urls.append(url)

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

        # Wait for page to load
        time.sleep(5)

        # Try clicking play button
        for sel in ['[aria-label="Play"]', 'button[class*="play"]', '.play-button', 'video', '[data-testid="play"]']:
            try:
                el = pg.query_selector(sel)
                if el:
                    el.click(timeout=3000)
                    print(f"[*] Clicked: {sel}", flush=True)
                    break
            except:
                pass

        # Also try JS play
        try:
            pg.evaluate("""() => {
                const v = document.querySelector('video');
                if (v) { v.play().catch(()=>{}); return 'video found'; }
                return 'no video';
            }""")
        except:
            pass

        # Wait for m3u8 to appear (up to 30s)
        for i in range(30):
            if m3u8_urls:
                break
            time.sleep(1)
            if i % 5 == 4:
                print(f"[*] Waiting... ({i+1}s, {len(all_urls)} requests captured)", flush=True)

        b.close()

    if not m3u8_urls:
        print("❌ No m3u8 URL captured")
        if all_urls:
            print(f"Captured {len(all_urls)} related URLs:")
            for u in all_urls[:10]:
                print(f"  {u[:120]}")
        sys.exit(1)

    # Use the first captured URL
    url = m3u8_urls[0]
    print(f"✅ Resolved: {url[:80]}...")

    if github_env:
        with open(github_env, "a") as f:
            f.write(f"RESOLVED_URL={url}\n")
            f.write(f"RESOLVED_REFERER=https://sevenhub.id/live\n")
        print("✅ Exported to GITHUB_ENV")

if __name__ == "__main__":
    main()
