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
      if (request.method === 'POST') {
        const update = await request.json();

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
          ctx.waitUntil(handleCancel(chatId, env));
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
// Ratio diukur nyata di mesin (ultrafast 32s / veryfast 70s untuk 20s video => 2.19x).
// Anchor: di runner GitHub 2 vCPU, veryfast 720p60 ~1.5x realtime (konservatif).
// Disclaimer: estimasi, bisa +-30% tergantung isi video & beban runner.
const SPEED_FACTOR = {
  speed: 1.5 * 2.19,    // ultrafast vs veryfast 2.19x, veryfast 1.5x rt
  balanced: 1.5,        // veryfast 1.5x rt
  quality: 1.5 / 3.0,   // slow ~3x lebih lambat dari veryfast
  max: 1.5 / 5.5,       // slower ~5.5x lebih lambat dari veryfast
};

function estEncodeSeconds(profileKey, recordSeconds) {
  const f = SPEED_FACTOR[profileKey] || SPEED_FACTOR.balanced;
  // waktu encode = durasi rekam / faktor (faktor>1 = lebih cepat dari realtime)
  return Math.round(recordSeconds / f);
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
  await sendMessage(env.BOT_TOKEN, chatId, msg);
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
    // Peringatan kalau total (rekam + encode) mendekati limit job 6 jam
    const totalThis = durSec + estEncodeSeconds(key, durSec);
    const LIMIT = 6 * 3600;
    msg += `\n💡 Estimasi ±30% (tergantung isi video & beban runner GitHub).`;
    if (totalThis > LIMIT * 0.85) {
      msg += `\n⚠️ <b>Waspada:</b> total rekam + encode ~${formatDuration(totalThis)} ` +
             `mendekati limit job 6 jam. HEVC bisa ke-skip kalau keburu timeout ` +
             `(original tetap dikirim).`;
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

  // Trigger GitHub Actions
  const ghResp = await triggerGitHubActions(env, url, duration, chatId, filename, referer, profile);

  if (ghResp.ok) {
    let msg = '✅ <b>Rekaman dimulai!</b>\n\n' +
      `🔗 URL: <code>${escapeHtml(url)}</code>\n` +
      `⏱ Durasi: ${formatDuration(duration)}\n` +
      `📦 File: ${filename}\n` +
      `⚙️ Encode: <b>${profile.label}</b> (${profile.preset}, crf ${profile.crf})\n`;
    if (referer) msg += `🔗 Referer: <code>${escapeHtml(referer)}</code>\n`;
    msg += '☁️ Hasil di-upload ke GitHub Release setelah selesai, lalu dikirim ke Telegram.\n\nKetik /status untuk cek progress.';
    await sendMessage(env.BOT_TOKEN, chatId, msg);
  } else {
    const errText = await ghResp.text();
    await sendMessage(env.BOT_TOKEN, chatId,
      `❌ Gagal trigger rekaman.\nError: ${escapeHtml(errText.slice(0, 500))}`
    );
  }

  return new Response('OK');
}

async function handleStatus(chatId, env) {
  try {
    const resp = await ghApi(env, `actions/runs?per_page=5`);
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

    let msg = `⏳ <b>${active.length} rekaman aktif:</b>\n\n`;
    for (const run of active) {
      const created = new Date(run.created_at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' });
      const elapsed = Math.round((Date.now() - new Date(run.created_at)) / 1000);
      msg += `• ${run.status} — ${formatDuration(elapsed)} — ${created}\n`;
    }
    await sendMessage(env.BOT_TOKEN, chatId, msg);
  } catch (err) {
    await sendMessage(env.BOT_TOKEN, chatId, `❌ Error: ${escapeHtml(err.message)}`);
  }
  return new Response('OK');
}

async function handleCancel(chatId, env) {
  try {
    const resp = await ghApi(env, 'actions/runs?per_page=5');
    const data = await resp.json();
    const inProgress = (data.workflow_runs || []).filter(r => r.status === 'in_progress');

    if (!inProgress.length) {
      await sendMessage(env.BOT_TOKEN, chatId, '📭 Tidak ada rekaman yang sedang berjalan.');
      return new Response('OK');
    }

    for (const run of inProgress) {
      await ghApi(env, `actions/runs/${run.id}/cancel`, 'POST');
    }

    await sendMessage(env.BOT_TOKEN, chatId, `🚫 <b>${inProgress.length} rekaman dibatalkan.</b>`);
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

async function triggerGitHubActions(env, m3u8Url, duration, chatId, filename, referer = '', profile = null) {
  const payload = {
    m3u8_url: m3u8Url,
    duration: duration,
    chat_id: String(chatId),
    human_duration: formatDuration(duration),
    duration_label: formatDurationShort(duration),
    filename: filename,
  };
  if (referer) payload.referer = referer;
  // Sisipkan profil encode (fallback ke default kalau null)
  const p = profile || ENCODE_PROFILES[DEFAULT_PROFILE];
  payload.hevc_preset = p.preset;
  payload.hevc_crf = p.crf;
  payload.encode_profile = p.key;

  return fetch(
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
  );
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

async function sendMessage(token, chatId, text) {
  // Split messages > 4096 chars
  const parts = splitMessage(text, 4096);
  for (const part of parts) {
    await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, text: part, parse_mode: 'HTML' })
    });
  }
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
