#!/usr/bin/env python3
"""set the badge's LED colours by feeding its running ws2812 lightgene.

the badge boots with a BIO program already running ("bio active" on the panel). the
reference kernel for that is `xous-core/libs/bio-lib/src/ws2812.rs`, and its protocol
is entirely FIFO-driven, so if the badge is running it we can recolour the strip
without uploading any code at all:

    FIFO1 in   first word ever = the GPIO pin mask (sent once, at init)
               thereafter, one word per LED, **last LED in the chain first**
                 bit 24     0 = more to come, 1 = commit and transmit
                 bits 23:16 green
                 bits 15:8  red
                 bits 7:0   blue
    FIFO2 out  a token once the strip has been written

`bio tx <value> [repeat]` is the console's way into that queue, and it takes a repeat
count, so a whole uniform strip is two commands.

  ./tools/leds.py --palette rose-pine
  ./tools/leds.py --solid eb6f92 --count 8
  ./tools/leds.py --off
"""

import argparse
import re
import sys
import time

import serial

DEFAULT_PORT = "/dev/ttyACM0"
BAUD = 1_000_000
COMMIT = 1 << 24

# rosé pine, azzie's colourscheme
ROSE_PINE = ["eb6f92", "f6c177", "ebbcba", "31748f", "9ccfd8", "c4a7e7"]
UD2 = ["ffffff", "888888", "ffffff", "888888"]

PALETTES = {"rose-pine": ROSE_PINE, "ud2": UD2}


def grb(hex_rgb: str) -> int:
    """ws2812 wants G,R,B rather than R,G,B."""
    h = hex_rgb.lstrip("#")
    if len(h) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise SystemExit(f"error: {hex_rgb!r} is not a 6-digit hex colour")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (g << 16) | (r << 8) | b


def send(ser: serial.Serial, line: str, wait: float = 0.6) -> str:
    data = (line + "\n").encode()
    # 24-byte pieces: whole-line bursts overrun the console's keyboard buffer, and
    # byte-at-a-time corrupts input outright (`ver` echoes as `vrr`).
    for i in range(0, len(data), 24):
        ser.write(data[i:i + 24])
        ser.flush()
        time.sleep(0.02)
    time.sleep(wait)
    return ser.read(200_000).decode("utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--palette", choices=sorted(PALETTES))
    mode.add_argument("--solid", metavar="RRGGBB")
    mode.add_argument("--off", action="store_true")
    ap.add_argument("--count", type=int, default=8, help="LEDs in the chain (default 8)")
    ap.add_argument("--brightness", type=float, default=0.25,
                    help="0..1 scale, default 0.25. these are bright and close to your face")
    ap.add_argument("--port", default=DEFAULT_PORT)
    args = ap.parse_args()

    if args.count < 1:
        raise SystemExit("error: --count must be at least 1")

    if args.off:
        colours = ["000000"] * args.count
    elif args.solid:
        colours = [args.solid] * args.count
    else:
        pal = PALETTES[args.palette]
        colours = [pal[i % len(pal)] for i in range(args.count)]

    scale = max(0.0, min(1.0, args.brightness))
    words = []
    for c in colours:
        v = grb(c)
        g, r, b = (v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF
        words.append((int(g * scale) << 16) | (int(r * scale) << 8) | int(b * scale))

    # the chain is fed last-LED-first, and the final word carries the commit bit
    words.reverse()

    try:
        ser = serial.Serial(args.port, BAUD, timeout=0.3)
    except serial.SerialException as exc:
        print(f"error: cannot open {args.port}: {exc}", file=sys.stderr)
        return 1

    with ser:
        time.sleep(0.4)
        ser.reset_input_buffer()
        send(ser, "", 0.6)

        for w in words[:-1]:
            send(ser, f"bio tx {w}", 0.35)
        last = words[-1] | COMMIT
        out = send(ser, f"bio tx {last}", 1.0)

        print(f"[+] sent {len(words)} LED words, commit on the last")
        if "ERR" in out.splitlines()[-3:] if out else False:
            print("    device answered ERR to the commit", file=sys.stderr)
        tail = " | ".join(l.strip() for l in out.splitlines() if l.strip())[-200:]
        print(f"    console: {tail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
