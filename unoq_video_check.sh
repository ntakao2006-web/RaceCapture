#!/bin/bash
# UNO Q 映像パイプライン確認 V-1〜V-3 を無人で通すスクリプト。
# 手順と判定基準の正は unoq_video_check_procedure.md（このスクリプトはその3〜5章を自動化したもの）。
#
# PCから流す（UNO Qへコピー不要）:
#   ssh unoq 'bash -s' < unoq_video_check.sh
# UNO Q上で直接:
#   bash unoq_video_check.sh
#
# - 作業ディレクトリは ~/enc_test（/tmp はtmpfsのため使わない）。素材186MB＋出力数十MBを置く
# - 結果は ~/enc_test/result_<日時>/ に一式保存し、最後に summary.txt を表示する
# - 走行ログ・SD・常駐サービスには触れない（停止もしない）。負荷条件として稼働状況を記録だけする
# - 不足パッケージは、パスワード無しsudoが通るときだけ自動で入れる

set -u
WORK="$HOME/enc_test"
TS=$(date +%Y%m%d_%H%M%S)
OUT="$WORK/result_$TS"
SRC="$WORK/src_2s.nv12"
SRC_BYTES=$((1920 * 1080 * 3 / 2 * 60))
EXPECT_FRAMES=900

# sudo無しで ~/ffmpeg-local に展開したffmpegがあればそれを使う（apt-get download＋dpkg -x。手順書4章）
LOCAL_FF="$HOME/ffmpeg-local"
if [ -x "$LOCAL_FF/usr/bin/ffmpeg" ]; then
    export PATH="$LOCAL_FF/usr/bin:$PATH"
    export LD_LIBRARY_PATH="$(find "$LOCAL_FF" -name '*.so*' -printf '%h
' | sort -u | tr '
' ':')${LD_LIBRARY_PATH:-}"
fi
TIME_BIN=/usr/bin/time; [ -x "$TIME_BIN" ] || TIME_BIN="$LOCAL_FF/usr/bin/time"

mkdir -p "$OUT" && cd "$WORK" || { echo "作業ディレクトリを作れない: $WORK"; exit 1; }
SUM="$OUT/summary.txt"
say() { echo "$*" | tee -a "$SUM"; }
section() { say ""; say "===== $* ====="; }

temps() {
    for z in /sys/class/thermal/thermal_zone*; do
        [ -r "$z/temp" ] || continue
        printf '%s=%s ' "$(cat "$z/type" 2>/dev/null)" "$(( $(cat "$z/temp") / 1000 ))C"
    done
}

# ---------------------------------------------------------------- 準備
section "準備"
say "日時: $(date '+%F %T')  ホスト: $(hostname)  カーネル: $(uname -r)"
say "負荷: $(cut -d' ' -f1-3 /proc/loadavg)  温度: $(temps)"
say "稼働中の主なサービス: $(systemctl list-units --type=service --state=running --no-legend 2>/dev/null \
    | awk '{print $1}' | grep -Ei 'racecapture|ecocapture|logger|rcp' | tr '\n' ' ')"

