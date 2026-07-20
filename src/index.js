// ===== Akses privat: hanya owner yang boleh pakai bot =====
const ALLOWED_USER_ID = 2027652715;

// ===== Profil encode HEVC (preset + crf) =====
// Setiap profil punya: label, preset x265, crf, dan ringkasan untuk /setting.
const ENCODE_PROFILES = {
  speed: {
    key: 'speed',
    label: '⚡ Ultra Cepat',
    preset: 'ultrafast',
    crf: 24,
    quality: '🟡 lumayan',
    note: 'Paling kenceng, file lebih gede (1.5–2x). Aman buat rekam sangat panjang.',
  },
  balanced: {
    key: 'balanced',
    label: '🟢 Cepat (Default)',
    preset: 'veryfast',
    crf: 24,
    quality: '🟢 bagus',
    note: 'Cepat & kualitas oke. Default bot.',
  },
  quality: {
    key: 'quality',
    label: '🟢🟢 Berkualitas',
    preset: 'slow',
    crf: 22,
    quality: '🟢🟢 lebih oke',
    note: 'Lebih bersih & file ~20% lebih kecil. Encode agak lama.',
  },
  max: {
    key: 'max',
    label: '🟢🟢🟢 Maksimal',
    preset: 'slower',
    crf: 20,
    quality: '🟢🟢🟢 transparan',
    note: 'Kualitas dekat-transparan, file ~30% lebih kecil. Encode paling lama.',
  },
};
const DEFAULT_PROFILE = 'balanced';

