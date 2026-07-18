from playwright.sync_api import sync_playwright
import json, time, os

OUT = "C:/Users/Administrator/Documents/cocote/detik_extract"
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome',
                          args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()
    captured = []
    def on_req(r):
        u = r.url
        if 'trans7' in u and '.m3u8' in u and 'wowzatokenhash=' in u:
            captured.append(u)
    pg.on("requestfinished", on_req)
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(8000)
    for sel in ['video','[class*=play]','button']:
        try:
            el = pg.query_selector(sel)
            if el: el.click(timeout=3000); break
        except: pass
    pg.wait_for_timeout(10000)
    pg.wait_for_timeout(3000)
    if not captured:
        print("NO PLAYLIST URL"); b.close(); exit()
    base_url = captured[0]
    print("PLAYLIST:", base_url[:90], "...")

    # Fetch playlist dari DALAM browser (bawa session/fingerprint)
    try:
        resp = pg.request.get(base_url, headers={'Referer':'https://20.detik.com/watch/livestreaming-trans7'})
        pl_text = resp.text()
        print("page.request status:", resp.status)
    except Exception as e:
        print("page.request ERR:", e)
        pl_text = ""
    print("PLAYLIST LINES:", len(pl_text.splitlines()))
    print(pl_text[:500])

    # Simpan playlist
    open(f"{OUT}/playlist.m3u8", 'w').write(pl_text)

    # Parse chunklist (jika playlist master) atau chunks langsung
    lines = [l.strip() for l in pl_text.splitlines() if l.strip() and not l.startswith('#')]
    print("MEDIA/CHUNK URLs:", len(lines))
    if lines:
        first = lines[0]
        # Jika ini chunklist (berisi .ts), download beberapa chunk
        if first.endswith('.ts'):
            print("Mode: chunklist, download 5 chunks...")
            for i, chunk in enumerate(lines[:5]):
                cu = chunk if chunk.startswith('http') else base_url.rsplit('/',1)[0] + '/' + chunk
                data = pg.evaluate('''async (u) => {
                    const r = await fetch(u, {credentials:'include'});
                    const buf = await r.arrayBuffer();
                    return Array.from(new Uint8Array(buf));
                }''', cu)
                path = f"{OUT}/chunk_{i:03d}.ts"
                open(path,'wb').write(bytes(data))
                print(f"  chunk {i}: {len(data)} bytes -> {path}")
        else:
            # Ini playlist master, fetch chunklist pertama
            cu = first if first.startswith('http') else base_url.rsplit('/',1)[0] + '/' + first
            print("Mode: master, fetch chunklist:", cu[:90])
            cl = pg.evaluate('''async (url) => {
                const r = await fetch(url, {credentials:'include'});
                return await r.text();
            }''', cu)
            open(f"{OUT}/chunklist.m3u8",'w').write(cl)
            print(cl[:500])

    b.close()
    print("DONE ->", OUT)
