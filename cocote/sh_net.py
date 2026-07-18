from playwright.sync_api import sync_playwright

URL="https://sevenhub.id/live"
captured=[]
with sync_playwright() as p:
    b=p.chromium.launch(headless=True, channel='chrome')
    ctx=b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg=ctx.new_page()
    pg.on("request", lambda r: captured.append(r.url))
    pg.goto(URL, wait_until='domcontentloaded', timeout=45000)
    pg.wait_for_timeout(8000)
    hits=[u for u in captured if any(k in u.lower() for k in ('m3u8','.ts','hls','stream','embed','player','json','api'))]
    print("=== TOTAL:", len(captured), "hits:", len(hits))
    for h in hits[:50]:
        print(h[:160])
    b.close()
