from playwright.sync_api import sync_playwright
import os, time

OUT = "C:/Users/Administrator/Documents/cocote/detik_extract"
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome',
                          args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()

    ts_files = []
    pl_files = []
    def handle_route(route):
        u = route.request.url
        if 'video.detik.com' in u and 'trans7' in u:
            try:
                response = route.fetch()
                body = response.body()
                if u.endswith('.m3u8') or 'chunklist' in u or 'playlist' in u:
                    fn = f"{OUT}/pl_{len(pl_files)}.m3u8"
                    open(fn,'wb').write(body); pl_files.append(fn)
                    print(f"PLAYLIST {len(pl_files)}: {len(body)} bytes")
                elif u.endswith('.ts') or 'media_w' in u:
                    if len(ts_files) < 20:
                        fn = f"{OUT}/seg_{len(ts_files):03d}.ts"
                        open(fn,'wb').write(body); ts_files.append(fn)
                        print(f"SEG {len(ts_files)}: {len(body)} bytes")
                route.fulfill(response=response)
                return
            except Exception as e:
                print("ROUTE ERR:", repr(e)[:100])
        route.continue_()

    pg.route("**/video.detik.com/**", handle_route)
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(6000)
    for sel in ['video','[class*=play]','button']:
        try:
            el = pg.query_selector(sel)
            if el: el.click(timeout=3000); break
        except: pass
    pg.wait_for_timeout(20000)
    print(f"\n=== CAPTURED: {len(pl_files)} playlists, {len(ts_files)} segments ===")
    if ts_files:
        with open(f"{OUT}/concat.ts",'wb') as out:
            for f in ts_files: out.write(open(f,'rb').read())
        print(f"concat.ts: {os.path.getsize(f'{OUT}/concat.ts')} bytes")
        # Convert ke mp4
        os.system(f'ffmpeg -y -i "{OUT}/concat.ts" -c copy "{OUT}/trans7_native.mp4" 2>&1 | tail -2')
        print("MP4:", os.path.getsize(f"{OUT}/trans7_native.mp4"), "bytes")
    b.close()
