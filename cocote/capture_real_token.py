from playwright.sync_api import sync_playwright
import json, time

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=['--no-sandbox','--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()
    captured = []
    pg.on("request", lambda r: captured.append(r.url) if 'trans7' in r.url and ('.m3u8' in r.url or 'wowzatoken' in r.url) else None)
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='domcontentloaded', timeout=60000)
    pg.wait_for_timeout(8000)
    # Klik play
    for sel in ['video','[class*=play]','button']:
        try:
            el = pg.query_selector(sel)
            if el:
                el.click(timeout=3000)
                break
        except: pass
    pg.wait_for_timeout(10000)
    # Filter yang punya wowzatokenhash
    tok_urls = [u for u in captured if 'wowzatokenhash=' in u]
    print("=== REAL TOKEN URL from browser ===")
    for u in tok_urls[:3]:
        print(u)
        print()
    b.close()
