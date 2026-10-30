#!/bin/sh
# 本体の ~/hud_load_20261030/ にこのフォルダの .ini と置いて、入力は file:/home/arduino/video_test/test_720p.jpg（毎秒30コマ）で測った
# 計器のパターンごとの負荷の試験（2026-10-30、手順書5-15）。録画サービスは止まっている前提（カメラ・エンコーダを使う）
#   sh run_load.sh <名前> <入力> <秒> [OVERLAY_NOHUD=1 など]
d=/home/arduino/hud_load_20261030
cd $d || exit 1
name=$1; input=$2; secs=$3; shift 3
env OVERLAY_HUD=$d/$name.ini OVERLAY_HUD_DEFAULT=/opt/ecologger-video/hud_default.ini OVERLAY_HUD_STATUS=$d/status_$name.txt \
    OVERLAY_MIN_FREE_MB=1300 OVERLAY_DEMO=1 TZ=Asia/Tokyo "$@" \
    /opt/ecologger-video/overlay_rec "$input" $d/out_$name.ts $secs /opt/ecologger-video/hud_font_64.pgm > $d/log_$name.txt 2>&1 &
pid=$!
: > mon_$name.txt
while kill -0 $pid 2>/dev/null; do
    sleep 5
    hz=$(curl -s -m 3 http://127.0.0.1:8080/api/telemetry | python3 -c 'import json,sys; s=json.load(sys.stdin)["status"]; print(s["receive_hz"], s["hardware"]["sd_errors"], s["hardware"]["sd_queue_dropped"])' 2>/dev/null)
    echo "$(date +%T) hz/sd_err/sd_drop $hz temp $(cat /sys/class/thermal/thermal_zone0/temp) load $(cut -d' ' -f1 /proc/loadavg) gpu $(cat /sys/class/devfreq/*gpu*/cur_freq 2>/dev/null | head -1)" >> mon_$name.txt
done
wait $pid; echo "exit=$?" >> log_$name.txt
tail -c 3000000 out_$name.ts > tail_$name.ts; rm -f out_$name.ts out_$name.csv
echo "== $name"; grep -E "^hud|frames=|per-frame|process CPU|exit=" log_$name.txt
awk '{print $3}' mon_$name.txt | sort -n | sed -n '1p;$p' | tr '\n' ' '; echo "(logger Hz min max)"
awk '{print $5}' mon_$name.txt | sort -n | tail -1 | xargs echo "temp max"
awk '{print $9}' mon_$name.txt | sort -n | uniq -c | tr '\n' ' '; echo "(gpu freq)"
awk '{s+=$4+$5? $4:0} END {}' mon_$name.txt; awk '{e+=$4; q+=$5} END {print "sd_err_sum", e, "sd_drop_sum", q}' mon_$name.txt
