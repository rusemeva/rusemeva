from playwright.sync_api import sync_playwright

URL = "https://20.detik.com/live/trans-tv"
with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome', args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36',
        proxy={"server": "socks5://127.0.0.1:1080"})
    pg = ctx.new_page()
    resp=[]
    pg.on("response", lambda r: resp.append((r.status, r.url)) if "video.detik.com" in r.url else None)
    pg.goto(URL, wait_until='domcontentloaded', timeout=60000)
    pg.wait_for_timeout(2000)
    try: pg.click("button:has-text('Memutarkan Video')", timeout=5000)
    except: pass
    # tunggu video playing
    playing = pg.evaluate('''async () => {
        for(let i=0;i<30;i++){
            const v=document.querySelector('video');
            if(v && !v.paused && v.currentTime>0) return {ok:true, t:v.currentTime};
            await new Promise(r=>setTimeout(r,500));
        }
        return {ok:false};
    }''')
    print("Playing:", playing)
    pg.wait_for_timeout(5000)
    vd=[x for x in resp if "video.detik.com" in x[1]]
    st={}
    for s,u in vd: st[s]=st.get(s,0)+1
    print(f"Responses={len(vd)} status={st}")
    for s,u in vd[:3]: print(s, u[:90])
    b.close()
