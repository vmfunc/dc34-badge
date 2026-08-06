#!/usr/bin/env python3
"""probe the badge's undocumented `image` verb.

it takes the same 70-byte framing as `bio` (the published loader's docstring says the
format is "identical to send_image.py" and calls the payload "pixel data"):

  [0:2]   u16 big-endian chunk index
  [2:66]  64 bytes of data
  [66:70] u32 big-endian crc32 over bytes [0:66]

the index is a **u16**, so it can address 65536 * 64 = 4 MiB of offset. if the
firmware does not bound it before using it as a write offset, that is an arbitrary
write. this walks the index upward to find where the acceptance stops, which is the
bound, and reports whether one exists at all.

  ./tools/image_probe.py --scan
  ./tools/image_probe.py --index 0 --index 4095
"""

import argparse
import base64
import struct
import sys
import time
import zlib

import serial

DEFAULT_PORT = "/dev/ttyACM0"
BAUD = 1_000_000
CHUNK_DATA_SIZE = 64


def frame(index: int, data: bytes) -> str:
    payload = struct.pack(">H", index) + data.ljust(CHUNK_DATA_SIZE, b"\x00")[:CHUNK_DATA_SIZE]
    wire = payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFF_FFFF)
    return base64.b64encode(wire).decode()


def prime(ser: serial.Serial) -> None:
    time.sleep(0.4)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(b"\r\n")
    ser.flush()
    time.sleep(0.8)
    ser.read(200_000)


def send(ser: serial.Serial, index: int, data: bytes, wait: float = 0.7) -> str:
    ser.write(f"image {frame(index, data)}\n".encode())
    ser.flush()
    time.sleep(wait)
    raw = ser.read(200_000).decode("utf-8", errors="replace")
    lines = [
        ln.strip() for ln in raw.splitlines()
        if ln.strip() and not ln.strip().startswith("[console]") and not ln.strip().startswith("image ")
    ]
    return " | ".join(lines) if lines else "<silence>"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", type=int, action="append", default=[])
    ap.add_argument("--scan", action="store_true", help="walk the index upward to find the bound")
    ap.add_argument("--port", default=DEFAULT_PORT)
    args = ap.parse_args()

    # a recognisable payload, so if it lands in a framebuffer it is visible on the panel
    payload = bytes(range(64))

    try:
        ser = serial.Serial(args.port, BAUD, timeout=0.3)
    except serial.SerialException as exc:
        print(f"error: cannot open {args.port}: {exc}", file=sys.stderr)
        return 1

    with ser:
        prime(ser)

        indices = list(args.index)
        if args.scan or not indices:
            # geometric walk: cheap, and brackets the bound wherever it is
            indices = [0, 1, 2, 63, 64, 127, 128, 255, 256, 511, 512,
                       1023, 1024, 2047, 2048, 4095, 4096, 8191, 8192,
                       16383, 16384, 32767, 32768, 65535]

        accepted, rejected = [], []
        for idx in indices:
            resp = send(ser, idx, payload)
            verdict = "ACCEPTED" if "ERR" not in resp else "rejected"
            (accepted if verdict == "ACCEPTED" else rejected).append(idx)
            print(f"index {idx:6d} (offset 0x{idx*64:07x})  {verdict:9s}  {resp[:110]}")

    print(f"\naccepted: {accepted}")
    print(f"rejected: {rejected}")
    if accepted and max(accepted) > 4096:
        print("\n!! the index is not tightly bounded. that is a write offset under our control.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
