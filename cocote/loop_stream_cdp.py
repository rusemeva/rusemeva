import subprocess, time, sys, os
from playwright.sync_api import sync_playwright

OUT = "C:/Users/Administrator/Documents/cocote/detik_live"
os.makedirs(OUT, exist_ok=True)
DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 600
URL = "https://20.detik.com/watch/livestreaming-trans7"

# 1. Launch Chrome ASLI (bukan Playwright) dengan remote debugging
chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if not os.path.exists(chrome_path):
    chrome_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
proc = subprocess.Popen([
    chrome_path,
    "--remote-debugging-port=9222",
    "--autoplay-policy=no-user-gesture-required",
    "--user-data-dir=C:/Users/Administrator/AppData/Local/ChromeDebug",
    URL
])
time.sleep(4)

JS_WAIT_PLAY = '''async () => {
    for(let i=0;i<40;i++){
        const v=document.querySelector('video');
        if(v && !v.paused && v.currentTime>0) return {ok:true,t:v.currentTime};
        await new Promise(r=>setTimeout(r,500));
    }
    return {ok:false};
}'''

JS_GEN=r'''async () => {
    function sha256Hex(s){ return crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)).then(h=>new Uint8Array(h)); }
    async function b64url(u8p){ const u8=await u8p; let bin=''; for(let i=0;i<u8.length;i++) bin+=String.fromCharCode(u8[i]); const b=btoa(bin); return b.split('+').join('-').split('/').join('_'); }
    const SEC="258eed02421df5e2";
    const now=Date.now(); const end=String(now+15*60*1000); const st="0";
    const hi="trans7-sec/smil:trans7.smil?"+SEC+"&wowzatokenendtime="+end+"&wowzatokenstarttime="+st;
    const tok=await b64url(sha256Hex(hi));
    return "https://video.detik.com/trans7-sec/smil:trans7.smil/playlist.m3u8?wowzatokenstarttime="+st+"&wowzatokenendtime="+end+"&wowzatokenhash="+encodeURIComponent(tok);
}'''

JS_LOOP=r'''async (tokenUrl, dura) => {
    function fetchBin(u){ return fetch(u,{credentials:'include'}).then(r=>r.arrayBuffer()).then(b=>Array.from(new Uint8Array(b))).catch(()=>null); }
    function fetchText(u){ return fetch(u,{credentials:'include'}).then(r=>r.text()).catch(()=>null); }
    const concat=[]; const seen=new Set(); const start=Date.now(); let seg=0; let err=null;
    while((Date.now()-start) < dura*1000){
        try {
            const mt=await fetchText(tokenUrl);
            if(!mt){ err='master null'; await new Promise(r=>setTimeout(r,2000)); continue; }
            const lines=mt.split('\n').map(x=>x.trim()).filter(x=>x && !x.startsWith('#'));
            const cl=lines[lines.length-1];
            const clUrl=cl.startsWith('http')?cl:(tokenUrl.split('/playlist.m3u8')[0]+'/'+cl);
            const clt=await fetchText(clUrl);
            if(!clt){ err='chunklist null'; await new Promise(r=>setTimeout(r,2000)); continue; }
            const ts=clt.split('\n').map(x=>x.trim()).filter(x=>x.endsWith('.ts'));
            for(const t of ts){
                const key=t.split('/').pop();
                if(seen.has(key)) continue;
                seen.add(key);
                const bin=await fetchBin(clUrl.split('/').slice(0,-1).join('/')+'/'+t);
                if(bin){ concat.push(bin); seg++; }
            }
            err=null;
        } catch(e){ err=e.message; }
        await new Promise(r=>setTimeout(r,2500));
    }
    return {seg:seg, concat:concat, err:err};
}'''

try:
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = b.contexts[0]
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.wait_for_timeout(2000)
        try:
            pg.click("button:has-text('Memutarkan Video')", timeout=5000)
        except: pass
        w = pg.evaluate(JS_WAIT_PLAY)
        if w.get('ok'):
            print(f"Video playing t={w.get('t'):.1f}s")
        else:
            print("WARN: video not playing")
        print(f"Recording {DURATION}s...")
        token = pg.evaluate(JS_GEN)
        result = pg.evaluate(JS_LOOP, [token, DURATION])
        print(f"Segments: {result.get('seg')}, Err: {result.get('err')}")
        with open(f"{OUT}/live.ts","wb") as o:
            for c in result.get('concat',[]): o.write(bytes(c))
        size=os.path.getsize(f"{OUT}/live.ts")
        print(f"TS: {size} bytes")
        if size>0:
            os.system(f'ffmpeg -y -i "{OUT}/live.ts" -c copy "{OUT}/trans7_live.mp4" 2>&1 | tail -1')
            print("MP4:", os.path.getsize(f"{OUT}/trans7_live.mp4"))
finally:
    proc.terminate()
