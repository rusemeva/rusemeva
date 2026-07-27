#!/usr/bin/env python3
"""Resolve sevenhub m3u8 URL via Playwright browser automation.
Opens the Dailymotion embed, intercepts m3u8 network request.
Exports RESOLVED_URL and RESOLVED_REFERER to GITHUB_ENV.
"""
import os, sys, time

def main():
    github_env = os.environ.get("GITHUB_ENV", "")
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        # Install playwright if not available
        os.system("pip install playwright -q && playwright install chromium -q")
        from playwright.sync_api import sync_playwright

    VIDEO_ID = "x8qckyq"
    PLAYER_URL = f"https://geo.dailymotion.com/player/x15a7g.html?video={VIDEO_ID}"
    
    m3u8_urls = []
    
    def handle_response(response):
        url = response.url
        if ".m3u8" in url and "cdndirector" in url:
            m3u8_urls.append(url)
            print(f"🎯 Captured m3u8: {url[:80]}...")
    
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"
        )
        pg = ctx.new_page()
        pg.on("response", handle_response)
        
        print(f"[*] Opening {PLAYER_URL}")
        pg.goto(PLAYER_URL, wait_until="domcontentloaded", timeout=30000)
        
        # Wait for m3u8 to appear (up to 20s)
        for i in range(20):
            if m3u8_urls:
                break
            time.sleep(1)
        
        b.close()
    
    if not m3u8_urls:
        print("❌ No m3u8 URL captured")
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
