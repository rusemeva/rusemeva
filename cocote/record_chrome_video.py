from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome',
                          args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36',
        record_video_dir='C:/Users/Administrator/Documents/cocote/'
    )
    pg = ctx.new_page()
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(6000)
    for sel in ['video','[class*=play]','button']:
        try:
            el = pg.query_selector(sel)
            if el: el.click(timeout=3000); break
        except: pass
    pg.wait_for_timeout(20000)  # record 20s
    info = pg.evaluate('''() => {
      const v=document.querySelector("video");
      return v?{w:v.videoWidth,h:v.videoHeight,ct:Math.round(v.currentTime*10)/10}:{nv:1};
    }''')
    print("VIDEO STATE:", info)
    pg.close()
    ctx.close()
    b.close()
    print("DONE - check video file")
