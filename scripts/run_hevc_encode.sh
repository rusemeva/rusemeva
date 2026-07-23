#!/usr/bin/env bash
set -euo pipefail
# #7 mulai timer kalibrasi
ENC_START=$SECONDS
FILE="${ORIG_FILE}"
HEVC_FILE="${FILE%.mp4}-h265-10bit.mp4"
FFMPEG_STATIC="${FFMPEG_STATIC}"
HEVC_PRESET="${HEVC_PRESET}"
HEVC_CRF="${HEVC_CRF}"
CHOSEN="${CHOSEN_PRESET}"
if [ "$CHOSEN" != "$HEVC_PRESET" ]; then
  MSG="🔻 <b>Auto-downgrade!</b> Preset <code>$CHOSEN</code> estimasi &gt;5j50m, otomatis turun ke <code>$HEVC_PRESET</code> (CRF $HEVC_CRF) biar muat 6 jam."
else
  MSG="🎚 Encode pakai preset <code>$HEVC_PRESET</code> (CRF $HEVC_CRF)."
fi
CHAT_ID="$CHAT_ID" FILENAME="$FILE" TG_API_URL="$TG_API_URL" BOT_TOKEN="$BOT_TOKEN" python3 scripts/send_message.py "$MSG" || true
echo "🎞 Encoding HEVC 10-bit (preset=${HEVC_PRESET}, CRF ${HEVC_CRF}) dari original..."
echo "📦 Original: $(ls -lh "$FILE" | awk '{print $5}')"

source scripts/encode_policy.sh
REQ_DUR="${REQUESTED_DURATION}"
SRC_DUR_INT="${DURATION_SEC}"
case "$SRC_DUR_INT" in ''|*[!0-9]*) SRC_DUR_INT=0 ;; esac
REAL_SRC_INT=$(probe_duration_int "$FILE" || true)
if [ "${REAL_SRC_INT:-0}" -gt 0 ] 2>/dev/null; then
  SRC_DUR_INT=$REAL_SRC_INT
elif [ "${SRC_DUR_INT:-0}" -le 0 ] 2>/dev/null; then
  case "$REQ_DUR" in ''|*[!0-9]*) SRC_DUR_INT=60 ;; *) SRC_DUR_INT=$REQ_DUR ;; esac
  [ "$SRC_DUR_INT" -le 0 ] 2>/dev/null && SRC_DUR_INT=60
fi
AUDIO_BPS=$(probe_audio_bps "$FILE" || echo 0)
MAXRATE_K=$(video_maxrate_k "$AUDIO_BPS")
BUFSIZE_K=$(( MAXRATE_K * 2 ))
echo "dur=${SRC_DUR_INT}s audio=${AUDIO_BPS} maxrate=${MAXRATE_K}k"

