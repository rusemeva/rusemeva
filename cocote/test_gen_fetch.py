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
    pg.wait_for_timeout(3000)
    # Generate + fetch dalam 1 evaluate (no time gap)
    res = pg.evaluate('''async (mod) => {
        const url = mod.gen();
        const r = await fetch(url, {credentials:'include'});
        const t = await r.text();
        return {status:r.status, len:t.length, head:t.slice(0,120)};
    }''', {"gen": None})
    print("RESULT:", res)
    b.close()
