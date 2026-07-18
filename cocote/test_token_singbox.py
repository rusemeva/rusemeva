import urllib.request, socks, socket

# Set SOCKS5 proxy (sing-box 127.0.0.1:1080)
socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 1080)
socket.socket = socks.socksocket

from urllib.parse import quote
import hashlib, base64, time

ST_SHSC="807aad1578ee7d9a"; ST_PREFIX="wowzatoken"; ST_URL_PREFIX="trans7-sec/smil:"
now=int(time.time()*1000); end=str(now+15*60*1000); start="0"
hinput=ST_URL_PREFIX+"?"+ST_SHSC+"&"+ST_PREFIX+"endtime="+end+"&"+ST_PREFIX+"starttime="+start
token=base64.b64encode(hashlib.sha256(hinput.encode()).digest()).decode().replace('+','-').replace('/','_')
url=f"https://video.detik.com/{ST_URL_PREFIX}trans7.smil/playlist.m3u8?{ST_PREFIX}starttime={start}&{ST_PREFIX}endtime={end}&{ST_PREFIX}hash={quote(token,safe='')}"
print("URL:",url[:90],"...")
req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://20.detik.com/watch/livestreaming-trans7'})
try:
    r=urllib.request.urlopen(req,timeout=15)
    print("HTTP",r.status,"-> SUCCESS via sing-box!")
    print(r.read().decode('utf-8','ignore')[:200])
except Exception as e:
    print("ERR",e)