# === SCENE-AWARE CRF ===
# Probe 5 cuplikan @8s: encode mini ultrafast di CRF basis, ukur bytes/s.
# Konten ramai/gelap (bytes/s tinggi) → CRF turun (lebih bagus).
# Konten sepi/talking-head (bytes/s rendah) → CRF naik (lebih hemat).
# Clamp final 22..28 biar tetap di sweet-spot ~1.2–1.4 Mbps @720p.
BASE_CRF=$HEVC_CRF
SCENE_DELTA=0
if [ "$SRC_DUR_INT" -ge 60 ] 2>/dev/null; then
  echo "🧠 Scene-aware probe (5x8s)..."
  SUM_BPS=0
  N_OK=0
  for frac in 10 30 50 70 90; do
    SS=$(( SRC_DUR_INT * frac / 100 ))
    # jangan mepet EOF
    MAX_SS=$(( SRC_DUR_INT - 10 ))
    [ "$SS" -gt "$MAX_SS" ] && SS=$MAX_SS
    [ "$SS" -lt 0 ] && SS=0
    SAMPLE="/tmp/rusemeva_scene_${frac}.mp4"
    "$FFMPEG_STATIC" -hide_banner -y -ss "$SS" -t 8 -i "$FILE" \
      -c:v libx265 -profile:v main10 -pix_fmt yuv420p10le \
      -crf ${BASE_CRF} -preset ultrafast -an "$SAMPLE" >/tmp/rusemeva_scene_probe.log 2>&1 || true
    if [ -s "$SAMPLE" ]; then
      BY=$(stat -c%s "$SAMPLE" 2>/dev/null || wc -c < "$SAMPLE")
      # bytes per second of sample
      BPS=$(( BY / 8 ))
      SUM_BPS=$(( SUM_BPS + BPS ))
      N_OK=$(( N_OK + 1 ))
      echo "   • t=${SS}s sample=${BY}B (~${BPS} B/s)"
    fi
    rm -f "$SAMPLE" 2>/dev/null || true
  done
  if [ "$N_OK" -gt 0 ]; then
    AVG_BPS=$(( SUM_BPS / N_OK ))
    echo "🧠 Scene avg complexity: ${AVG_BPS} B/s (n=$N_OK) base_crf=$BASE_CRF"
    # Kalibrasi kasar 720p@CRF24 ultrafast sample:
    # sepi < 40k B/s, normal 40–90k, ramai > 90k
    if [ "$AVG_BPS" -gt 90000 ]; then
      SCENE_DELTA=-2
      SCENE_LABEL="ramai/kompleks"
    elif [ "$AVG_BPS" -gt 60000 ]; then
      SCENE_DELTA=-1
      SCENE_LABEL="agak ramai"
    elif [ "$AVG_BPS" -lt 35000 ]; then
      SCENE_DELTA=1
      SCENE_LABEL="sepi/talking-head"
    else
      SCENE_DELTA=0
      SCENE_LABEL="normal"
    fi
    HEVC_CRF=$(( BASE_CRF + SCENE_DELTA ))
    [ "$HEVC_CRF" -lt 22 ] && HEVC_CRF=22
    [ "$HEVC_CRF" -gt 28 ] && HEVC_CRF=28
    echo "🧠 Scene-aware: ${SCENE_LABEL} → CRF ${BASE_CRF} + (${SCENE_DELTA}) = ${HEVC_CRF}"
    if [ "$HEVC_CRF" != "$BASE_CRF" ]; then
      CHAT_ID="$CHAT_ID" TG_API_URL="$TG_API_URL" BOT_TOKEN="$BOT_TOKEN" python3 scripts/send_message.py \
        "🧠 <b>Scene-aware:</b> konten <code>${SCENE_LABEL}</code> → CRF <code>${BASE_CRF}</code> → <code>${HEVC_CRF}</code> (jaga ~1.3 Mbps, anti-buram di bagian penting)." || true
    fi
  else
    echo "⚠️ Scene probe gagal — pakai CRF basis $BASE_CRF"
  fi
else
  echo "ℹ️ Video pendek (<60s) — skip scene-aware"
fi

# x265 adaptive quant: alokasi bit lebih pintar per-block (dalam-frame scene-aware)

# === LIVE-FRIENDLY MODE (siaran TV) ===
# Aktif jika: profil /setting live  ATAU auto-detect chrome statis (logo/ticker).
# Efek: AQ lebih agresif di detail, denoise ringan, jaga tengah, hemat area statis.
ENCODE_PROFILE="${ENCODE_PROFILE}"
LIVE_MODE=0
LIVE_REASON=""
if [ "$ENCODE_PROFILE" = "live" ]; then
  LIVE_MODE=1
  LIVE_REASON="profil /setting live"
