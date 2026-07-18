from playwright.sync_api import sync_playwright
import os, time, base64

OUT = "C:/Users/Administrator/Documents/cocote/detik_extract"
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome',
                          args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()

    # Tangkap URL chunklist + 1 chunk via network listener (request URL aja)
    chunk_urls = []
    pl_urls = []
    def on_req(r):
        u = r.url
        if 'video.detik.com' in u and 'trans7' in u:
            if 'media_w' in u and u not in chunk_urls:
                chunk_urls.append(u)
            elif ('chunklist' in u or u.endswith('.m3u8')) and u not in pl_urls:
                pl_urls.append(u)
    pg.on('request', on_req)

    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(6000)
    # Paksa play via JS
    pg.evaluate('''() => {
        const v = document.querySelector('video');
        if(v){ v.muted=true; v.play().catch(()=>{}); }
        // Cari hls global
        if(window.hls) window.hls.startLoad();
    }''')
    pg.wait_for_timeout(15000)

    print(f"PL URLs: {len(pl_urls)}, CHUNK URLs: {len(chunk_urls)}")
    if not chunk_urls:
        print("NO CHUNKS"); b.close(); exit()

    # Fetch chunk PERTAMA via browser asli (fetch dari page context)
    first_chunk = chunk_urls[0]
    print("Fetching chunk via browser fetch:", first_chunk[:80], "...")
    result = pg.evaluate('''async (url) => {
        try {
            const r = await fetch(url, {credentials:'include', mode:'cors'});
            const buf = await r.arrayBuffer();
            const arr = Array.from(new Uint8Array(buf));
            return {ok:true, status:r.status, len:buf.byteLength, arr:arr};
        } catch(e) { return {ok:false, err:e.message}; }
    }''', first_chunk)
    print("FETCH RESULT:", result.get('status'), result.get('len'), "bytes" if result.get('ok') else result.get('err'))
    if result.get('ok') and result.get('len',0) > 0:
        data = bytes(result['arr'])
        fn = f"{OUT}/chunk0.ts"
        open(fn,'wb').write(data)
        print(f"SAVED {fn}: {len(data)} bytes")
        os.system(f'ffprobe -v error -show_entries stream=codec_name,width,height -of default=noprint_wrappers=1 "{fn}" 2>&1 | head -3')
    b.close()
