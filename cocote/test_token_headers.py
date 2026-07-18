from playwright.sync_api import sync_playwright
import sys
sys.path.insert(0, 'C:/Users/Administrator/Documents/cocote')
from gen_token import gen_token

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome',
                          args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='domcontentloaded', timeout=60000)
    pg.wait_for_timeout(4000)

    url, _ = gen_token()
    # Coba berbagai header
    for name, headers in [
        ("with-origin", {"Origin":"https://20.detik.com","Referer":"https://20.detik.com/watch/livestreaming-trans7"}),
        ("hls-like", {"Origin":"https://20.detik.com","Referer":"https://20.detik.com/watch/livestreaming-trans7","Sec-Fetch-Dest":"empty","Sec-Fetch-Mode":"cors","Sec-Fetch-Site":"cross-site","Accept":"*/*"}),
    ]:
        res = pg.evaluate('''async (args) => {
            try {
                const r = await fetch(args.url, {credentials:'include', mode:'cors', headers:args.headers});
                const t = await r.text();
                return {status:r.status, len:t.length, head:t.slice(0,100)};
            } catch(e){ return {err:e.message}; }
        }''', {"url":url, "headers":headers})
        print(f"{name}: {res}")
    b.close()