else
  # Auto-detect: bandingkan stabilitas sudut vs tengah di 5 timestamp
  # Kalau sudut jauh lebih stabil → kemungkinan logo/ticker TV.
  if [ "${SRC_DUR_INT:-0}" -ge 120 ] 2>/dev/null; then
    echo "📺 Live-detect: cek chrome statis (logo/ticker)..."
    CORNER_DIFF=0
    CENTER_DIFF=0
    N_PAIR=0
    PREV_C=""
    PREV_M=""
    for frac in 15 35 55 75 90; do
      SS=$(( SRC_DUR_INT * frac / 100 ))
      MAX_SS=$(( SRC_DUR_INT - 2 ))
      [ "$SS" -gt "$MAX_SS" ] && SS=$MAX_SS
      FC="/tmp/rusemeva_live_c_${frac}.png"
      FM="/tmp/rusemeva_live_m_${frac}.png"
      # sudut kiri-atas 12%
      "$FFMPEG_STATIC" -hide_banner -y -ss "$SS" -i "$FILE" -vframes 1 \
        -vf "crop=iw*0.12:ih*0.12:0:0,scale=64:64,format=gray" "$FC" >/dev/null 2>&1 || true
      # tengah 30%
      "$FFMPEG_STATIC" -hide_banner -y -ss "$SS" -i "$FILE" -vframes 1 \
        -vf "crop=iw*0.30:ih*0.30:(iw-ow)/2:(ih-oh)/2,scale=64:64,format=gray" "$FM" >/dev/null 2>&1 || true
      if [ -n "$PREV_C" ] && [ -s "$FC" ] && [ -s "$PREV_C" ]; then
        # mean abs diff via ffmpeg psnr (lower=more similar/static)
        DC=$("$FFMPEG_STATIC" -hide_banner -i "$PREV_C" -i "$FC" -filter_complex "psnr" -f null - 2>&1 | sed -n 's/.*mse_avg:\([0-9.]*\).*/\1/p' | tail -1)
        DM=$("$FFMPEG_STATIC" -hide_banner -i "$PREV_M" -i "$FM" -filter_complex "psnr" -f null - 2>&1 | sed -n 's/.*mse_avg:\([0-9.]*\).*/\1/p' | tail -1)
        DC=${DC%.*}; DM=${DM%.*}
        [ -z "$DC" ] && DC=0
        [ -z "$DM" ] && DM=0
        CORNER_DIFF=$(( CORNER_DIFF + DC ))
        CENTER_DIFF=$(( CENTER_DIFF + DM ))
        N_PAIR=$(( N_PAIR + 1 ))
        echo "   • t=${SS}s corner_mse~$DC center_mse~$DM"
      fi
      PREV_C=$FC; PREV_M=$FM
    done
    rm -f /tmp/rusemeva_live_c_*.png /tmp/rusemeva_live_m_*.png 2>/dev/null || true
    if [ "$N_PAIR" -gt 0 ]; then
      AVG_C=$(( CORNER_DIFF / N_PAIR ))
      AVG_M=$(( CENTER_DIFF / N_PAIR ))
      echo "📺 Live-detect avg: corner_mse=$AVG_C center_mse=$AVG_M"
      # sudut statis (mse kecil) + tengah lebih dinamis → siaran TV
      if [ "$AVG_C" -le 25 ] && [ "$AVG_M" -ge $(( AVG_C * 3 + 5 )) ]; then
        LIVE_MODE=1
        LIVE_REASON="auto-detect chrome TV (logo/ticker)"
      fi
    fi
  fi
fi

VF_LIVE=""
if [ "$LIVE_MODE" = "1" ]; then
  echo "📺 LIVE MODE ON ($LIVE_REASON)"
  # Denoise sangat ringan (siaran sering noisy), jaga detail wajah
  VF_LIVE="hqdn3d=0.8:0.6:2:2"
  # AQ lebih kuat + lookahead lebih panjang + mild deblock (ticker/logo lebih rapi)
  X265_PARAMS="aq-mode=3:aq-strength=1.25:qcomp=0.72:rd=3:psy-rd=1.8:psy-rdoq=1.0:rc-lookahead=60:scenecut=40:deblock=-1,-1:sao=1:strong-intra-smoothing=1:bframes=6"
  CHAT_ID="$CHAT_ID" TG_API_URL="$TG_API_URL" BOT_TOKEN="$BOT_TOKEN" python3 scripts/send_message.py \
    "📺 <b>Live-friendly ON</b> — ${LIVE_REASON}.\\nJaga tengah frame, hemat logo/ticker, denoise ringan. Target tetap ~1.3 Mbps." || true
