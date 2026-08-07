#!/usr/bin/env bash
# flash a built image onto the badge through the boot1 UF2 bootloader.
#
#   ./tools/flash.sh <dir-with-uf2s>
#   ./tools/flash.sh firmware/dumps/dc34-badge-latest      # restore the stock image
#
# how to get the badge into the bootloader:
#   hold PROG (the button nearest the USB connector) while plugging in.
#   it enumerates as 1d50:6196 "Baochip-1x" with a mass storage volume labelled
#   BAOCHIP. press PROG again afterwards to run what you flashed.
#
# THIS IS THE IRREVERSIBLE ONE. writing a non-vendor-signed image makes boot1 run
# erase_secrets() before your code, which permanently wipes KEY_SLOTS, and
# THE_FLAG_1 (RRAM data slot 260) is in that set. the stock image can be restored
# from firmware/dumps/dc34-badge-latest; the FT-programmed flag value cannot.
set -euo pipefail

SRC="${1:-}"
LABEL="BAOCHIP"

if [[ -z "$SRC" ]]; then
  echo "usage: $0 <directory containing loader.uf2 / xous.uf2 / swap.uf2>" >&2
  exit 2
fi
if [[ ! -d "$SRC" ]]; then
  echo "error: $SRC is not a directory" >&2
  exit 2
fi

shopt -s nullglob
uf2s=("$SRC"/*.uf2)
if (( ${#uf2s[@]} == 0 )); then
  echo "error: no .uf2 files in $SRC" >&2
  exit 1
fi

dev="/dev/disk/by-label/$LABEL"
if [[ ! -e "$dev" ]]; then
  echo "error: no volume labelled $LABEL." >&2
  echo "       hold PROG while plugging the badge in, then re-run." >&2
  exit 1
fi

# use the mount the desktop already made if there is one, rather than fighting it
mnt="$(findmnt -n -o TARGET "$(readlink -f "$dev")" 2>/dev/null || true)"
if [[ -z "$mnt" ]]; then
  echo "error: $LABEL is present but not mounted." >&2
  echo "       mount it (clicking it in the file manager is fine), then re-run." >&2
  exit 1
fi

echo "target volume : $mnt"
echo "source        : $SRC"
printf 'files         :'; for f in "${uf2s[@]}"; do printf ' %s' "$(basename "$f")"; done; echo
echo
read -r -p "flash these onto the badge? this is irreversible for the flag. [type FLASH] " ok
if [[ "$ok" != "FLASH" ]]; then
  echo "aborted, nothing written."
  exit 1
fi

# loader first, then the kernel, then swap. the bootloader tolerates any order, but
# this way a partial copy leaves the most-recoverable state.
order=(loader.uf2 xous.uf2 swap.uf2 apps.uf2)
copied=0
for name in "${order[@]}"; do
  f="$SRC/$name"
  [[ -f "$f" ]] || continue
  echo "  -> $name ($(stat -c %s "$f") bytes)"
  cp "$f" "$mnt/"
  sync
  copied=$((copied + 1))
done

# anything not in the known order list, copied afterwards
for f in "${uf2s[@]}"; do
  base="$(basename "$f")"
  [[ " ${order[*]} " == *" $base "* ]] && continue
  echo "  -> $base ($(stat -c %s "$f") bytes)"
  cp "$f" "$mnt/"
  sync
  copied=$((copied + 1))
done

echo
echo "copied $copied file(s), synced."
echo "press PROG on the badge to run the new image."
