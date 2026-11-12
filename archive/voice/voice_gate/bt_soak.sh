#!/bin/bash
# UNO Q内蔵Bluetooth（WCN3990）の一晩の再現試験（2026-10-18）。
# 10/17夜に固まったときと同じく、ケースに入れたままのイヤホンを約16秒おきに呼び出し続ける。
# チップの異常（hci0のtx timeout・crash・Frame reassembly・hardware error）が出たら呼び出しをやめ、
# その後も自力で戻るかを1分ごとに記録する。10分ごとに温度・電源・エラー数も残す。
#   nohup ./bt_soak.sh 43200 > /dev/null 2>&1 &     （秒。既定12時間）
MAC=${MAC:-40:DE:17:B6:15:45}
END=$(( $(date +%s) + ${1:-43200} ))
DIR=~/bt_diag; LOG=$DIR/soak.log; KLOG=$DIR/soak_kernel.log
mkdir -p $DIR; : > $LOG
ts() { date '+%m-%d %H:%M:%S'; }
start=$(dmesg | wc -l)
echo "$(ts) START mac=$MAC until $(date -d @$END '+%m-%d %H:%M')" >> $LOG
n=0; failed=0; last_health=0
while [ $(date +%s) -lt $END ]; do
  now=$(date +%s)
  if [ $((now - last_health)) -ge 600 ]; then
    last_health=$now
    echo "$(ts) HEALTH tries=$n cpu=$(($(cat /sys/class/thermal/thermal_zone3/temp)/1000))C wlan=$(($(cat /sys/class/thermal/thermal_zone2/temp)/1000))C bt=$(bluetoothctl show | awk '/Powered/{print $2}') $(hciconfig hci0 2>/dev/null | grep -o 'errors:[0-9]*' | tr '\n' ' ')" >> $LOG
  fi
  if [ $failed -eq 0 ]; then
    t0=$(date +%s)
    r=$(bluetoothctl --timeout 8 connect $MAC 2>&1 | tail -1); n=$((n+1))
    case "$r" in *successful*) echo "$(ts) CONNECTED at try $n (earphone out of the case?)" >> $LOG; bluetoothctl disconnect $MAC >/dev/null 2>&1;; esac
    # Keep the 10/17 pace: one call about every 16 s.
    sleep $(( 16 - ($(date +%s) - t0) > 0 ? 16 - ($(date +%s) - t0) : 1 ))
    if dmesg | tail -n +$((start+1)) | grep -qiE "hci0: (command .* tx timeout|crash|Frame reassembly|hardware error|Reading QCA version information failed)"; then
      failed=$(date +%s)
      echo "$(ts) ERROR after $n tries ($(( (failed - $(date -d "$(head -1 $LOG | cut -c1-14)" +%s 2>/dev/null || echo $failed)) ))s)" >> $LOG
      dmesg | tail -n +$((start+1)) | grep -iE "hci0|bluetooth" > $KLOG
    fi
  else
    # After a failure: does the chip come back on its own?
    sleep 60
    echo "$(ts) AFTER bt=$(bluetoothctl show | awk '/Powered/{print $2}') power_on=$(bluetoothctl power on 2>&1 | tail -1 | tr -d '\n')" >> $LOG
  fi
done
dmesg | tail -n +$((start+1)) | grep -iE "hci0|bluetooth" > $KLOG
echo "$(ts) END tries=$n failed=$([ $failed -gt 0 ] && echo yes || echo no)" >> $LOG
