from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome', args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()
    tokens = []
    pg.on("request", lambda r: tokens.append(r.url) if "playlist.m3u8" in r.url and "wowzatoken" in r.url else None)
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='domcontentloaded', timeout=60000)
    pg.wait_for_timeout(2000)
    pg.click("button:has-text('Memutarkan Video')", timeout=5000)
    pg.wait_for_timeout(6000)
    print("=== HLS.js tokens (from detikVideo.js) ===")
    for t in tokens[:5]:
        print(t)
    b.close()
