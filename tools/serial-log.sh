#!/usr/bin/env bash
# timestamped serial capture into captures/uart/. read-only by default, so you can
# leave it running on a second terminal all con without touching the target.
#
#   ./tools/serial-log.sh /dev/ttyACM0 1000000
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
port="${1:-/dev/ttyACM0}"
# the badge's xous console is 1000000 8n1, not the usual 115200. wrong baud looks
# exactly like "the badge has no console", which is how you skip past the console.
baud="${2:-1000000}"

if [[ ! -e "$port" ]]; then
  echo "error: $port not present. plugged in? check 'dmesg | tail' or 'ls /dev/tty*'" >&2
  exit 1
fi

out="$root/captures/uart/$(date +%Y%m%d-%H%M%S)-$(basename "$port")-$baud.log"

echo "logging $port @ $baud -> ${out#"$root"/}   (ctrl-a ctrl-x to quit picocom)"

# --imap lfcrlf keeps the log readable when the target only sends LF.
# picocom's --logfile does the tee for us and survives the target rebooting.
exec picocom --baud "$baud" --imap lfcrlf --logfile "$out" "$port"
