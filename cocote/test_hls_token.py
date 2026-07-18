from playwright.sync_api import sync_playwright

HLS_TOKEN=("https://video.detik.com/trans7-sec/smil:trans7.smil/playlist.m3u8"
             "?wowzatokenstarttime=0&wowzatokenendtime=1784242854995"
             "&wowzatokenhash=LAqtkG3anCRFAHUTKSjMrMNN62gJxsOG6GT9oI0vDSo%3D")

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome',
                          args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='domcontentloaded', timeout=60000)
    pg.wait_for_timeout(3000)
    res = pg.evaluate('''async (url) => {
        const r = await fetch(url, {credentials:'include'});
        const t = await r.text();
        return {status:r.status, len:t.length, head:t.slice(0,150)};
    }''', HLS_TOKEN)
    print("HLS token fetch:", res)
    b.close()
