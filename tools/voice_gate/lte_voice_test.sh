#!/bin/sh
# Unattended LTE voice test on the UNO Q (ER-10-6, ER-10-9): runs with the PC unplugged and
# leaves results in ~/audio_check/lte_voice_<time>.log. The pit side (pit_loop.py on the relay
# host) must already be talking in the same room.
#
#   setsid nohup sh lte_voice_test.sh wss://<relay>/ws/audio/voice-test 120 >/dev/null 2>&1 &
#
# To run it once on the next power-up (the UNO Q is powered by the PC's USB, so unplugging it
# to carry it outside reboots it), add a one-shot entry for user arduino:
#   @reboot crontab -r; sh $HOME/audio_check/lte_voice_test.sh wss://<relay>/ws/audio/voice-test 120
#
# Phases: no voice / pit voice down / driver voice up (talking all the time) /
# up (4 s talk, 6 s quiet) / both. Each phase reconnects (a settings change restarts the
# session), waits for streaming, then measures. At the end the send settings and the real
# voice agent's socket are put back.
cd "$(dirname "$0")"
URL=$1; SECS=${2:-120}
LOG=$PWD/lte_voice_$(date +%Y%m%d_%H%M%S).log
DIR=/run/ecocapture-voice
exec >>"$LOG" 2>&1

set_podium() {
  curl -s -X POST -H 'Content-Type: application/json' -H 'X-EcoCapture: 1' -d "$1" 127.0.0.1:8080/api/podium \
    | python3 -c 'import json,sys;d=json.load(sys.stdin);c=d.get("config");print("settings:",d if c is None else (c["link"],c["destination"],"recv",c["voice_receive"],"send",c["voice_send"]))'
}
wait_streaming() {
  i=0
  while [ $i -lt 60 ]; do
    s=$(curl -s 127.0.0.1:8080/api/podium | python3 -c 'import json,sys;print(json.load(sys.stdin)["status"]["state"])')
    case "$s" in streaming|waiting_gps) echo "$(date +%T) streaming after $((i*5)) s"; return 0;; esac
    sleep 5; i=$((i+1))
  done
  echo "$(date +%T) not streaming after 300 s"; return 1
}
fake() {
  [ -n "$FAKE" ] && kill $FAKE 2>/dev/null; sleep 1
  rm -f $DIR/agent.sock
  python3 fake_agent.py driver_reply.wav "$1" "$2" >>"$LOG.agent" 2>&1 &
  FAKE=$!; sleep 2
}
phase() {
  echo; echo "===== $1 ($(date +%T)) ====="
  set_podium "$2"
  sleep 3
  wait_streaming && { sleep 8; python3 telemetry_rate.py "$SECS" "$1"; }
  curl -s 127.0.0.1:8080/api/podium | python3 -c 'import json,sys;s=json.load(sys.stdin)["status"];print({k:s.get(k) for k in ["state","frames","bytes","reconnects","voice","voice_reason","voice_packets","voice_bytes","voice_dropped","voice_sent","voice_pauses","last_failure_operation","last_failure_reason"]})'
}

echo "LTE voice test $(date)  url=$URL  measure=${SECS}s"
# Started from @reboot: wait for the web service and the real voice agent.
i=0
until curl -s -o /dev/null 127.0.0.1:8080/api/podium && [ -S $DIR/agent.sock ]; do
  i=$((i+1)); [ $i -gt 60 ] && { echo "web or voice agent not up"; exit 1; }; sleep 5
done
mv $DIR/agent.sock $DIR/agent.sock.real || exit 1
trap 'kill $FAKE 2>/dev/null; rm -f $DIR/agent.sock; mv $DIR/agent.sock.real $DIR/agent.sock' EXIT
fake 0 0
BASE='"enabled":true,"link":"lte","destination":"server","server_url":"'$URL'"'
phase 'A no voice'          "{$BASE,\"voice_receive\":false,\"voice_send\":false}"
phase 'B down only'         "{$BASE,\"voice_receive\":true,\"voice_send\":false}"
phase 'C up always'         "{$BASE,\"voice_receive\":false,\"voice_send\":true}"
fake 4 6
phase 'D up 4s/10s'         "{$BASE,\"voice_receive\":false,\"voice_send\":true}"
fake 0 0
phase 'E down + up always'  "{$BASE,\"voice_receive\":true,\"voice_send\":true}"
echo; echo "===== restore ($(date +%T)) ====="
set_podium '{"enabled":true,"link":"wifi","destination":"podium","voice_receive":false,"voice_send":false}'
curl -s 127.0.0.1:8080/api/podium/events > "$LOG.events.json"
echo "done $(date)"
