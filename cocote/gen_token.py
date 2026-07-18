#!/usr/bin/env python3
"""Generate detik Wowza SecureToken untuk Trans7 dan rekam via ffmpeg."""
import hashlib, base64, time, subprocess, sys
from urllib.parse import quote

# Config dari detikVideo.core.js (Trans7)
ST_SHSC = "258eed02421df5e2"  # secret untuk video.detik.com (Trans7)
ST_PREFIX = "wowzatoken"
ST_URL_PREFIX = "trans7-sec/smil:"
ST_URL_POSTFIX = "trans7.smil"  # PENTING: ada di input hash!
ST_DOMAIN = "https://video.detik.com"  # tetap video.detik.com (bukan ezdrm)
ST_EXPIRE_MIN = 15
ST_ENABLE_ENDTIME_ONLY = True  # stEnableEndTimeOnly=true

def gen_token():
    now = int(time.time() * 1000)
    end_time = str(now + ST_EXPIRE_MIN * 60 * 1000)
    start_time = "0" if ST_ENABLE_ENDTIME_ONLY else str(now)
    hash_input = (ST_URL_PREFIX + ST_URL_POSTFIX + "?" + ST_SHSC + "&" +
                  ST_PREFIX + "endtime=" + end_time + "&" +
                  ST_PREFIX + "starttime=" + start_time)
    sha = hashlib.sha256(hash_input.encode('utf-8')).digest()
    token = base64.b64encode(sha).decode('utf-8')
    # Wowza: + → -, / → _, PADDING DIPERTAHANKAN (CryptoJS Base64 keep padding)
    token = token.replace('+', '-').replace('/', '_')
    url = (f"{ST_DOMAIN}/{ST_URL_PREFIX}{ST_URL_POSTFIX}/playlist.m3u8"
           f"?{ST_PREFIX}starttime={start_time}&{ST_PREFIX}endtime={end_time}&{ST_PREFIX}hash={quote(token, safe='')}")
    return url, hash_input

if __name__ == '__main__':
    url, hinput = gen_token()
    print("Hash input:", hinput)
    print("Token URL :", url)
    print("\nTesting with curl...")
    # Test master playlist
    import urllib.request
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36',
        'Referer': 'https://20.detik.com/watch/livestreaming-trans7'
    })
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        body = resp.read().decode('utf-8', 'ignore')
        print("HTTP", resp.status)
        print(body[:400])
    except Exception as e:
        print("ERR", e)