need=()
command -v v4l2-ctl >/dev/null || need+=(v4l-utils)
command -v ffmpeg   >/dev/null || need+=(ffmpeg)
[ -x "$TIME_BIN" ]            || need+=(time)
if [ ${#need[@]} -gt 0 ]; then
    if sudo -n true 2>/dev/null; then
        say "不足パッケージを導入: ${need[*]}"
        sudo -n apt-get update -qq >"$OUT/apt.log" 2>&1
        sudo -n apt-get install -y -qq "${need[@]}" >>"$OUT/apt.log" 2>&1 || say "⚠️ apt-get失敗（$OUT/apt.log）"
    else
        say "⚠️ 不足パッケージ: ${need[*]}（パスワード無しsudoが通らないため自動導入しない）"
        say "   手動で: sudo apt-get install -y ${need[*]}"
    fi
fi

avail_kb=$(df -Pk "$WORK" | awk 'NR==2{print $4}')
say "空き容量: $((avail_kb / 1024)) MB（2GB以上必要）"
[ "$avail_kb" -ge $((2 * 1024 * 1024)) ] || say "⚠️ 空き容量不足。素材の生成に失敗する可能性がある"

# ---------------------------------------------------------------- V-1
section "V-1 エンコーダデバイスが見えているか"
{ ls -l /dev/video* 2>&1; echo; v4l2-ctl --list-devices 2>&1; } >"$OUT/v1_devices.txt"
ENC_DEV="" ; DEC_DEV=""
for d in /dev/video*; do
    [ -e "$d" ] || continue
    out_fmt=$(v4l2-ctl -d "$d" --list-formats-out 2>/dev/null)
    cap_fmt=$(v4l2-ctl -d "$d" --list-formats     2>/dev/null)
    { echo "===== $d"; echo "-- OUTPUT(入力) 側:"; echo "$out_fmt"; echo "-- CAPTURE(出力) 側:"; echo "$cap_fmt"; } >>"$OUT/v1_formats.txt"
    # エンコーダ = 入力が生画・出力がH.264 / デコーダ = 入力がH.264・出力が生画
    if echo "$out_fmt" | grep -qiE "nv12|nv21|yuv" && echo "$cap_fmt" | grep -qiE "h264"; then ENC_DEV+="$d "; fi
    if echo "$out_fmt" | grep -qiE "h264" && echo "$cap_fmt" | grep -qiE "nv12|nv21|yuv"; then DEC_DEV+="$d "; fi
done
say "エンコーダ: ${ENC_DEV:-（見つからない）}"
say "デコーダ  : ${DEC_DEV:-（見つからない）}"
lsmod 2>/dev/null | grep -i venus >"$OUT/v1_venus_lsmod.txt"
say "venusドライバ: $( [ -s "$OUT/v1_venus_lsmod.txt" ] && echo 読み込み済み || echo '読み込まれていない（組み込みの可能性あり）')"
[ -n "$ENC_DEV" ] && V1=OK || V1=NG
say "V-1判定: $V1"

# ---------------------------------------------------------------- V-2
section "V-2 ffmpegがエンコーダを持っているか"
ffmpeg -hide_banner -encoders 2>/dev/null | grep -i v4l2 | tee "$OUT/v2_encoders.txt" >>"$SUM"
if ! command -v ffmpeg >/dev/null; then V2="未実施（ffmpegなし）"
elif grep -q h264_v4l2m2m "$OUT/v2_encoders.txt"; then V2=OK; else V2=NG; fi
ffmpeg -hide_banner -encoders 2>/dev/null | grep -q libx264 && HAS_X264=1 || HAS_X264=0
say "V-2判定: $V2（ビルドに含まれているかだけの確認。実際に回るかはV-3で見る）"

# ---------------------------------------------------------------- V-3
section "V-3 1080p30のハードウェアエンコードが実時間で回るか"
if [ "$(stat -c %s "$SRC" 2>/dev/null || echo 0)" -ne "$SRC_BYTES" ]; then
    say "素材を生成（2秒・NV12・約186MB）..."
    ffmpeg -hide_banner -loglevel error -f lavfi -i testsrc2=size=1920x1080:rate=30 -t 2 \
        -pix_fmt nv12 -f rawvideo -y "$SRC" 2>"$OUT/v3_src.log"
fi
if [ "$(stat -c %s "$SRC" 2>/dev/null || echo 0)" -ne "$SRC_BYTES" ]; then
    say "❌ 素材の生成に失敗（$OUT/v3_src.log）。V-3は実施できない"
    V3="実施不可"
else
    say "素材: $SRC（再実行時は使い回す）"

    run_enc() {  # $1=名前 $2..=エンコーダ指定
        local name=$1; shift
        local t0 t1
        say "--- $name: エンコード開始（温度: $(temps)）"
        t0=$(date +%s.%N)
        timeout 180 "$TIME_BIN" -v ffmpeg -hide_banner -loglevel verbose \
            -stream_loop 14 -f rawvideo -pix_fmt nv12 -s 1920x1080 -r 30 -i "$SRC" \
            "$@" -b:v 12M -fps_mode passthrough \
            -y "$OUT/out_$name.mp4" 2>"$OUT/enc_$name.log"
        local rc=$?
        t1=$(date +%s.%N)
        say "    終了コード: $rc  実時間: $(awk "BEGIN{printf \"%.1f\", $t1-$t0}")秒（素材は30秒）  温度: $(temps)"
        say "    最終 $(tr '\r' '\n' <"$OUT/enc_$name.log" | grep -oE 'frame= *[0-9]+|speed= *[0-9.]+x' | tail -2 | tr -d ' ' | tr '\n' ' ')"
        say "    $(grep -E 'Percent of CPU' "$OUT/enc_$name.log" | sed 's/^\s*//')"
        if [ -s "$OUT/out_$name.mp4" ]; then
            local probe
            probe=$(ffprobe -v error -count_frames -select_streams v:0 \
                -show_entries stream=nb_read_frames,codec_name,width,height,avg_frame_rate \
                -of default=noprint_wrappers=1 "$OUT/out_$name.mp4" | tr '\n' ' ')
            say "    出力: $probe サイズ: $(du -h "$OUT/out_$name.mp4" | cut -f1)"
            ffmpeg -v error -i "$OUT/out_$name.mp4" -f null - >"$OUT/decode_check_$name.txt" 2>&1
            if [ -s "$OUT/decode_check_$name.txt" ]; then say "    ⚠️ 読み戻しでエラーあり（decode_check_$name.txt）"; else say "    読み戻し: エラーなし"; fi
            eval "FRAMES_$name=\$(echo \"\$probe\" | sed -n 's/.*nb_read_frames=\([0-9]*\).*/\1/p')"
        else
            say "    ❌ 出力ファイルなし"
            eval "FRAMES_$name=0"
        fi
        eval "SPEED_$name=\$(tr '\r' '\n' <\"\$OUT/enc_$name.log\" | grep -oE 'speed= *[0-9.]+x' | tail -1 | tr -d ' ' | sed 's/speed=//; s/x//')"
        eval "RC_$name=$rc"
    }

    run_enc hw -c:v h264_v4l2m2m
    say "    使用デバイス（ログより）:"
    grep -Ei "v4l2|/dev/video|Using device|driver" "$OUT/enc_hw.log" | grep -v '^\s*$' | head -8 | sed 's/^/      /' | tee -a "$SUM" >/dev/null

    if [ "$HAS_X264" = 1 ]; then
        run_enc sw -c:v libx264 -preset ultrafast
    else
        say "--- 対照（libx264）: このffmpegにlibx264が無いため省略"
    fi

    # 判定（手順書5-3: ①使用デバイス ②フレーム欠落 ③保存結果。速度・CPUは補助）
    hw_dev_ok=0
    grep -qiE "/dev/video|v4l2" "$OUT/enc_hw.log" && [ "${RC_hw:-1}" -eq 0 ] && hw_dev_ok=1
    if [ "${RC_hw:-1}" -ne 0 ] || [ "${FRAMES_hw:-0}" = 0 ]; then
        V3="NG（HWエンコードがエラーで落ちた＝使えない）"
    elif [ "$hw_dev_ok" = 1 ] && [ "${FRAMES_hw:-0}" = "$EXPECT_FRAMES" ] && [ ! -s "$OUT/decode_check_hw.txt" ] \
         && awk "BEGIN{exit !(${SPEED_hw:-0} >= 1.0)}"; then
        V3="OK（900フレーム・欠落なし・実時間以上）"
    else
        V3="要確認（フレーム ${FRAMES_hw:-?}/$EXPECT_FRAMES、speed ${SPEED_hw:-?}x）"
    fi
    [ -n "${SPEED_sw:-}" ] && say "対照比較: HW speed=${SPEED_hw:-?}x / SW(libx264) speed=${SPEED_sw}x（はっきり分かれればHWが効いている裏付け）"

    # ffmpegを通さずエンコーダを直接駆動する（2026-10-09: ffmpeg 7.1.5のh264_v4l2m2mはVenusで落ちたため。手順書5-5）
    # 入力は高さ1088行に揃える（1080行詰めだと色差面がずれる）。入力側に30fpsを伝えないとクロックが上がらない
    ENC0=${ENC_DEV%% *}
    SRC88="$WORK/src_2s_1088.nv12"
    [ "$(stat -c %s "$SRC88" 2>/dev/null || echo 0)" -eq $((1920 * 1088 * 3 / 2 * 60)) ] ||         ffmpeg -v error -y -f rawvideo -pix_fmt nv12 -s 1920x1080 -i "$SRC" -vf pad=1920:1088 -pix_fmt nv12 -f rawvideo "$SRC88"
    if [ -n "$ENC0" ] && [ -s "$SRC88" ]; then
        say "--- hw_v4l2（v4l2-ctlで$ENC0を直接駆動）: 開始（温度: $(temps)）"
        t0=$(date +%s.%N)
        timeout 180 "$TIME_BIN" -v v4l2-ctl -d "$ENC0"             --set-fmt-video-out=width=1920,height=1080,pixelformat=NV12 --set-fmt-video=pixelformat=H264 --set-output-parm=30             --stream-out-mmap --stream-mmap --stream-from="$SRC88" --stream-loop             --stream-to="$OUT/out_hw_v4l2.h264" --stream-count=$EXPECT_FRAMES >"$OUT/enc_hw_v4l2.log" 2>&1
        RC_v4l2=$?
        WALL_v4l2=$(awk "BEGIN{printf \"%.1f\", $(date +%s.%N)-$t0}")
        FRAMES_v4l2=$(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames             -of csv=p=0 "$OUT/out_hw_v4l2.h264" 2>/dev/null)
        ffmpeg -v error -i "$OUT/out_hw_v4l2.h264" -f null - >"$OUT/decode_check_hw_v4l2.txt" 2>&1
        say "    終了コード: $RC_v4l2  実時間: ${WALL_v4l2}秒（素材は30秒）  フレーム: ${FRAMES_v4l2:-0}/$EXPECT_FRAMES  温度: $(temps)"
        say "    $(grep -E 'Percent of CPU' "$OUT/enc_hw_v4l2.log" | sed 's/^\s*//')"
        [ -s "$OUT/decode_check_hw_v4l2.txt" ] && say "    ⚠️ 読み戻しでエラーあり" || say "    読み戻し: エラーなし"
        ffmpeg -v error -y -i "$OUT/out_hw_v4l2.h264" -vf "select=eq(n\,300)" -frames:v 1 -q:v 3 "$OUT/frame_hw_v4l2.jpg" 2>/dev/null
        if [ "$RC_v4l2" -eq 0 ] && [ "${FRAMES_v4l2:-0}" = "$EXPECT_FRAMES" ] && [ ! -s "$OUT/decode_check_hw_v4l2.txt" ]              && awk "BEGIN{exit !($WALL_v4l2 <= 30.0)}"; then
            V3_v4l2="OK"
        else
            V3_v4l2="NG"
        fi
        say "    直接駆動の判定: $V3_v4l2（目視用に frame_hw_v4l2.jpg を保存）"
        case "$V3" in OK*) ;; *) [ "$V3_v4l2" = OK ] && V3="△ エンコーダ本体はOK（直接駆動で実時間以上）／ffmpeg経由は ${V3}" ;; esac
    fi
fi
say "V-3判定: $V3"

# ---------------------------------------------------------------- まとめ
section "まとめ"
say "V-1 $V1 / V-2 $V2 / V-3 $V3"
say "結果一式: $OUT"
say "※ 出力mp4は目視でブロックノイズ・コマ飛び・色化けが無いかも確認すること（手順書5-3③）"
