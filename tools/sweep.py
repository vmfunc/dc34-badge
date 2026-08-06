#!/usr/bin/env python3
"""map which pages a BIO program on this badge is allowed to read.

there is no host->core data path: "bio tx" injects into the same queue the core
pushes to, so a value sent with tx comes straight back on rx without the core ever
seeing it. the target address therefore has to be assembled into the program, which
means one upload per probe.

the oracle, per the RTL (bio_bdma.sv:2576): an out-of-window read is redirected to
`gutter`, which resets to 0. nothing answers at address 0, so the read never retires
and the core waits on it forever. the program pushes a marker BEFORE the load, so:

  marker, then a value    -> the read retired          -> ALLOWED
  marker, then silence    -> the read never retired    -> filtered
  nothing at all          -> the program never ran     -> inconclusive

  ./tools/sweep.py 0x603E2080 0x60000000
  ./tools/sweep.py --range 0x603E0000 0x603F0000 --step 0x1000
"""

import argparse
import pathlib
import re
import sys
import tempfile
import time

import serial

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from bio_upload import assemble, upload  # noqa: E402

DEFAULT_PORT = "/dev/ttyACM0"
BAUD = 1_000_000
MARKER = 0x11111111
RX_RE = re.compile(r"cmds::bio:\s*([0-9a-fA-F]{1,8})\s*\(src/cmds/bio\.rs:508\)")

# 8 instructions per tile at 4 bytes each; 0xF00 max means 120 tiles fits with room
TILES = 110

TEMPLATE = """\
.option norvc
.text
.globl _start
_start:
.rept {tiles}
    li   a0, {addr}           # the address under test, baked in
    lw   a1, 0(a0)            # hangs forever if the page is outside every window
1:
    mv   x16, a1              # push the result continuously, never stop
    mv   x17, a1
    mv   x18, a1
    mv   x19, a1
    j    1b
.endr
"""


def prime(ser: serial.Serial) -> None:
    time.sleep(0.4)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(b"\r\n")
    ser.flush()
    time.sleep(0.8)
    ser.read(200_000)


def rx(ser: serial.Serial, wait: float = 0.6):
    ser.write(b"bio rx\n")
    ser.flush()
    time.sleep(wait)
    raw = ser.read(200_000).decode("utf-8", errors="replace")
    if "timeout" in raw:
        return None
    m = RX_RE.search(raw)
    return int(m.group(1), 16) if m else None


def drain(ser: serial.Serial, limit: int = 40) -> None:
    for _ in range(limit):
        if rx(ser, 0.3) is None:
            return


def build(addr: int) -> bytes:
    with tempfile.TemporaryDirectory() as td:
        src = pathlib.Path(td) / "sweep.S"
        src.write_text(TEMPLATE.format(tiles=TILES, addr=f"0x{addr:08x}"))
        return assemble(src)


def probe(ser: serial.Serial, addr: int):
    """-> (verdict, value)"""
    drain(ser)
    upload(ser, build(addr), None, 1_000_000)

    for _ in range(4):
        v = rx(ser)
        if v is not None:
            return "allowed", v
    return "filtered", None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("addresses", nargs="*")
    ap.add_argument("--range", nargs=2, metavar=("START", "END"))
    ap.add_argument("--step", default="0x1000")
    ap.add_argument("--port", default=DEFAULT_PORT)
    args = ap.parse_args()

    targets = [int(a, 0) for a in args.addresses]
    if args.range:
        start, end, step = int(args.range[0], 0), int(args.range[1], 0), int(args.step, 0)
        targets += list(range(start, end, step))
    if not targets:
        print("error: give addresses or --range", file=sys.stderr)
        return 2

    try:
        ser = serial.Serial(args.port, BAUD, timeout=0.3)
    except serial.SerialException as exc:
        print(f"error: cannot open {args.port}: {exc}", file=sys.stderr)
        return 1

    allowed = []
    with ser:
        prime(ser)
        for addr in targets:
            verdict, value = probe(ser, addr)
            if verdict == "allowed":
                allowed.append((addr, value))
                print(f"0x{addr:08x}  ALLOWED   {value:08x}")
            else:
                print(f"0x{addr:08x}  {verdict}")

    print(f"\n{len(allowed)} readable of {len(targets)} probed")
    for addr, value in allowed:
        print(f"  0x{addr:08x} = {value:08x}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
