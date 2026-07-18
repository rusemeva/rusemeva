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
    url, _ = gen_token()
    res = pg.evaluate('''async (url) => {
        return await new Promise((resolve) => {
            const x = new XMLHttpRequest();
            x.open('GET', url, true);
            x.withCredentials = true;
            x.onload = () => resolve({status:x.status, len:x.responseText.length, head:x.responseText.slice(0,100)});
            x.onerror = () => resolve({err:'xhr error'});
            x.send();
        });
    }''', url)
    print("XHR OUR TOKEN:", res)
    b.close()
