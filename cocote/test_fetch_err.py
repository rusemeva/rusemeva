from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome', args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='domcontentloaded', timeout=60000)
    pg.wait_for_timeout(2000)
    res = pg.evaluate('''async () => {
        function sha256Hex(s){
            const h = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
            return new Uint8Array(h);
        }
        function b64url(u8){
            let bin=''; for(let i=0;i<u8.length;i++) bin+=String.fromCharCode(u8[i]);
            return btoa(bin).replace(/\\+/g,'-').replace(/\\//g,'_');
        }
        const ST_SHSC="258eed02421df5e2";
        const now=Date.now(); const end=String(now+15*60*1000); const st="0";
        const hi="trans7-sec/smil:trans7.smil?"+ST_SHSC+"&wowzatokenendtime="+end+"&wowzatokenstarttime="+st;
        const buf=await sha256Hex(hi); const tok=b64url(buf);
        const url="https://video.detik.com/trans7-sec/smil:trans7.smil/playlist.m3u8?wowzatokenstarttime="+st+"&wowzatokenendtime="+end+"&wowzatokenhash="+encodeURIComponent(tok);
        try {
            const r=await fetch(url,{credentials:'include'});
            const t=await r.text();
            return {ok:true, status:r.status, len:t.length, head:t.slice(0,80)};
        } catch(e) {
            return {ok:false, err:e.message, name:e.name};
        }
    }''')
    print("RESULT:", res)
    b.close()
