#!/usr/bin/env bash
# dump flash to firmware/dumps/<label>.bin, hash it, and print the manifest row.
#
#   ./tools/dump-firmware.sh 01-baseline rp2040
#   ./tools/dump-firmware.sh 01-baseline esp32 /dev/ttyUSB0
#   ./tools/dump-firmware.sh 01-baseline swd            # openocd, needs cfg below
#   ./tools/dump-firmware.sh 01-baseline baochip        # refuses, and explains why
#
# this does NOT write to the badge. dumping is the one operation that is always safe
# to do first, so it is the one thing wrapped in a script you can run half asleep.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
label="${1:-}"
target="${2:-}"
port="${3:-/dev/ttyUSB0}"

# rp2040 flash is 2MB on a stock pico module; override if the badge carries more.
RP2040_FLASH_SIZE=$((2 * 1024 * 1024))
ESP32_FLASH_SIZE=$((4 * 1024 * 1024))

if [[ -z "$label" || -z "$target" ]]; then
  echo "usage: $0 <label> <rp2040|esp32|swd> [port]" >&2
  exit 2
fi

out="$root/firmware/dumps/${label}.bin"
if [[ -e "$out" ]]; then
  echo "error: $out exists. dumps are immutable evidence, pick a new label." >&2
  exit 1
fi

case "$target" in
  baochip)
    # the dc34 badge. this mode deliberately does nothing except stop you.
    cat >&2 <<'WARN'
STOP.

the baochip UF2 bootloader (hold PROG, plug in, volume mounts as BAOCHIP) is a
WRITE path. it does not read the shipped image back out. so there is no
"dump first" on this badge, and that inverts the usual rule:

  copying apps.uf2 onto the badge OVERWRITES the shipped CTF app.
  there is no undo, and the stock firmware is not published until after the con.

before you flash anything at all:
  1. get everything you can without writing: serial console at 1000000 8n1
     (tools/serial-log.sh), usb descriptors (lsusb -v), observable behaviour.
  2. if you must run your own code, understand that you are trading the
     challenge for the ability to experiment. that may be the right trade.
     make it deliberately, not at 4am.
  3. anything you do build, keep the UF2 and carve it: tools/uf2.py.

WARN
    exit 1
    ;;
  rp2040)
    # -a saves the whole flash, not just the loaded program
    picotool save -a "$out"
    ;;
  esp32)
    esptool --port "$port" read_flash 0 "$ESP32_FLASH_SIZE" "$out"
    ;;
  swd)
    cfg="$root/re/scripts/openocd.cfg"
    if [[ ! -f "$cfg" ]]; then
      echo "error: write $cfg first (interface + target for this badge)" >&2
      exit 1
    fi
    openocd -f "$cfg" -c "init; dump_image $out 0x0 $RP2040_FLASH_SIZE; exit"
    ;;
  *)
    echo "error: unknown target '$target'" >&2
    exit 2
    ;;
esac

if [[ ! -s "$out" ]]; then
  echo "error: dump produced an empty file, not recording it" >&2
  rm -f "$out"
  exit 1
fi

hash="$(sha256sum "$out" | cut -d' ' -f1)"
size="$(stat -c %s "$out" 2>/dev/null || stat -f %z "$out")"
date="$(date +%F)"

echo "$hash  $(basename "$out")" >> "$root/firmware/dumps/.sha256"

echo
echo "dumped $size bytes to ${out#"$root"/}"
echo "paste into firmware/MANIFEST.md:"
echo
echo "| \`${label}.bin\` | \`${hash:0:16}\` | badge #? | $target | $date | |"
