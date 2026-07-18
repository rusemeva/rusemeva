from playwright.sync_api import sync_playwright
import os, sys

OUT = "C:/Users/Administrator/Documents/cocote/detik_live"
os.makedirs(OUT, exist_ok=True)

DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 600
CDP = "http://127.0.0.1:9222"  # Chrome dengan --remote-debugging-port=9222

# Connect ke Chrome yg SUDA JALAN (bukan launch baru)
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    # Cari tab yg detik, atau buka baru
    pg = ctx.new_page()
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='domcontentloaded', timeout=60000)
    pg.wait_for_timeout(3000)
    try:
        pg.click("button:has-text('Memutarkan Video')", timeout=5000)
    except:
        pass
    pg.wait_for_timeout(3000)
    # Generate token di Chrome ASLI (yg sudah punya session valid)
    JS = '''async () => {
        function sha256Hex(s){ return crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)).then(h=>new Uint8Array(h)); }
        async function b64url(u8p){ const u8=await u8p; let bin=''; for(let i=0;i<u8.length;i++) bin+=String.fromCharCode(u8[i]); return btoa(bin).replace(/\\+/g,'-').replace(/\\//g,'_'); }
        const SEC="258eed02421df5e2";
        const now=Date.now(); const end=String(now+15*60*1000);
        const hi="trans7-sec/smil:trans7.smil?"+SEC+"&wowzatokenendtime="+end+"&wowzatokenstarttime=0";
        const tok=await b64url(sha256Hex(hi));
        return "https://video.detik.com/trans7-sec/smil:trans7.smil/playlist.m3u8?wowzatokenstarttime=0&wowzatokenendtime="+end+"&wowzatokenhash="+encodeURIComponent(tok);
    }'''
    token_url = pg.evaluate(JS)
    print("Token:", token_url[:80])
    # Fetch pakai token ini
    r = pg.evaluate('''async (u) => {
        const t = await fetch(u, {credentials:'include'});
        return {status: t.status, len: (await t.text()).length};
    }''', token_url)
    print("Fetch result:", r)
    browser.close()
