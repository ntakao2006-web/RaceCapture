#!/bin/sh
# Read-only check of the UNO Q before a manned voice test (handoff_20261020_voice_field_test.md, ch. 2).
# Changes nothing. From the PC:
#   ssh unoq 'sh -s' < tools/voice_gate/precheck.sh
# Each line starts with OK / NG / -- (information only).
ok() { echo "OK  $*"; }
ng() { echo "NG  $*"; }
info() { echo "--  $*"; }

for s in ecocapture-voice ecocapture-mcu-supervisor; do
  if systemctl is-active -q "$s"; then ok "$s 稼働中"; else ng "$s が動いていない（$(systemctl is-active "$s" 2>&1)）"; fi
done
[ -f /opt/ecocapture-voice/librnnoise_old.so ] && ok "RNNoise（旧版）配置済み" \
  || ng "RNNoise未配置 → ~/EcoCapture-Web で sh install-voice-agent.sh"
python3 -c 'import numpy' 2>/dev/null && ok "numpyあり" || ng "ホストのpython3にnumpyが無い（音声エージェントが起動しない）"

# The agent takes any USB audio device (whatever its name); which one it chose is in its status below.
info "USBオーディオ: $(grep -A1 'USB-Audio' /proc/asound/cards | sed -n 's/^ *[0-9]* \[\([^ ]*\) *\]: USB-Audio - /\1 = /p' | tr '\n' ' ')"
info "再生先: $(aplay -l 2>/dev/null | grep '^card' | sed 's/ \[.*//' | sort -u | tr '\n' ' ')"
bt=$(XDG_RUNTIME_DIR=/run/user/$(id -u) pactl list short sinks 2>/dev/null | grep -c bluez)
[ "$bt" -gt 0 ] && info "Bluetoothイヤホン接続中（耳はこちらが優先）" || info "Bluetoothイヤホンは未接続（耳はUSB）"

# Send settings and voice counters as the web service sees them.
curl -s -m 5 127.0.0.1:8080/api/podium | python3 -c '
import json, re, sys
d = json.load(sys.stdin); c = d.get("config", {}); s = d.get("status", {})
def line(good, text): print(("OK  " if good else "NG  ") + text)
line(c.get("enabled"), "送信 " + ("ON" if c.get("enabled") else "OFF"))
line(c.get("destination") == "server", "送り先: " + str(c.get("destination")) + "（試験は server）")
url = c.get("server_url", "")
room = re.sub(r".*/ws/audio/", "", url) if url else ""
line(room == "voice-test", "部屋: " + (room or "（未設定）") + "（試験は voice-test）")
print("--  回線: " + str(c.get("link")) + " / 使用中: " + str(s.get("active_link")) + "（T1〜T5は wifi、T6は lte）")
line(c.get("voice_receive"), "ピットの音声を受ける " + ("ON" if c.get("voice_receive") else "OFF"))
line(c.get("voice_send"), "ドライバーの声を送る " + ("ON" if c.get("voice_send") else "OFF"))
a = s.get("voice_agent")
line(a is not None, "音声エージェントの応答: " + json.dumps(a, ensure_ascii=False))
if a is not None:
    line(a.get("mic"), "マイク: " + (str(a.get("card")) if a.get("mic") else "なし（USBのマイク・イヤホンが挿さっているか）"))
    line(a.get("route"), "耳: " + (str(a.get("route")) + " / " + str(a.get("device")) if a.get("route") else "なし"))
print("--  voice=%s sent=%s packets=%s dropped=%s pauses=%s reason=%s" % tuple(
    s.get(k) for k in ("voice", "voice_sent", "voice_packets", "voice_dropped", "voice_pauses", "voice_reason")))
if s.get("radio"): print("--  LTE電波: " + json.dumps(s["radio"], ensure_ascii=False))
' 2>/dev/null || ng "/api/podium が応答しない（EcoCaptureのWebが起動していない）"
