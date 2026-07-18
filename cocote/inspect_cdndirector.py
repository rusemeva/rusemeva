from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(headless=True, channel='chrome')
    ctx=b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg=ctx.new_page()
    captured=[]
    pg.on("request", lambda r: captured.append((r.url, dict(r.headers))))
    pg.goto("https://sevenhub.id/live", wait_until='domcontentloaded', timeout=45000)
    pg.wait_for_timeout(12000)
    for u,h in captured:
        if 'cdndirector' in u and '.m3u8' in u:
            print("=== CDNDIRECTOR REQUEST ===")
            print("URL:", u[:120])
            for k,v in h.items():
                if k.lower() in ('user-agent','referer','origin','cookie','sec-fetch','x-request','accept'):
                    print(f"  {k}: {v[:80]}")
            break
    else:
        print("No cdndirector request captured in RDP browser")
    b.close()