else
  echo "📺 Live mode OFF (konten general)"
  X265_PARAMS="aq-mode=3:aq-strength=1.0:rd=3:psy-rd=1.5:psy-rdoq=1.0:rc-lookahead=40:scenecut=40"
fi



CHAT_ID="$CHAT_ID" FILENAME="$FILE" TG_API_URL="$TG_API_URL" BOT_TOKEN="$BOT_TOKEN" PROGRESS_MSG_FILE=/tmp/rusemeva_progress_msg_id PROGRESS_STATE_FILE=/tmp/rusemeva_progress_state SRC_DUR_SEC="$SRC_DUR_INT" python3 scripts/progress.py start || true
LAST_PCT=-1
HEVC_LOG=/tmp/rusemeva_hevc_encode.log
# FIX PROGRESS 0%: -progress pipe:1 tulis ke stdout.
# Pakai '3>&1 1>>...' supaya progress ke fd 3 (yg di-pipe ke while),
# stderr+stdout utama ke log. Tanpa ini, progress diambil log, while kosong.
# Live denoise filter (kosong kalau bukan live)
LIVE_VF_ARGS=()
if [ -n "${VF_LIVE:-}" ]; then
  LIVE_VF_ARGS=(-vf "$VF_LIVE")
fi
"$FFMPEG_STATIC" -hide_banner -y -i "$FILE" \
  "${LIVE_VF_ARGS[@]}" \
  -c:v libx265 -profile:v main10 -pix_fmt yuv420p10le \
  -crf ${HEVC_CRF} -preset ${HEVC_PRESET} -maxrate ${MAXRATE_K:-1450}k -bufsize ${BUFSIZE_K:-2900}k \
  -x265-params "${X265_PARAMS}" -tag:v hvc1 \
  -c:a copy -progress pipe:3 "$HEVC_FILE" \
  3> >(while IFS='=' read -r k v; do
    if [ "$k" = "out_time_ms" ]; then
      ms=${v%.*}
      [ "$ms" -gt 0 ] 2>/dev/null || continue
      cur=$(( ms / 1000000 ))
      pct=$(( (cur * 100) / SRC_DUR_INT )); [ "$pct" -gt 100 ] && pct=100
      if [ "$pct" != "$LAST_PCT" ]; then
        LAST_PCT=$pct
        echo "🔄 HEVC encode ${pct}%"
        CHAT_ID="$CHAT_ID" FILENAME="$FILE" TG_API_URL="$TG_API_URL" BOT_TOKEN="$BOT_TOKEN" PROGRESS_MSG_FILE=/tmp/rusemeva_progress_msg_id PROGRESS_STATE_FILE=/tmp/rusemeva_progress_state SRC_DUR_SEC="$SRC_DUR_INT" python3 scripts/progress.py progress "$pct" || true
      fi
    fi
  done) \
  > "$HEVC_LOG" 2>&1
echo "🔄 HEVC encode 100%"
CHAT_ID="$CHAT_ID" FILENAME="$FILE" TG_API_URL="$TG_API_URL" BOT_TOKEN="$BOT_TOKEN" PROGRESS_MSG_FILE=/tmp/rusemeva_progress_msg_id python3 scripts/progress.py done || true

