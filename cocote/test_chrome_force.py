from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel='chrome',
                          args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36')
    pg = ctx.new_page()
    pg.goto('https://20.detik.com/watch/livestreaming-trans7', wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(10000)
    # Cek HLS + paksa play
    diag = pg.evaluate('''() => {
      const v = document.querySelector(\"video\");
      const out = {hasVideo: !!v};
      if(v){
        out.src = v.currentSrc||v.src;
        out.hls = v.hls ? 'yes' : 'no';
        v.muted = true;
        v.play().catch(e=>out.playErr=e.message);
        out.paused = v.paused;
      }
      // Cari global hls
      out.winHls = typeof window.hls !== 'undefined';
      return out;
    }''')
    print('DIAG:', diag)
    pg.wait_for_timeout(15000)
    info = pg.evaluate('''() => {
      const v = document.querySelector(\"video\");
      return {w:v.videoWidth,h:v.videoHeight,paused:v.paused,rs:v.readyState,ct:Math.round(v.currentTime*10)/10,err:v.error&&v.error.code};
    }''')
    print('AFTER 15s:', info)
    b.close()
