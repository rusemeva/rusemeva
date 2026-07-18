from playwright.sync_api import sync_playwright
import os, time

OUT = "C:/Users/Administrator/Documents/cocote/detik_extract"
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome',
                          args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()

    # Tangkap SEMUA request ke video.detik.com (URL + body)
    log = []
    def on_req(r):
        u = r.url
        if 'video.detik.com' in u or 'ezdrm.detik.com' in u:
            entry = {'url': u[:140], 'method': r.method}
            try:
                if r.method == 'POST':
                    entry['post'] = r.post_data[:200] if r.post_data else None
            except: pass
            log.append(entry)
    pg.on("request", on_req)

    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(6000)
    for sel in ['video','[class*=play]','button']:
        try:
            el = pg.query_selector(sel)
            if el: el.click(timeout=3000); break
        except: pass
    pg.wait_for_timeout(15000)

    print(f"=== {len(log)} requests to detik video ===")
    for e in log[:15]:
        print(e['method'], e['url'])
        if e.get('post'): print("   POST:", e['post'])
    b.close()
