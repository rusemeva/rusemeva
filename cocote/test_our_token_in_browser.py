from playwright.sync_api import sync_playwright
import sys
sys.path.insert(0, 'C:/Users/Administrator/Documents/cocote')
# Import generator token kita
from gen_token import gen_token

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome',
                          args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='domcontentloaded', timeout=60000)
    pg.wait_for_timeout(4000)

    # Generate token manual
    url, hinput = gen_token()
    print("Our token URL:", url[:100])
    # Fetch dari dalam browser
    res = pg.evaluate('''async (u) => {
        try {
            const r = await fetch(u, {credentials:'include', mode:'cors'});
            const t = await r.text();
            return {status:r.status, len:t.length, head:t.slice(0,120)};
        } catch(e){ return {err:e.message}; }
    }''', url)
    print("BROWSER FETCH OUR TOKEN:", res)
    b.close()
