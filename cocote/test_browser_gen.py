from playwright.sync_api import sync_playwright
import sys, inspect
sys.path.insert(0, 'C:/Users/Administrator/Documents/cocote')
import gen_token as G
# Ambil source fungsi gen_token + constants
src = inspect.getsource(G)
# Strip import & main block
clean = []
for line in src.splitlines():
    if line.startswith('import ') or line.startswith('from ') or 'if __name__' in line:
        continue
    clean.append(line)
js_consts = '''
const ST_SHSC="258eed02421df5e2";
const ST_PREFIX="wowzatoken";
const ST_URL_PREFIX="trans7-sec/smil:";
const ST_URL_POSTFIX="trans7.smil";
const ST_DOMAIN="https://video.detik.com";
const ST_EXPIRE_MIN=15;
function genToken(){
  const now=Date.now();
  const end=String(now+ST_EXPIRE_MIN*60*1000);
  const start="0";
  const hi=ST_URL_PREFIX+ST_URL_POSTFIX+"?"+ST_SHSC+"&"+ST_PREFIX+"endtime="+end+"&"+ST_PREFIX+"starttime="+start;
  const sha=sha256(hi);
  let tok=btoa(String.fromCharCode(...new Uint8Array(sha))).replace(/\\+/g,"-").replace(/\\//g,"_");
  return ST_DOMAIN+"/"+ST_URL_PREFIX+ST_URL_POSTFIX+"/playlist.m3u8?"+ST_PREFIX+"starttime="+start+"&"+ST_PREFIX+"endtime="+end+"&"+ST_PREFIX+"hash="+encodeURIComponent(tok);
}
'''
with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome', args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='domcontentloaded', timeout=60000)
    pg.wait_for_timeout(3000)
    # Inject sha256 (pakai SubtleCrypto via crypto.subtle)
    res = pg.evaluate('''async () => {
        function sha256(s){
            return crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)).then(h=>new Uint8Array(h));
        }
        const ST_SHSC="258eed02421df5e2";
        const ST_PREFIX="wowzatoken";
        const ST_URL_PREFIX="trans7-sec/smil:";
        const ST_URL_POSTFIX="trans7.smil";
        const ST_DOMAIN="https://video.detik.com";
        const now=Date.now();
        const end=String(now+15*60*1000);
        const start="0";
        const hi=ST_URL_PREFIX+ST_URL_POSTFIX+"?"+ST_SHSC+"&"+ST_PREFIX+"endtime="+end+"&"+ST_PREFIX+"starttime="+start;
        const buf=await sha256(hi);
        let tok=btoa(String.fromCharCode(...buf)).replace(/\\+/g,"-").replace(/\\//g,"_");
        const url=ST_DOMAIN+"/"+ST_URL_PREFIX+ST_URL_POSTFIX+"/playlist.m3u8?"+ST_PREFIX+"starttime="+start+"&"+ST_PREFIX+"endtime="+end+"&"+ST_PREFIX+"hash="+encodeURIComponent(tok);
        const r=await fetch(url,{credentials:'include'});
        const t=await r.text();
        return {status:r.status, len:t.length, head:t.slice(0,120)};
    }''')
    print("BROWSER GEN+FETCH:", res)
    b.close()
