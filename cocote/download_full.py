from playwright.sync_api import sync_playwright
import os, time

OUT = "C:/Users/Administrator/Documents/cocote/detik_extract"
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome',
                          args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()

    # Capture chunklist URL
    captured = {'pl': [], 'chunklist': [], 'chunks': []}
    def on_req(r):
        u = r.url
        if 'video.detik.com' in u and 'trans7' in u:
            if u.endswith('.m3u8') and u not in captured['pl']:
                captured['pl'].append(u)
            elif 'chunklist' in u and u not in captured['chunklist']:
                captured['chunklist'].append(u)
            elif 'media_w' in u and u not in captured['chunks']:
                captured['chunks'].append(u)
    pg.on('request', on_req)

    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='networkidle', timeout=60000)
    # Poll sampai chunklist ketangkap (max 40s)
    for _ in range(20):
        pg.evaluate('''() => { const v=document.querySelector('video'); if(v){v.muted=true; v.play().catch(()=>{});} }''')
        pg.wait_for_timeout(2000)
        if captured['chunklist']:
            break
    pg.wait_for_timeout(5000)

    print(f"PL={len(captured['pl'])}, CHUNKLIST={len(captured['chunklist'])}, CHUNKS={len(captured['chunks'])}")

    # Ambil chunklist text via browser fetch
    if captured['chunklist']:
        cl_url = captured['chunklist'][-1]
        cl_text = pg.evaluate('''async (url) => {
            const r = await fetch(url, {credentials:'include'});
            return await r.text();
        }''', cl_url)
        open(f"{OUT}/chunklist.m3u8",'w').write(cl_text)
        print("CHUNKLIST:", cl_text[:300])
        # Parse semua .ts dari chunklist
        ts_urls = [l.strip() for l in cl_text.splitlines() if l.strip().endswith('.ts')]
        print(f"TS in chunklist: {len(ts_urls)}")
        # Download semua via browser fetch
        downloaded = 0
        for i, tsu in enumerate(ts_urls[:40]):  # limit 40 chunk
            full = tsu if tsu.startswith('http') else cl_url.rsplit('/',1)[0] + '/' + tsu
            res = pg.evaluate('''async (url) => {
                const r = await fetch(url, {credentials:'include'});
                const buf = await r.arrayBuffer();
                return {ok:r.ok, arr:Array.from(new Uint8Array(buf))};
            }''', full)
            if res.get('ok'):
                data = bytes(res['arr'])
                open(f"{OUT}/seg_{i:03d}.ts",'wb').write(data)
                downloaded += 1
        print(f"Downloaded {downloaded} segments")
        if downloaded:
            with open(f"{OUT}/concat.ts",'wb') as o:
                for i in range(downloaded):
                    o.write(open(f"{OUT}/seg_{i:03d}.ts",'rb').read())
            os.system(f'ffmpeg -y -i "{OUT}/concat.ts" -c copy "{OUT}/trans7_native.mp4" 2>&1 | tail -1')
            print("MP4 size:", os.path.getsize(f"{OUT}/trans7_native.mp4"))
            os.system(f'ffprobe -v error -show_entries stream=codec_name,width,height -of default=noprint_wrappers=1 "{OUT}/trans7_native.mp4" 2>&1 | head -3')
    b.close()
