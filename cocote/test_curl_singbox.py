from playwright.sync_api import sync_playwright
import subprocess, json

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome', args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()
    captured=[]
    pg.on("request", lambda r: captured.append(r.url) if 'wowzatokenhash=' in r.url else None)
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(8000)
    for sel in ['video','[class*=play]','button']:
        try:
            el=pg.query_selector(sel)
            if el: el.click(timeout=3000); break
        except: pass
    pg.wait_for_timeout(12000)
    tok=[u for u in captured if 'wowzatokenhash=' in u]
    if not tok:
        print("NO TOKEN"); b.close(); exit()
    url=tok[0]
    ck='; '.join(f"{c['name']}={c['value']}" for c in ctx.cookies())
    b.close()

# curl lewat sing-box proxy + cookies
ua='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36'
cmd=['curl','-s','-o','/dev/null','-w','%{http_code}','--max-time','15',
     '-x','socks5://127.0.0.1:1080',
     '-A',ua,'-e','https://20.detik.com/watch/livestreaming-trans7',
     '-H',f'Cookie: {ck}','--referer','https://20.detik.com/watch/livestreaming-trans7',
     url]
code=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
print("HTTP via curl+singbox+cookies:",code.stdout.strip())
print("URL:",url[:80],"...")