export default {
  async fetch(request, env, ctx) {
    // Return OK immediately to prevent Telegram webhook retries
    const response = new Response('OK');

    try {
      const url = new URL(request.url);

      // === #7 Endpoint /rtcal GET: baca kalibrasi RT (realtime_x aktual, rata-rata histori) ===
      // encode.yml panggil GET ini buat dapat BASE_RT yg akurat.
      if (request.method === 'GET' && url.pathname === '/rtcal') {
        const preset = url.searchParams.get('preset') || '';
        const raw = await env.ORVELLA_KV.get(`orv:rtcal:${preset}`);
        return new Response(raw || '', { status: 200 });
      }

      if (request.method === 'POST') {
        const url = new URL(request.url);

        // === #2 Endpoint /progress: progress.py push % encode ke sini -> simpan KV ===
        if (url.pathname === '/progress') {
          try {
            const body = await request.json();
            const id = (body.id || '').toString();
            const pct = parseInt(body.pct, 10);
            const secret = (body.secret || '').toString();
            // Kalau PROGRESS_SECRET diset, wajib cocok (anti-abuse)
            if (env.PROGRESS_SECRET && secret !== env.PROGRESS_SECRET) {
              return new Response('forbidden', { status: 403 });
            }
            if (id && !isNaN(pct)) {
              // TTL 6 jam (1 encode job max) biar KV gak numpuk
              await env.ORVELLA_KV.put(`orv:${id}:pct`, String(pct), { expirationTtl: 21600 });
            }
            return new Response('OK');
          } catch (_) {
            return new Response('bad request', { status: 400 });
          }
        }

        // === #7 Endpoint /rtcal POST: simpan kalibrasi RT (realtime_x aktual) ===
        // GET sudah di-handle di awal fetch (baca nilai). Ini handler POST (tulis).
        if (url.pathname === '/rtcal') {
          try {
            const body = await request.json();
            const preset = (body.preset || '').toString();
            const rt = parseFloat(body.rt);
            const secret = (body.secret || '').toString();
            if (env.PROGRESS_SECRET && secret !== env.PROGRESS_SECRET) {
              return new Response('forbidden', { status: 403 });
            }
            if (preset && !isNaN(rt) && rt > 0) {
              const prev = parseFloat(await env.ORVELLA_KV.get(`orv:rtcal:${preset}`) || '');
              let avg = rt;
              if (!isNaN(prev) && prev > 0) {
                avg = (prev + rt) / 2;
              }
              await env.ORVELLA_KV.put(`orv:rtcal:${preset}`, avg.toFixed(4), { expirationTtl: 60*86400 });
              return new Response(`ok avg=${avg.toFixed(4)}`, { status: 200 });
            }
            return new Response('bad', { status: 400 });
          } catch (_) {
            return new Response('err', { status: 500 });
          }
        }

        if (url.pathname === '/link') {
          try {
            const body = await request.json();
            const runId = (body.run_id || '').toString();
            const orvId = (body.orv_id || '').toString();
            const secret = (body.secret || '').toString();
            if (env.PROGRESS_SECRET && secret !== env.PROGRESS_SECRET) {
              return new Response('forbidden', { status: 403 });
            }
            if (runId && orvId) {
              await env.ORVELLA_KV.put(`run:${runId}`, orvId, { expirationTtl: 21600 });
              // Reverse map: orv_id -> run_id (biar /cancel <ORV> bisa resolve run)
              await env.ORVELLA_KV.put(`orv:${orvId}:run`, String(runId), { expirationTtl: 21600 });
              return new Response('OK');
            }
            return new Response('bad', { status: 400 });
          } catch (_) {
            return new Response('err', { status: 500 });
          }
        }

        // (handler /rtcal sudah dipindah ke awal fetch: GET baca kalibrasi, POST simpan)

        const update = await request.json();

        // === #7 INLINE KEYBOARD: tangani callback_query (tombol /setting) ===
        if (update.callback_query) {
          const cb = update.callback_query;
          const cbFromId = cb.from?.id;
          const cbChatId = cb.message?.chat?.id;
          const cbData = cb.data || '';
          // Access control
          if (cbFromId !== ALLOWED_USER_ID) {
            return response;
          }
          if (cbData.startsWith('set:')) {
            const key = cbData.slice(4);
            ctx.waitUntil(handleSettingSelect(`/setting ${key}`, cbChatId, env));
            // Edit pesan biar tombol gak berkedip (opsional: biarkan)
            ctx.waitUntil(fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/answerCallbackQuery`, {
              method: 'POST', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ callback_query_id: cb.id })
            }));
          }
          return response;
        }

        // Access control — tolak siapa pun selain owner
        const incoming = update.message || update.edited_message;
        const fromId = incoming?.from?.id;
        const guardChatId = incoming?.chat?.id;
        if (fromId !== undefined && fromId !== ALLOWED_USER_ID) {
          if (guardChatId !== undefined) {
            ctx.waitUntil(sendMessage(env.BOT_TOKEN, guardChatId,
              '⛔ <b>Akses ditolak.</b>\nBot ini privat dan hanya bisa digunakan oleh pemiliknya.'
            ));
          }
          return response;
        }

        if (update.message?.text === '/start' || update.message?.text === '/help') {
          ctx.waitUntil(sendMessage(env.BOT_TOKEN, update.message.chat.id,
            '🎬 <b>Orvella Vault</b>\n\n' +
                        '<b>Commands:</b>\n' +
                        '/record &lt;url&gt; &lt;durasi&gt; — Process media\n' +
                        '/record &lt;url&gt; &lt;durasi&gt; --referer &lt;url&gt; — Process with referer\n' +
                        '/setting — Pilih profil encode HEVC\n' +
                        '/status — Cek status\n' +
                        '/cancel — Batalkan proses\n\n' +
                        '<b>Format durasi:</b>\n' +
                        '  300 / 300s → 300 detik\n' +
                        '  5m → 5 menit\n' +
                        '  2h → 2 jam\n' +
                        '  1h30m → 1 jam 30 menit\n\n' +
                        '<b>Contoh:</b>\n' +
                        '/record https://example.com/stream.m3u8 5m\n' +
                        '/record https://example.com/stream.m3u8 1h30m --referer https://example.com'
          ));
          return response;
        }

        const text = update.message?.text;
        const chatId = update.message?.chat?.id;

        if (!text || !chatId) return response;

        // Offload all handlers to waitUntil — respond to webhook instantly
        if (text.startsWith('/record')) {
          ctx.waitUntil(handleRecord(text, chatId, env));
        } else if (text === '/setting') {
          ctx.waitUntil(handleSetting(chatId, env));
        } else if (text.startsWith('/setting ')) {
          // /setting <key> — pilih profil langsung
          ctx.waitUntil(handleSettingSelect(text, chatId, env));
        } else if (text === '/status') {
          ctx.waitUntil(handleStatus(chatId, env));
        } else if (text === '/cancel') {
          ctx.waitUntil(handleCancel(chatId, env, text));
        } else if (text.startsWith('/cancel ')) {
          ctx.waitUntil(handleCancel(chatId, env, text));
        } else if (text.startsWith('/')) {
          ctx.waitUntil(sendMessage(env.BOT_TOKEN, chatId,
            '❓ Command tidak dikenali.\nKetik /start untuk melihat daftar command.'
          ));
        }

        return response;
      }

      return new Response('orvella-vault', { status: 200 });
    } catch (err) {
      return response;
    }
  }
};

// ============ SETTING (encode profile) ============

// Hitung estimasi waktu encode buat durasi tertentu.
// Ratio ultrafast:veryfast diukur nyata di mesin (32s:70s untuk 20s => 2.19x).
// Anchor: di runner GitHub 2 vCPU, veryfast 720p60 ~2.5x realtime (encode lebih
// cepat dari durasi rekam). slow ~3x lebih lambat dari veryfast, slower ~5.5x.
// Disclaimer: estimasi, bisa +-30% tergantung isi video & beban runner.
const SPEED_FACTOR = {
  speed: 2.5 * 2.19,    // ultrafast vs veryfast 2.19x
  balanced: 2.5,        // veryfast 2.5x rt
  quality: 2.5 / 3.0,   // slow ~3x lebih lambat
  max: 2.5 / 5.5,       // slower ~5.5x lebih lambat
};

function estEncodeSeconds(profileKey, recordSeconds, probeRes) {
  let f = SPEED_FACTOR[profileKey] || SPEED_FACTOR.balanced;
  if (probeRes) {
    const w = parseInt(probeRes, 10) || 1280;
    const ratio = (w * w) / (1280 * 1280);
    const r = Math.max(0.5, Math.min(3.5, ratio));
    f = f / r;
  }
  // waktu encode = durasi rekam / faktor (faktor>1 = lebih cepat dari realtime)
  let s = recordSeconds / f;
  if (s > 2 * 3600) s += 20 * 60;
  else s += 10 * 60;
  return Math.round(s);
}

async function getProfile(env, chatId) {
  try {
    const v = await env.ORVELLA_KV.get(`encprof:${chatId}`);
    if (v && ENCODE_PROFILES[v]) return v;
  } catch (_) {}
  return DEFAULT_PROFILE;
}

async function setProfile(env, chatId, key) {
  if (!ENCODE_PROFILES[key]) return false;
  try {
    await env.ORVELLA_KV.put(`encprof:${chatId}`, key);
    return true;
  } catch (_) {
    return false;
  }
}

async function handleSetting(chatId, env) {
  const current = await getProfile(env, chatId);
  let msg = '⚙️ <b>Pengaturan Encode HEVC</b>\n\n';
  msg += `Profil aktif: <b>${ENCODE_PROFILES[current].label}</b>\n\n`;
  msg += 'Pilih profil (ketik perintah):\n\n';
  for (const k of Object.keys(ENCODE_PROFILES)) {
    const p = ENCODE_PROFILES[k];
    const mark = k === current ? ' ✓' : '';
    msg += `${p.label}${mark}\n`;
    msg += `  └ /setting ${p.key}\n`;
    msg += `     preset: ${p.preset} | crf: ${p.crf} | kualitas: ${p.quality}\n`;
    msg += `     ${p.note}\n\n`;
  }
  msg += '💡 Estimasi waktu encode otomatis disesuaikan durasi rekam. Contoh pakai /record 120m.';
  await sendMessage(env.BOT_TOKEN, chatId, msg, settingsKeyboard());
}

async function handleSettingSelect(text, chatId, env) {
  const parts = text.trim().split(/\s+/);
  const key = parts[1]?.toLowerCase();
  if (!key || !ENCODE_PROFILES[key]) {
    await sendMessage(env.BOT_TOKEN, chatId,
      '❌ Profil tidak dikenal.\nGunakan: /setting speed | balanced | quality | max\n' +
      'Optional durasi: /setting quality 120m (untuk estimasi waktu encode).'
    );
    return;
  }
  const ok = await setProfile(env, chatId, key);
  const p = ENCODE_PROFILES[key];
  if (!ok) {
    await sendMessage(env.BOT_TOKEN, chatId, '⚠️ Gagal menyimpan ke KV (cek binding wrangler.toml).');
    return;
  }

  // Parse durasi opsional (misal /setting quality 120m)
  let durSec = null;
  if (parts[2]) {
    durSec = parseDuration(parts[2]);
  }

  let msg = `✅ Profil diubah ke <b>${p.label}</b>\n\n` +
    `⚙️ preset: <code>${p.preset}</code> | crf: <code>${p.crf}</code>\n` +
    `🟢 kualitas: ${p.quality}\n` +
    `📦 ${p.note}\n`;

  if (durSec && durSec > 0) {
    msg += `\n<b>Estimasi encode (rekam ${formatDuration(durSec)}):</b>\n`;
    msg += `⏱ Profil ini: ~${formatDuration(estEncodeSeconds(key, durSec))}\n\n`;
    // Bandingkan semua profil biar user tahu trade-off
    msg += `<b>Bandingkan semua profil:</b>\n`;
    for (const k of Object.keys(ENCODE_PROFILES)) {
      const pp = ENCODE_PROFILES[k];
      const e = estEncodeSeconds(k, durSec);
      const mark = k === key ? ' ▶' : '';
      msg += `• ${pp.label}${mark}: ~${formatDuration(e)} (${pp.quality})\n`;
    }
    // Peringatan kalau total (rekam + encode) vs limit job 6 jam
    const totalThis = durSec + estEncodeSeconds(key, durSec);
    const LIMIT = 6 * 3600;
    msg += `\n💡 Estimasi ±30% (tergantung isi video & beban runner GitHub).`;
    if (totalThis > LIMIT) {
      msg += `\n⛔ <b>Ke-skip:</b> total ~${formatDuration(totalThis)} LEWAT limit 6 jam. ` +
             `HEVC tidak akan diencode, original tetap dikirim.`;
    } else if (totalThis > LIMIT * 0.85) {
      msg += `\n⚠️ <b>Waspada:</b> total ~${formatDuration(totalThis)} mendekati limit 6 jam. ` +
             `HEVC bisa ke-skip kalau keburu timeout (original tetap dikirim).`;
    } else if (totalThis > LIMIT * 0.6) {
      msg += `\n⏳ Total ~${formatDuration(totalThis)} — masih aman di bawah limit 6 jam.`;
    }
  } else {
    msg += `\n💡 Ketik /setting ${key} <durasi> (contoh: /setting ${key} 120m) untuk estimasi waktu encode.`;
  }

  await sendMessage(env.BOT_TOKEN, chatId, msg);
}

// ============ COMMAND HANDLERS ============

async function handleRecord(text, chatId, env) {
  const parts = text.split(/\s+/);

  if (parts.length < 2) {
    await sendMessage(env.BOT_TOKEN, chatId,
      '❌ Format: /record &lt;url&gt; &lt;durasi&gt;\n\n' +
      '<b>Format durasi:</b>\n' +
      '  300 / 300s → 300 detik\n' +
      '  5m → 5 menit\n' +
      '  2h → 2 jam\n' +
      '  1h30m → 1 jam 30 menit\n\n' +
      'Contoh:\n' +
      '/record https://example.com/stream.m3u8 5m'
    );
    return new Response('OK');
  }

  let url = parts[1];

  // Extract optional --referer flag
  let referer = '';
  const refIdx = parts.indexOf('--referer');
  if (refIdx !== -1 && refIdx + 1 < parts.length) {
    referer = parts[refIdx + 1];
    // Remove --referer and its value from parts for duration parsing
    parts.splice(refIdx, 2);
  }

  // Parse duration: /record <url> [duration]
  let duration = 300; // default 5 menit
  if (parts.length >= 3) {
    const durStr = parts.slice(2).join(''); // join for "1h30m" without spaces
    const parsed = parseDuration(durStr);
    if (parsed === null) {
      await sendMessage(env.BOT_TOKEN, chatId,
        '❌ Format durasi salah.\n\n' +
        '<b>Contoh:</b> 300, 300s, 5m, 2h, 1h30m'
      );
      return new Response('OK');
    }
    if (parsed <= 0 || parsed > 21600) {
      await sendMessage(env.BOT_TOKEN, chatId,
        '❌ Durasi harus antara 1 detik - 21600 detik (max 6 jam).'
      );
      return new Response('OK');
    }
    duration = parsed;
  }

  // === #6 GUARD GANDA: blokir kalau ada run in_progress (rekam/encode) ===
  // Cek KV lock dulu (cepat), lalu GH API sbg otoritat.
  try {
    const running = await checkActiveRuns(env);
    if (running.length > 0) {
      let msg = '⛔ <b>Masih ada proses berjalan.</b>\n\n';
      msg += `Tunggu sampai selesai / dibatalkan dulu:\n`;
      for (const r of running.slice(0, 5)) {
        const wf = r.name || '';
        const phase = wf.includes('encode') ? '🔄 Encode HEVC' : (wf.includes('record') ? '🎬 Rekam' : wf);
        msg += `• ${phase}\n  🔗 ${r.html_url}\n`;
      }
      msg += '\nGunakan /cancel untuk membatalkan, atau /status untuk detail.';
      await sendMessage(env.BOT_TOKEN, chatId, msg);
      return new Response('OK');
    }
  } catch (_) { /* kalau GH API error, biarkan lanjut (fail-open) */ }

  // === #1 PROBE m3u8: ambil resolusi asli buat estimasi AKURAT ===
  // Worker fetch playlist, cari #EXT-X-STREAM-INF:RESOLUTION=WxH (atau variant).
  // Map resolusi -> faktor realtime (1080p60 jauh lebih berat dr 720p60).
  let probeRes = '';
  let probeFpsHint = '';
  try {
    const m3u8Resp = await fetch(url, { method: 'GET', signal: AbortSignal.timeout(10000),
      headers: { 'User-Agent': 'Mozilla/5.0', ...(referer ? { 'Referer': referer } : {}) } });
    if (m3u8Resp.ok) {
      const txt = await m3u8Resp.text();
      // Cari resolusi tertinggi di STREAM-INF
      const resMatch = txt.match(/RESOLUTION=(\d+)x(\d+)/g);
      if (resMatch) {
        let best = 0;
        for (const m of resMatch) {
          const w = parseInt(m.match(/(\d+)x/)[1], 10);
          if (w > best) best = w;
        }
        probeRes = String(best);
      }
      // Framerate hint (FRAME-RATE=60)
      const fr = txt.match(/FRAME-RATE=(\d+(\.\d+)?)/);
      if (fr) probeFpsHint = fr[1];
    }
  } catch (_) { /* probe gagal = fallback estimasi default */ }

  // Faktor realtime berdasarkan resolusi (720p baseline 2.5x; makin tinggi makin lambat)
  function rtFactorForRes(resStr, baseFactor) {
    const w = parseInt(resStr, 10) || 1280;
    // 720p(1280) baseline 1.0; 1080p(1920) ~1.8x lebih lambat; 480p ~0.6x
    const ratio = (w * w) / (1280 * 1280); // area piksel relatif thd 720p
    // clamp biar gak meledak
    const r = Math.max(0.5, Math.min(3.5, ratio));
    return baseFactor / r;
  }

  // Validate URL
  if (!url.startsWith('http')) {
    await sendMessage(env.BOT_TOKEN, chatId, '❌ URL harus dimulai dengan http:// atau https://');
    return new Response('OK');
  }

  // Check URL reachable
  try {
    const headers = { method: 'HEAD', signal: AbortSignal.timeout(10000) };
    if (referer) headers.headers = { 'Referer': referer };
    const resp = await fetch(url, headers);
    if (!resp.ok) {
      await sendMessage(env.BOT_TOKEN, chatId,
        `❌ URL tidak bisa diakses (HTTP ${resp.status})\nPastikan link masih valid.`
      );
      return new Response('OK');
    }
  } catch {
    await sendMessage(env.BOT_TOKEN, chatId, '❌ Gagal mengakses URL. Pastikan link benar.');
    return new Response('OK');
  }

  // Ambil profil encode aktif
  const profileKey = await getProfile(env, chatId);
  const profile = ENCODE_PROFILES[profileKey];

  // Generate filename (WIB timezone)
  const now = new Date();
  const wib = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Jakarta' }));
  const pad = n => String(n).padStart(2, '0');
  const ts = `${wib.getFullYear()}-${pad(wib.getMonth()+1)}-${pad(wib.getDate())}T${pad(wib.getHours())}-${pad(wib.getMinutes())}-${pad(wib.getSeconds())}`;
  const filename = `recording-${ts}-${formatDurationShort(duration)}.mp4`;

  // === #4 ESTIMASI SEBELUM REKAM: hitung & tampilkan di notif mulai ===
  const recSec = duration;
  const encSec = estEncodeSeconds(profileKey, recSec, probeRes);
  const totalSec = recSec + encSec;
  const LIMIT = 6 * 3600;
  let estLine = `⏱ Estimasi: rekam ${formatDuration(recSec)} + encode ~${formatDuration(encSec)} (total ~${formatDuration(totalSec)})`;
  if (totalSec > LIMIT) {
    estLine += `\n⛔ Total LEWAT 6 jam — HEVC bisa ke-skip (auto-downgrade di encode.yml otomatis turun preset).`;
  } else if (totalSec > LIMIT * 0.85) {
    estLine += `\n⚠️ Mendekati limit 6 jam — HEVC bisa ke-potong (original tetap dikirim).`;
  }

  // Trigger GitHub Actions
  const trig = await triggerGitHubActions(env, url, duration, chatId, filename, referer, profile);
  const orvId = trig.orvId;

  if (trig.resp.ok) {
    let msg = '✅ <b>Rekaman dimulai!</b>\n\n' +
      `🆔 ID: <code>${orvId}</code>\n` +
      `🔗 URL: <code>${escapeHtml(url)}</code>\n` +
      `⏱ Durasi: ${formatDuration(duration)}\n` +
      `📦 File: ${filename}\n` +
      `⚙️ Encode: <b>${profile.label}</b> (${profile.preset}, crf ${profile.crf})\n`;
    if (referer) msg += `🔗 Referer: <code>${escapeHtml(referer)}</code>\n`;
    if (probeRes) msg += `🖥 Sumber: ${probeRes}p${probeFpsHint ? ' @' + probeFpsHint + 'fps' : ''}\n`;
    msg += `${estLine}\n\n☁️ Hasil di-upload ke GitHub Release setelah selesai, lalu dikirim ke Telegram.\n\nSimpan ID ini untuk /cancel <id> kalau mau membatalkan.`;
    await sendMessage(env.BOT_TOKEN, chatId, msg);
  } else {
    const errText = await trig.resp.text();
    await sendMessage(env.BOT_TOKEN, chatId,
      `❌ Gagal trigger rekaman.\nError: ${escapeHtml(errText.slice(0, 500))}`
    );
  }

  return new Response('OK');
}

async function handleStatus(chatId, env) {
  try {
    const resp = await ghApi(env, `actions/runs?per_page=8`);
    const data = await resp.json();

    if (!data.workflow_runs?.length) {
      await sendMessage(env.BOT_TOKEN, chatId, '📭 Tidak ada rekaman aktif.');
      return new Response('OK');
    }

    const active = data.workflow_runs.filter(r => r.status === 'in_progress' || r.status === 'queued');
    if (active.length === 0) {
      const last = data.workflow_runs[0];
      const emoji = last.conclusion === 'success' ? '✅' : last.conclusion === 'failure' ? '❌' : last.conclusion === 'cancelled' ? '🚫' : '📭';
      await sendMessage(env.BOT_TOKEN, chatId,
        `${emoji} <b>Tidak ada rekaman aktif</b>\n\n` +
        `Terakhir: ${last.status} (${last.conclusion || '-'})\n` +
        `🔗 ${last.html_url}`
      );
      return new Response('OK');
    }

    let msg = `⏳ <b>${active.length} proses aktif:</b>\n\n`;
    for (const run of active) {
      const wf = run.name || '';
      const phase = wf.includes('encode') ? '🔄 Encode HEVC' : (wf.includes('record') ? '🎬 Rekam' : '⚙️ ' + wf);
      const created = new Date(run.created_at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta', hour: '2-digit', minute: '2-digit' });
      const elapsed = Math.round((Date.now() - new Date(run.created_at)) / 1000);
      msg += `• ${phase}\n`;
      msg += `  ⏱ ${formatDuration(elapsed)} · mulai ${created} WIB\n`;
      msg += `  🔗 ${run.html_url}\n`;

      // Kalau encode lagi jalan -> ambil progress % dari KV (di-push progress.py)
      if (wf.includes('encode')) {
        try {
          const jobsResp = await ghApi(env, `actions/runs/${run.id}/jobs?per_page=5`);
          const jobs = await jobsResp.json();
          const job = jobs.workflow_runs?.jobs?.[0] || jobs.jobs?.[0];
          if (job?.steps) {
            const enc = job.steps.find(s => s.name && s.name.toLowerCase().includes('encode to hevc'));
            if (enc) {
              const st = enc.status;
              const em = enc.conclusion || '';
              let pct = '';
              if (st === 'in_progress') {
                pct = ' ⏳ (berjalan)';
                // Baca % terakhir dari KV: orv:<id>:pct (di-push progress.py tiap 5%)
                try {
                  const orvId = run.display_title?.match(/ORV-[a-z0-9-]+/i)?.[0]
                    || (await env.ORVELLA_KV.get(`run:${run.id}`));
                  if (orvId) {
                    const kvPct = await env.ORVELLA_KV.get(`orv:${orvId}:pct`);
                    if (kvPct !== null && kvPct !== undefined && kvPct !== '') {
                      const n = parseInt(kvPct, 10);
                      if (!isNaN(n) && n >= 0) pct = ` 🔄 ${n}%`;
                    }
                  }
                } catch (_) {}
              }
              else if (st === 'completed' && em === 'success') pct = ' ✅';
              else if (st === 'completed' && em === 'failure') pct = ' ❌';
              msg += `  📊 Status: ${st}${pct}\n`;
            }
          }
        } catch (_) {
          // ignore: progress detail gak krusial
        }
      }
      msg += `\n`;
    }
    await sendMessage(env.BOT_TOKEN, chatId, msg);
  } catch (err) {
    await sendMessage(env.BOT_TOKEN, chatId, `❌ Error: ${escapeHtml(err.message)}`);
  }
  return new Response('OK');
}

async function handleCancel(chatId, env, text) {
  // Cari ID opsional: /cancel ORV-XXXX atau /cancel <run_url>
  let targetId = '';
  const parts = (text || '').trim().split(/\s+/);
  if (parts[1]) targetId = parts[1];

  try {
    const resp = await ghApi(env, 'actions/runs?per_page=20');
    const data = await resp.json();
    const inProgress = (data.workflow_runs || []).filter(r => r.status === 'in_progress');

    if (!inProgress.length) {
      await sendMessage(env.BOT_TOKEN, chatId, '📭 Tidak ada rekaman yang sedang berjalan.');
      return new Response('OK');
    }

    // === #2 /cancel <id>: filter by ID biar lebih presisi ===
    if (targetId) {
      // Coba resolve dari KV dulu (ID = orv:ID)
      let matched = [];
      try {
        const meta = await env.ORVELLA_KV.get(`orv:${targetId}`);
        if (meta) {
          const m = JSON.parse(meta);
          // KV simpan chat_id; cocokkan dgn chat pengirim
          if (m.chat_id && String(m.chat_id) !== String(chatId)) {
            await sendMessage(env.BOT_TOKEN, chatId,
              `⛔ ID <code>${targetId}</code> bukan milikmu.`);
            return new Response('OK');
          }
        }
      } catch (_) {}

      // Resolve run IDs dari reverse-map KV (orv_id -> run_id)
      // encode tulis `orv:<id>:run`, record tulis `orv:<id>:recrun`
      try {
        const encRun = await env.ORVELLA_KV.get(`orv:${targetId}:run`);
        const recRun = await env.ORVELLA_KV.get(`orv:${targetId}:recrun`);
        const ids = [encRun, recRun].filter(Boolean);
        if (ids.length) {
          for (const rid of ids) {
            const run = inProgress.find(r => String(r.id) === String(rid));
            if (run) matched.push(run);
          }
        }
      } catch (_) {}

      // Kalau reverse-map kosong, fallback: match by run-id di URL / substring
      if (!matched.length) {
        const t = targetId.replace(/^.*\/runs\//, '').replace(/[^A-Za-z0-9]/g, '');
        matched = inProgress.filter(r =>
          String(r.id) === t ||
          (r.html_url && r.html_url.includes(t)) ||
          (r.name && r.name.toLowerCase().includes(targetId.toLowerCase()))
        );
      }

      if (!matched.length) {
        await sendMessage(env.BOT_TOKEN, chatId,
          `⚠️ Tidak ada proses aktif dengan ID <code>${targetId}</code>.\nGunakan /status untuk lihat daftar ID/run.`);
        return new Response('OK');
      }
      for (const run of matched) {
        await ghApi(env, `actions/runs/${run.id}/cancel`, 'POST');
      }
      await sendMessage(env.BOT_TOKEN, chatId,
        `🚫 <b>${matched.length} rekaman dibatalkan.</b>\n🔗 ${matched[0].html_url}`);
      return new Response('OK');
    }

    // Fallback: cancel SEMUA in_progress (perilaku lama)
    for (const run of inProgress) {
      await ghApi(env, `actions/runs/${run.id}/cancel`, 'POST');
    }
    await sendMessage(env.BOT_TOKEN, chatId,
      `🚫 <b>${inProgress.length} rekaman dibatalkan.</b>`);
  } catch (err) {
    await sendMessage(env.BOT_TOKEN, chatId, `❌ Error: ${escapeHtml(err.message)}`);
  }
  return new Response('OK');
}

// ============ DURATION PARSING ============

function parseDuration(str) {
  str = str.trim().toLowerCase();

  // Pure number → seconds (e.g. "300" or "300s")
  if (/^\d+s?$/.test(str)) {
    return parseInt(str);
  }

  // Pattern: 1h30m, 2h, 30m, 1h30s, 1h30m15s
  let total = 0;
  let remaining = str;

  const hMatch = remaining.match(/^(\d+)h/);
  if (hMatch) {
    total += parseInt(hMatch[1]) * 3600;
    remaining = remaining.slice(hMatch[0].length);
  }

  const mMatch = remaining.match(/^(\d+)m/);
  if (mMatch) {
    total += parseInt(mMatch[1]) * 60;
    remaining = remaining.slice(mMatch[0].length);
  }

  const sMatch = remaining.match(/^(\d+)s?$/);
  if (sMatch) {
    total += parseInt(sMatch[1]);
    remaining = '';
  }

  if (remaining || total === 0) return null;
  return total;
}

// ============ HELPERS ============

// ============ ORV ID GENERATOR ============
// ID unik per aksi: ORV-<base36 timestamp>-<rand>
// Dipakai di /record, /cancel, notif biar user gampang rujuk.
function genOrvId() {
  const ts = Date.now().toString(36).toUpperCase();
  const rnd = Math.random().toString(36).slice(2, 6).toUpperCase();
  return `ORV-${ts}-${rnd}`;
}

async function triggerGitHubActions(env, m3u8Url, duration, chatId, filename, referer = '', profile = null) {
  const orvId = genOrvId();
  // Simpan mapping ID -> chat (biar /status /cancel gampang)
  try {
    await env.ORVELLA_KV.put(`orv:${orvId}`, JSON.stringify({
      chat_id: String(chatId),
      type: 'record',
      created_at: new Date().toISOString(),
    }), { expirationTtl: 60 * 60 * 24 * 7 }); // 7 hari
  } catch (_) { /* KV optional */ }

  const payload = {
    m3u8_url: m3u8Url,
    duration: duration,
    chat_id: String(chatId),
    human_duration: formatDuration(duration),
    duration_label: formatDurationShort(duration),
    filename: filename,
    orv_id: orvId,
  };
  if (referer) payload.referer = referer;
  // Sisipkan profil encode (fallback ke default kalau null)
  const p = profile || ENCODE_PROFILES[DEFAULT_PROFILE];
  payload.hevc_preset = p.preset;
  payload.hevc_crf = p.crf;
  payload.encode_profile = p.key;

  return {
    resp: fetch(
      `https://api.github.com/repos/${env.GH_OWNER}/${env.GH_REPO}/dispatches`,
      {
        method: 'POST',
        headers: {
          'Authorization': `token ${env.GH_TOKEN}`,
          'Accept': 'application/vnd.github.v3+json',
          'User-Agent': 'orvella-vault'
        },
        body: JSON.stringify({
            event_type: 'record-request',
            client_payload: payload
          })
      }
    ),
    orvId,
  };
}

async function checkActiveRuns(env) {
  try {
    const resp = await ghApi(env, 'actions/runs?per_page=10');
    const data = await resp.json();
    return (data.workflow_runs || []).filter(r =>
      r.status === 'in_progress' || r.status === 'queued' || r.status === 'pending');
  } catch (_) {
    return [];
  }
}

function ghApi(env, path, method = 'GET') {
  return fetch(
    `https://api.github.com/repos/${env.GH_OWNER}/${env.GH_REPO}/${path}`,
    {
      method,
      headers: {
        'Authorization': `token ${env.GH_TOKEN}`,
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'orvella-vault'
      }
    }
  );
}

async function sendMessage(token, chatId, text, replyMarkup = null) {
  // Split messages > 4096 chars
  const parts = splitMessage(text, 4096);
  for (const part of parts) {
    const body = { chat_id: chatId, text: part, parse_mode: 'HTML' };
    if (replyMarkup) body.reply_markup = replyMarkup;
    await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
  }
}

function settingsKeyboard() {
  const keys = Object.keys(ENCODE_PROFILES);
  const row = keys.map(k => ({ text: ENCODE_PROFILES[k].label, callback_data: `set:${k}` }));
  return { inline_keyboard: [row] };
}

function splitMessage(text, maxLen) {
  const parts = [];
  while (text.length > maxLen) {
    let idx = text.lastIndexOf('\n', maxLen);
    if (idx <= 0) idx = maxLen;
    parts.push(text.slice(0, idx));
    text = text.slice(idx);
  }
  if (text) parts.push(text);
  return parts;
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function formatDuration(seconds) {
  if (seconds < 60) return `${seconds} detik`;
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return s ? `${m} menit ${s} detik` : `${m} menit`;
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  let parts = `${h} jam`;
  if (m) parts += ` ${m} menit`;
  if (s) parts += ` ${s} detik`;
  return parts;
}

function formatDurationShort(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  let parts = '';
  if (h) parts += `${h}h`;
  if (m) parts += `${m}m`;
  if (s || !parts) parts += `${s}s`;
  return parts;
}
