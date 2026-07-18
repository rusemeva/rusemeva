from playwright.sync_api import sync_playwright
import urllib.request, json, time

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=['--no-sandbox','--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()
    captured = []
    pg.on("request", lambda r: captured.append(r.url) if 'wowzatokenhash=' in r.url else None)
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='domcontentloaded', timeout=60000)
    pg.wait_for_timeout(8000)
    for sel in ['video','[class*=play]','button']:
        try:
            el = pg.query_selector(sel)
            if el:
                el.click(timeout=3000); break
        except: pass
    pg.wait_for_timeout(10000)
    tok_urls = [u for u in captured if 'wowzatokenhash=' in u]
    if not tok_urls:
        print("NO TOKEN CAPTURED"); b.close(); exit()
    url = tok_urls[0]
    # Dapet cookies dari context
    cookies = ctx.cookies()
    ck = '; '.join(f"{c['name']}={c['value']}" for c in cookies)
    print("URL:", url[:90], "...")
    print("COOKIES:", ck[:100], "...")
    # Test curl dengan URL + cookie dari browser
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36',
        'Referer': 'https://20.detik.com/watch/livestreaming-trans7',
        'Cookie': ck
    })
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        print("HTTP", resp.status)
        print(resp.read().decode('utf-8','ignore')[:300])
    except Exception as e:
        print("ERR", e)
    b.close()