if [ -s "$HEVC_FILE" ]; then
  echo "✅ HEVC selesai: $(ls -lh "$HEVC_FILE" | awk '{print $5}')"

  # === AUTO BITRATE/SIZE GUARD ===
  # Target: HEVC harus lebih kecil dari original (kayak run 18 Jul: 2.2→1.4 Mbps).
  # Kalau masih >= original, naikkan CRF bertahap (lebih longgar) lalu re-encode.
  # Batas max CRF 28 biar kualitas tetap oke (tidak jelek parah).
  # Target hemat: HEVC <= 90% original (margin kecil biar "turun beneran").
  ORIG_BYTES=$(stat -c%s "$FILE" 2>/dev/null || wc -c < "$FILE")
  TARGET_BYTES=$(target_bytes "$SRC_DUR_INT" "$ORIG_BYTES" || awk "BEGIN{printf \"%d\", $ORIG_BYTES * 0.90}")
  CUR_CRF="$HEVC_CRF"
  MAX_CRF=28
  try=0
  while true; do
    HEVC_BYTES=$(stat -c%s "$HEVC_FILE" 2>/dev/null || wc -c < "$HEVC_FILE")
    echo "📏 size: orig=${ORIG_BYTES} hevc=${HEVC_BYTES} target<=${TARGET_BYTES} (crf=${CUR_CRF})"
    HBR_CHK=$(probe_bitrate "$HEVC_FILE" || true)
    if [ -n "$HBR_CHK" ] && [ "$HBR_CHK" -le 1500000 ]; then
      if [ "$HEVC_BYTES" -le "$TARGET_BYTES" ] || [ "$HBR_CHK" -le 1450000 ]; then
        echo "Size/bitrate OK crf=$CUR_CRF bps=$HBR_CHK"
        break
      fi
    fi
    if [ -z "$HBR_CHK" ]; then
      echo "bitrate unknown - fail"; exit 1
    fi
    NEXT_CRF=$((CUR_CRF + 2))
    if [ "$NEXT_CRF" -gt "$MAX_CRF" ]; then
      echo "⚠️ Masih besar di CRF $CUR_CRF, tapi sudah cap $MAX_CRF — stop biar kualitas tidak jelek."
      CHAT_ID="$CHAT_ID" TG_API_URL="$TG_API_URL" BOT_TOKEN="$BOT_TOKEN" python3 scripts/send_message.py \
        "⚠️ <b>Auto-size:</b> HEVC masih besar di CRF $CUR_CRF (cap $MAX_CRF). Kualitas dipertahankan, size tidak dipaksa lebih kecil." || true
      break
    fi
    try=$((try + 1))
    echo "🔻 Auto-size try#$try: CRF $CUR_CRF → $NEXT_CRF (HEVC masih >= 90% original)"
    CHAT_ID="$CHAT_ID" TG_API_URL="$TG_API_URL" BOT_TOKEN="$BOT_TOKEN" python3 scripts/send_message.py \
      "🔻 <b>Auto-size:</b> file HEVC masih besar, re-encode CRF <code>$CUR_CRF</code> → <code>$NEXT_CRF</code> (target &lt; original, max CRF $MAX_CRF)." || true
    CUR_CRF=$NEXT_CRF
    HEVC_CRF=$CUR_CRF
    # re-encode (progress bar reset ringan)
    CHAT_ID="$CHAT_ID" FILENAME="$FILE" TG_API_URL="$TG_API_URL" BOT_TOKEN="$BOT_TOKEN" PROGRESS_MSG_FILE=/tmp/rusemeva_progress_msg_id PROGRESS_STATE_FILE=/tmp/rusemeva_progress_state SRC_DUR_SEC="$SRC_DUR_INT" PHASE_LABEL="Re-encode CRF $CUR_CRF" python3 scripts/progress.py start || true
    LAST_PCT=-1
    "$FFMPEG_STATIC" -hide_banner -y -i "$FILE" \
      -c:v libx265 -profile:v main10 -pix_fmt yuv420p10le \
      -crf ${CUR_CRF} -preset ${HEVC_PRESET} -maxrate ${MAXRATE_K:-1450}k -bufsize ${BUFSIZE_K:-2900}k \
      -x265-params "${X265_PARAMS:-aq-mode=3:aq-strength=1.0}" -tag:v hvc1 \
      -c:a copy -progress pipe:3 "$HEVC_FILE" \
      3> >(while IFS='=' read -r k v; do
        if [ "$k" = "out_time_ms" ]; then
          ms=${v%.*}
          [ "$ms" -gt 0 ] 2>/dev/null || continue
          cur=$(( ms / 1000000 ))
          pct=$(( (cur * 100) / SRC_DUR_INT )); [ "$pct" -gt 100 ] && pct=100
          if [ "$pct" != "$LAST_PCT" ]; then
            LAST_PCT=$pct
            CHAT_ID="$CHAT_ID" FILENAME="$FILE" TG_API_URL="$TG_API_URL" BOT_TOKEN="$BOT_TOKEN" PROGRESS_MSG_FILE=/tmp/rusemeva_progress_msg_id PROGRESS_STATE_FILE=/tmp/rusemeva_progress_state SRC_DUR_SEC="$SRC_DUR_INT" PHASE_LABEL="Re-encode CRF $CUR_CRF" python3 scripts/progress.py progress "$pct" || true
          fi
        fi
      done) \
      > "$HEVC_LOG" 2>&1 || true
    CHAT_ID="$CHAT_ID" FILENAME="$FILE" TG_API_URL="$TG_API_URL" BOT_TOKEN="$BOT_TOKEN" PROGRESS_MSG_FILE=/tmp/rusemeva_progress_msg_id PHASE_LABEL="Re-encode CRF $CUR_CRF" python3 scripts/progress.py done || true
    if [ ! -s "$HEVC_FILE" ]; then
      echo "❌ Re-encode CRF $CUR_CRF gagal menghasilkan file"
      break
    fi
  done
  echo "HEVC_CRF_FINAL=$CUR_CRF" >> $GITHUB_ENV

  # === MIN BITRATE FLOOR (~1.2 Mbps) ===
  # User feedback: 1.0 Mbps @720p terlalu buram; sweet spot ~1.3 Mbps.
  # Kalau hasil < 1.2 Mbps dan CRF masih bisa diturunkan (>=22), re-encode 1x CRF-2.
  MIN_BPS=1200000
  HBR_NOW=$(ffprobe -v error -show_entries format=bit_rate -of default=noprint_wrappers=1:nokey=1 "$HEVC_FILE" 2>/dev/null | head -1)
  case "$HBR_NOW" in ''|*[!0-9]*) HBR_NOW=0 ;; esac
  if [ "$HBR_NOW" -gt 0 ] && [ "$HBR_NOW" -lt "$MIN_BPS" ]; then
    FLOOR_CRF=$((CUR_CRF - 2))
    if [ "$FLOOR_CRF" -lt 22 ]; then FLOOR_CRF=22; fi
    if [ "$FLOOR_CRF" -lt "$CUR_CRF" ]; then
      echo "🪞 Bitrate rendah (${HBR_NOW} bps < ${MIN_BPS}) — naik kualitas CRF $CUR_CRF → $FLOOR_CRF (target ~1.3 Mbps)"
      CHAT_ID="$CHAT_ID" TG_API_URL="$TG_API_URL" BOT_TOKEN="$BOT_TOKEN" python3 scripts/send_message.py \
        "🪞 <b>Auto-quality:</b> bitrate terlalu rendah (&lt;1.2 Mbps). Re-encode CRF <code>$CUR_CRF</code> → <code>$FLOOR_CRF</code> biar tidak buram." || true
      CUR_CRF=$FLOOR_CRF
      HEVC_CRF=$CUR_CRF
      CHAT_ID="$CHAT_ID" FILENAME="$FILE" TG_API_URL="$TG_API_URL" BOT_TOKEN="$BOT_TOKEN" PROGRESS_MSG_FILE=/tmp/rusemeva_progress_msg_id PROGRESS_STATE_FILE=/tmp/rusemeva_progress_state SRC_DUR_SEC="$SRC_DUR_INT" PHASE_LABEL="Re-encode CRF $CUR_CRF (anti-blur)" python3 scripts/progress.py start || true
      LAST_PCT=-1
      "$FFMPEG_STATIC" -hide_banner -y -i "$FILE" \
        -c:v libx265 -profile:v main10 -pix_fmt yuv420p10le \
        -crf ${CUR_CRF} -preset ${HEVC_PRESET} -x265-params "${X265_PARAMS:-aq-mode=3:aq-strength=1.0}" -tag:v hvc1 \
        -c:a copy -progress pipe:3 "$HEVC_FILE" \
        3> >(while IFS='=' read -r k v; do
          if [ "$k" = "out_time_ms" ]; then
            ms=${v%.*}
            [ "$ms" -gt 0 ] 2>/dev/null || continue
            cur=$(( ms / 1000000 ))
            pct=$(( (cur * 100) / SRC_DUR_INT )); [ "$pct" -gt 100 ] && pct=100
            if [ "$pct" != "$LAST_PCT" ]; then
              LAST_PCT=$pct
              CHAT_ID="$CHAT_ID" FILENAME="$FILE" TG_API_URL="$TG_API_URL" BOT_TOKEN="$BOT_TOKEN" PROGRESS_MSG_FILE=/tmp/rusemeva_progress_msg_id PROGRESS_STATE_FILE=/tmp/rusemeva_progress_state SRC_DUR_SEC="$SRC_DUR_INT" PHASE_LABEL="Re-encode CRF $CUR_CRF (anti-blur)" python3 scripts/progress.py progress "$pct" || true
            fi
          fi
        done) \
        > "$HEVC_LOG" 2>&1 || true
      CHAT_ID="$CHAT_ID" FILENAME="$FILE" TG_API_URL="$TG_API_URL" BOT_TOKEN="$BOT_TOKEN" PROGRESS_MSG_FILE=/tmp/rusemeva_progress_msg_id PHASE_LABEL="Re-encode CRF $CUR_CRF (anti-blur)" python3 scripts/progress.py done || true
      echo "HEVC_CRF_FINAL=$CUR_CRF" >> $GITHUB_ENV
      HBR_NOW=$(ffprobe -v error -show_entries format=bit_rate -of default=noprint_wrappers=1:nokey=1 "$HEVC_FILE" 2>/dev/null | head -1)
      echo "🪞 Setelah anti-blur: crf=$CUR_CRF bitrate=${HBR_NOW:-?}"
    fi
  fi

  echo "HEVC_FILE=$HEVC_FILE" >> $GITHUB_ENV
  echo "HEVC_SIZE=$(ls -lh "$HEVC_FILE" | awk '{print $5}')" >> $GITHUB_ENV
  HDUR=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$HEVC_FILE" 2>/dev/null | head -1)
  HDUR_INT=${HDUR%.*}
  [ -z "$HDUR_INT" ] && HDUR_INT=0
  echo "HEVC_DUR=$(printf '%02d:%02d:%02d' $((HDUR_INT/3600)) $(((HDUR_INT%3600)/60)) $((HDUR_INT%60)))" >> $GITHUB_ENV
  HW=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of default=noprint_wrappers=1:nokey=1 "$HEVC_FILE" 2>/dev/null|head -1)
  HH=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=noprint_wrappers=1:nokey=1 "$HEVC_FILE" 2>/dev/null|head -1)
  [ -n "$HW" ] && [ -n "$HH" ] && echo "HEVC_RES=${HW}x${HH}" >> $GITHUB_ENV
  HCV=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$HEVC_FILE" 2>/dev/null|head -1)
  [ -n "$HCV" ] && echo "HEVC_VCODEC=$HCV" >> $GITHUB_ENV
  HBR=$(ffprobe -v error -show_entries format=bit_rate -of default=noprint_wrappers=1:nokey=1 "$HEVC_FILE" 2>/dev/null|head -1)
  case "$HBR" in ''|*[!0-9]*) ;; *) echo "HEVC_VBITRATE=$(awk "BEGIN{printf \"%.1f Mbps\", ${HBR}/1000000}")" >> $GITHUB_ENV ;; esac
  # === #4 VERIFIKASI AUDIO: pastikan HEVC punya stream audio ===
  # x265 cuma encode video; -c:a copy harusnya salin audio. Cek biar gak ke-drop.
  AUD=$(ffprobe -v error -select_streams a -show_entries stream=index -of default=noprint_wrappers=1:nokey=1 "$HEVC_FILE" 2>/dev/null | head -1)
  if [ -z "$AUD" ]; then
    echo "🔇 HEVC TIDAK punya audio stream — re-mux dari original..."
    TMP_REMUX="${HEVC_FILE%.mp4}.remux.mp4"
    "$FFMPEG_STATIC" -hide_banner -y -i "$HEVC_FILE" -i "$FILE" \
      -map 0:v:0 -map 1:a? -c copy "$TMP_REMUX" 2>/dev/null || true
    if [ -s "$TMP_REMUX" ]; then
      AUD2=$(ffprobe -v error -select_streams a -show_entries stream=index -of default=noprint_wrappers=1:nokey=1 "$TMP_REMUX" 2>/dev/null | head -1)
      if [ -n "$AUD2" ]; then
        mv -f "$TMP_REMUX" "$HEVC_FILE"
        echo "✅ Audio berhasil di-re-mux ke HEVC."
      else
        rm -f "$TMP_REMUX"
        echo "⚠️ Original juga gak punya audio — HEVC tanpa suara (wajar kalau sumber silent)."
      fi
    else
      rm -f "$TMP_REMUX"
      echo "⚠️ Re-mux gagal — HEVC tanpa suara."
    fi
  else
    echo "🔊 HEVC punya audio stream (#$AUD) — OK."
  fi
  HEVC_THUMB="${HEVC_FILE%.mp4}.jpg"
  HSEEK=1; [ "$HDUR_INT" -gt 6 ] && HSEEK=$((HDUR_INT/2))
  "$FFMPEG_STATIC" -hide_banner -loglevel error -y -ss "$HSEEK" -i "$HEVC_FILE" -frames:v 1 -q:v 2 -vf "scale=640:-2" "$HEVC_THUMB" 2>/dev/null || true
  [ ! -s "$HEVC_THUMB" ] && "$FFMPEG_STATIC" -hide_banner -loglevel error -y -ss 1 -i "$HEVC_FILE" -frames:v 1 -q:v 2 -vf "scale=640:-2" "$HEVC_THUMB" 2>/dev/null || true
  if [ -s "$HEVC_THUMB" ]; then echo "HEVC_THUMB_FILE=$HEVC_THUMB" >> $GITHUB_ENV; echo "HAS_HEVC_THUMB=1" >> $GITHUB_ENV; else echo "HAS_HEVC_THUMB=0" >> $GITHUB_ENV; fi
  # === #7 KALIBRASI: hitung realtime_x aktual & kirim ke worker (KV) ===
  ENC_ELAPSED=$(( SECONDS - ENC_START ))
  if [ "$HDUR_INT" -gt 0 ] && [ "$ENC_ELAPSED" -gt 0 ]; then
    ACT_RT=$(awk "BEGIN{printf \"%.4f\", $HDUR_INT / $ENC_ELAPSED}")
    echo "🎯 realtime_x aktual: ${ACT_RT}x (video ${HDUR_INT}s / encode ${ENC_ELAPSED}s)"
    # Kirim ke worker biar disimpan + di-rata-rata ke KV
    curl -fsS --retry 2 --retry-delay 3 -X POST "https://rusemeva.rusemeva.workers.dev/rtcal" \
      -H "Content-Type: application/json" \
      -d "{\"preset\":\"${HEVC_PRESET}\",\"rt\":${ACT_RT},\"secret\":\"${PROGRESS_SECRET}\"}" 2>/dev/null || \
      echo "⚠️ Gagal kirim kalibrasi ke worker (non-fatal)."
  fi
else
  echo "⚠️ Encode HEVC gagal."
  # === #5 ERROR CLASSIFICATION: deteksi penyebab gagal biar notif jujur ===
  # Cek log encode untuk kata kunci umum
  REASON="unknown"
  if grep -qiE "No space left on device|disk full|ENOSPC" "$HEVC_LOG" 2>/dev/null; then
    REASON="disk_full"
  elif grep -qiE "Codec .* not found|Unknown encoder|libx265|Unable to find a suitable output|Invalid data found|moov atom not found" "$HEVC_LOG" 2>/dev/null; then
    REASON="codec_or_corrupt"
  elif grep -qiE "Timeout|timed out|killed|Signal 9|SIGKILL" "$HEVC_LOG" 2>/dev/null; then
    REASON="timeout_or_killed"
  elif grep -qiE "Conversion failed|Error .* frames|Denominator" "$HEVC_LOG" 2>/dev/null; then
    REASON="ffmpeg_error"
  fi
  echo "FAIL_REASON=$REASON" >> $GITHUB_ENV
  echo "🔍 FAIL_REASON=$REASON"
fi

