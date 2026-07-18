from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome',
                          args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(6000)
    pg.evaluate('''() => { const v=document.querySelector('video'); if(v){v.muted=true; v.play().catch(()=>{});} }''')
    pg.wait_for_timeout(6000)
    # Ambil vars dari detikVideo
    out = pg.evaluate('''() => {
        const dv = window.detikVideo;
        if(!dv) return {err:'no detikVideo'};
        const f = dv.features || {};
        const v = dv.vars || {};
        return {
            stShSc: f.stShSc,
            stUrlPrefix: f.stUrlPrefix,
            stUrlPostfix: f.stUrlPostfix,
            stPrefixParameter: f.stPrefixParameter,
            stStartTime: f.stStartTime,
            stEndTime: f.stEndTime,
            stFillUsableHashInput: v.stFillUsableHashInput,
            stUsableHashOriginal: v.stUsableHashOriginal,
            stUsableHash: v.stUsableHash,
            stHttpUrl: v.stHttpUrl
        };
    }''')
    print(out)
    b.close()
