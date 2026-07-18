from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(headless=True, channel='chrome')
    ctx=b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg=ctx.new_page()
    pg.goto("https://sevenhub.id/live", wait_until='domcontentloaded', timeout=45000)
    pg.wait_for_timeout(5000)
    cookies=pg.context.cookies()
    dm=[c for c in cookies if 'dailymotion' in c.get('domain','')]
    print("cookies:", [(c['name'], c['value'][:20]) for c in dm])
    # ambil m3u8 dari API lalu fetch pakai cookie
    import urllib.request, json
    api='https://geo.dailymotion.com/video/x8qckyq.json?legacy=true&embedder=https%3A%2F%2Fsevenhub.id%2Flive&geo=1&player-id=x15a7g&publisher-id=x2virdk&locale=id&dmV1st=00a6db6f-0d2b-e7da-4b68-8da7135d0d0f&dmTs=95300&is_native_app=0&app=idm.internet.download.manager.plus&dmViewId=1jtnb2eb9cc961fbd77&parallelCalls=1'
    req=urllib.request.Request(api, headers={'User-Agent':'Mozilla/5.0','Referer':'https://sevenhub.id/live'})
    d=json.loads(urllib.request.urlopen(req, timeout=20).read())
    m3u8=d['qualities']['auto'][0]['url']
    ckin='; '.join(f"{c['name']}={c['value']}" for c in dm)
    req2=urllib.request.Request(m3u8, headers={'User-Agent':'Mozilla/5.0','Referer':'https://sevenhub.id/live','Cookie':ckin})
    try:
        body=urllib.request.urlopen(req2, timeout=20).read()
        print('WITH COOKIE OK size', len(body))
    except Exception as e:
        print('WITH COOKIE FAIL', str(e)[:60])
    b.close()
