#!/usr/bin/env python3
"""read memory through the BIO peek primitive.

pairs with re/scripts/peek.S, which must already be loaded:

  ./tools/bio_upload.py --asm re/scripts/peek.S --clk 1000000
  ./tools/peek.py 0x603E2080 --words 8

the FIFO between host and BIO is deep and retains whatever a previous program left
in it, so every read drains to empty first. skipping that is how you end up reading
the last experiment's constants and believing them.
"""

import argparse
import re
import sys
import time

import serial

DEFAULT_PORT = "/dev/ttyACM0"
BAUD = 1_000_000
WORD = 4

# the console answers "bio rx" with a log line carrying the value in hex, and on an
# empty queue prints "timeout" first and then a fixed sentinel. the source line number
# in the log message is what separates an rx result from the tx command's own echo,
# and matching on it is the difference between reading memory and reading yourself.
RX_LINE = 508
TX_LINE = 542
VALUE_RE = re.compile(rf"cmds::bio:\s*([0-9a-fA-F]{{1,8}})\s*\(src/cmds/bio\.rs:{RX_LINE}\)")
EMPTY_SENTINEL = 0xEB1F646F


def read_reply(ser: serial.Serial, timeout: float = 3.0) -> tuple[int | None, bool]:
    """-> (value, queue_was_empty)."""
    deadline = time.time() + timeout
    buf = ""
    empty = False
    while time.time() < deadline:
        chunk = ser.read(4096)
        if chunk:
            buf += chunk.decode("utf-8", errors="replace")
            if "timeout" in buf:
                empty = True
            if buf.rstrip().endswith("[console]"):
                break
    vals = VALUE_RE.findall(buf)
    if not vals:
        return None, empty
    return int(vals[-1], 16), empty


def drain(ser: serial.Serial, limit: int = 64) -> int:
    """pop until the queue reports empty. returns how many stale words were tossed."""
    tossed = 0
    for _ in range(limit):
        ser.write(b"bio rx\n")
        ser.flush()
        val, empty = read_reply(ser)
        if empty or val is None or val == EMPTY_SENTINEL:
            return tossed
        tossed += 1
    print(f"warning: still draining after {limit} pops", file=sys.stderr)
    return tossed


def peek(ser: serial.Serial, addr: int) -> int | None:
    ser.write(f"bio tx 0x{addr:08x}\n".encode())
    ser.flush()
    read_reply(ser)  # the tx echo
    ser.write(b"bio rx\n")
    ser.flush()
    val, empty = read_reply(ser)
    if empty or val == EMPTY_SENTINEL:
        return None
    return val


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("address", help="start address, hex or decimal")
    ap.add_argument("--words", type=int, default=1)
    ap.add_argument("--port", default=DEFAULT_PORT)
    args = ap.parse_args()

    base = int(args.address, 0)

    try:
        ser = serial.Serial(args.port, BAUD, timeout=0.2)
    except serial.SerialException as exc:
        print(f"error: cannot open {args.port}: {exc}", file=sys.stderr)
        return 1

    raw = bytearray()
    with ser:
        ser.reset_input_buffer()
        tossed = drain(ser)
        if tossed:
            print(f"[*] drained {tossed} stale word(s) before starting")

        for i in range(args.words):
            addr = base + i * WORD
            val = peek(ser, addr)
            if val is None:
                print(f"0x{addr:08x}: <no data> (filtered, or the core stalled)")
                raw += b"\x00" * WORD
                continue
            raw += val.to_bytes(WORD, "little")
            print(f"0x{addr:08x}: {val:08x}")

    printable = "".join(chr(b) if 32 <= b < 127 else "." for b in raw)
    print(f"\nbytes : {raw.hex()}")
    print(f"ascii : {printable}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
