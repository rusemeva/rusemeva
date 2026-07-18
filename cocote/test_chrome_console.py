from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome',
                          args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()
    errors = []
    pg.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type in ('error','warning') else None)
    pg.on("pageerror", lambda e: errors.append(f"PAGEERR: {e.message}"))
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(12000)
    for sel in ['video','[class*=play]','button']:
        try:
            el = pg.query_selector(sel)
            if el: el.click(timeout=3000); break
        except: pass
    pg.wait_for_timeout(10000)
    print("=== CONSOLE ERRORS ===")
    for e in errors[-20:]:
        if any(k in e.lower() for k in ['hls','video','media','source','mse','fetch','403','token','decode']):
            print(e)
    b.close()
