#!/bin/sh
# エコラン（2026-10-25 決勝）の走行記録を流し、今のカメラの景色に焼き込んで録る。110秒目に配置を rich へ切り替える
# 本体の ~/hud_load_20261030/ に replay_telemetry.py・rich.ini・default.ini と置き、抜き出した走行記録を /tmp/ecorun_lap1.csv に置く
d=/home/arduino/hud_load_20261030
cd $d || exit 1
cam=$(ls /dev/v4l/by-id/*-video-index0 | head -1)
python3 $d/replay_telemetry.py /tmp/ecorun_lap1.csv --port 18081 > $d/replay.log 2>&1 &
rp=$!
sleep 2
cp $d/default.ini $d/replay_hud.ini
mkdir -p $d/replay
env OVERLAY_HUD=$d/replay_hud.ini OVERLAY_HUD_DEFAULT=/opt/ecologger-video/hud_default.ini OVERLAY_HUD_STATUS=$d/status_replay.txt \
    OVERLAY_MIN_FREE_MB=1300 OVERLAY_TELEMETRY_PORT=18081 TZ=Asia/Tokyo \
    /opt/ecologger-video/overlay_rec "$cam" "$d/replay/%Y%m%d_%H%M%S.ts" 180 /opt/ecologger-video/hud_font_64.pgm > $d/log_replay.txt 2>&1 &
pid=$!
: > mon_replay.txt
t=0
while kill -0 $pid 2>/dev/null; do
    sleep 5; t=$((t + 5))
    if [ $t = 110 ]; then cp rich.ini replay_hud.ini.tmp && mv replay_hud.ini.tmp replay_hud.ini; echo "$(date +%T) switched to rich" >> mon_replay.txt; fi
    hz=$(curl -s -m 3 http://127.0.0.1:8080/api/telemetry | python3 -c 'import json,sys; s=json.load(sys.stdin)["status"]; print(s["receive_hz"], s["hardware"]["sd_errors"], s["hardware"]["sd_queue_dropped"])' 2>/dev/null)
    echo "$(date +%T) hz/sd_err/sd_drop $hz temp $(cat /sys/class/thermal/thermal_zone0/temp) load $(cut -d' ' -f1 /proc/loadavg) gpu $(cat /sys/class/devfreq/5900000.gpu/cur_freq)" >> mon_replay.txt
done
wait $pid; echo "exit=$?" >> log_replay.txt
kill $rp
cat log_replay.txt; cat status_replay.txt; ls -la replay
