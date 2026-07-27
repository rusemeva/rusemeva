#!/usr/bin/env python3
"""Generate Wowza SecureToken for Trans7 and export to GITHUB_ENV."""
import hashlib, base64, time, os
from urllib.parse import quote

def main():
    secret = os.environ.get("WOWZA_SECRET", "") or (os.sys.argv[1] if len(os.sys.argv) > 1 else "")
    if not secret:
        print("❌ WOWZA_SECRET not provided")
        os.sys.exit(1)

    st_prefix = "wowzatoken"
    url_prefix = "trans7-sec/smil:"
    url_postfix = "trans7.smil"
    domain = "https://video.detik.com"

    now = int(time.time() * 1000)
    end_time = str(now + 15 * 60 * 1000)  # 15 menit
    start_time = "0"

    hash_input = (url_prefix + url_postfix + "?" + secret + "&" +
                  st_prefix + "endtime=" + end_time + "&" +
                  st_prefix + "starttime=" + start_time)
    sha = hashlib.sha256(hash_input.encode("utf-8")).digest()
    token = base64.b64encode(sha).decode("utf-8").replace("+", "-").replace("/", "_")

    url = (f"{domain}/{url_prefix}{url_postfix}/playlist.m3u8"
           f"?{st_prefix}starttime={start_time}&{st_prefix}endtime={end_time}&{st_prefix}hash={quote(token, safe='')}")

    # Export ke GITHUB_ENV
    github_env = os.environ.get("GITHUB_ENV", "")
    if github_env:
        with open(github_env, "a") as f:
            f.write(f"RESOLVED_URL={url}\n")
            f.write(f"RESOLVED_REFERER=https://20.detik.com/watch/livestreaming-trans7\n")
        print(f"✅ Exported to GITHUB_ENV")
    
    print(f"URL: {url[:80]}...")

if __name__ == "__main__":
    main()
