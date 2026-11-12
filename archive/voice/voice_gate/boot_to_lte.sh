#!/bin/sh
# Power-on to first telemetry over LTE, as on race day (ER-1-4): the send settings are
# already LTE + relay when the UNO Q is powered up, nothing is changed at boot.
# Logs every 2 s, against the kernel's uptime, until telemetry has flowed for a minute
# or 10 min have passed, to ~/audio_check/boot_lte_<time>.log. Run once from @reboot:
#   @reboot sh $HOME/audio_check/boot_to_lte.sh
# The entry and boot_lte.done are cleared only after a complete run, so a power blip while
# plugging in the battery does not use it up.
cd "$(dirname "$0")"
[ -e boot_lte.done ] && exit 0
LOG=$PWD/boot_lte_$(date +%Y%m%d_%H%M%S).log
exec >>"$LOG" 2>&1
echo "boot to LTE $(date)"
first=
while :; do
  up=$(cut -d' ' -f1 /proc/uptime)
  line=$(curl -s -m 3 127.0.0.1:8080/api/podium | python3 -c '
import json,sys
try:d=json.load(sys.stdin)
except Exception:print("web not answering");sys.exit()
c,s=d["config"],d["status"]
print(c["link"],c["destination"],s["state"],"frames",s["frames"],"reconnects",s["reconnects"],s.get("last_failure_stage"),s.get("last_failure_reason"))' 2>&1)
  echo "$up $line"
  case "$line" in
    *" frames 0 "*|"web not answering"*) ;;
    *frames*) [ -z "$first" ] && { first=$up; echo "FIRST TELEMETRY at uptime $up s"; } ;;
  esac
  [ -n "$first" ] && awk "BEGIN{exit !($up - $first > 60)}" && break
  awk "BEGIN{exit !($up > 600)}" && { echo "no telemetry within 600 s of boot"; break; }
  sleep 2
done
curl -s 127.0.0.1:8080/api/podium/events > "$LOG.events.json"
journalctl -b --no-pager -o short-monotonic -u ecocapture-web-start -u ecocapture-mcu-start -u ecocapture-mcu-supervisor 2>/dev/null | tail -40 > "$LOG.services"
date > boot_lte.done; crontab -r 2>/dev/null; sync
echo "done $(date)"
