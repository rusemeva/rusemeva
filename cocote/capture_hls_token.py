from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome',
                          args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()
    pls = []
    pg.on('request', lambda r: pls.append(r.url) if 'playlist.m3u8' in r.url and 'video.detik.com' in r.url else None)
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(8000)
    pg.evaluate('''() => { const v=document.querySelector('video'); if(v){v.muted=true; v.play().catch(()=>{});} if(window.hls&&window.hls.startLoad)window.hls.startLoad(); }''')
    pg.wait_for_timeout(8000)
    print(f"Playlists captured: {len(pls)}")
    for u in pls[:3]:
        print(u)
        print("---")
    b.close()
