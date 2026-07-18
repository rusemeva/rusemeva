from playwright.sync_api import sync_playwright
import urllib.request

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome', args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()
    captured = []
    pg.on("request", lambda r: captured.append((r.url, dict(r.headers))) if 'wowzatokenhash=' in r.url else None)
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(8000)
    for sel in ['video','[class*=play]','button']:
        try:
            el = pg.query_selector(sel)
            if el: el.click(timeout=3000); break
        except: pass
    pg.wait_for_timeout(12000)
    tok = [(u,h) for u,h in captured if 'wowzatokenhash=' in u]
    if not tok:
        print("NO TOKEN"); b.close(); exit()
    url, headers = tok[0]
    ck = '; '.join(f"{c['name']}={c['value']}" for c in ctx.cookies())
    # Replay dengan headers ASLI dari browser request
    req_headers = {
        'User-Agent': headers.get('user-agent','Mozilla/5.0'),
        'Referer': headers.get('referer','https://20.detik.com/watch/livestreaming-trans7'),
        'Cookie': ck,
        'Accept': headers.get('accept','*/*'),
        'Origin': headers.get('origin','https://20.detik.com'),
    }
    print("REPLAY with browser headers...")
    req = urllib.request.Request(url, headers=req_headers)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        print("HTTP", resp.status, "-> SUCCESS!")
        print(resp.read().decode('utf-8','ignore')[:200])
    except Exception as e:
        print("ERR", e)
    b.close()
