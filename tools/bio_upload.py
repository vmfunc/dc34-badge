#!/usr/bin/env python3
"""assemble and upload a BIO program to the badge over the console.

reimplements baochip/bio-loader's wire format rather than depending on it, so the
solve runs from a clean checkout inside `nix develop` with no pipx step.

  ./tools/bio_upload.py --asm re/scripts/probe.S
  ./tools/bio_upload.py --bin prog.bin --clk 1MHz --pins 16,18
  ./tools/bio_upload.py --clear

wire format, per chunk, base64'd behind the literal "bio ":
  [0:2]   u16 big-endian chunk index
  [2:66]  64 bytes of code
  [66:70] u32 big-endian crc32 over bytes [0:66]

the device answers OK per chunk, SUCCESS on the 64th, CLEAR for a clear. a short
program is padded on-device with "bio pad".
"""

import argparse
import base64
import pathlib
import struct
import subprocess
import sys
import tempfile
import time
import zlib

import serial

DEFAULT_PORT = "/dev/ttyACM0"
BAUD = 1_000_000
MAX_CODE_BYTES = 0xF00
CHUNK_DATA_SIZE = 64
NUM_CHUNKS = MAX_CODE_BYTES // CHUNK_DATA_SIZE
SETTLE = 0.6

# BIO cores are RV32E, but x16..x31 are the FIFO/GPIO aliases and a real rv32e
# assembler rejects them. assemble as rv32imac so the register names encode, the
# BIO decodes the result on its own terms.
MARCH = "rv32imac"
MABI = "ilp32"


def make_chunk(index: int, data: bytes) -> bytes:
    assert len(data) == CHUNK_DATA_SIZE
    payload = struct.pack(">H", index) + data
    return payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFF_FFFF)


def assemble(src: pathlib.Path) -> bytes:
    """.S -> raw little-endian instruction stream, via the rv32 cross toolchain."""
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        obj, elf, binf = tmp / "a.o", tmp / "a.elf", tmp / "a.bin"
        try:
            subprocess.run(
                ["riscv32-none-elf-as", f"-march={MARCH}", f"-mabi={MABI}",
                 "-o", str(obj), str(src)],
                check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["riscv32-none-elf-ld", "-Ttext=0", "--oformat=elf32-littleriscv",
                 "-o", str(elf), str(obj)],
                check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["riscv32-none-elf-objcopy", "-O", "binary", str(elf), str(binf)],
                check=True, capture_output=True, text=True,
            )
        except FileNotFoundError as exc:
            print(f"error: {exc}. are you inside `nix develop`?", file=sys.stderr)
            raise SystemExit(1)
        except subprocess.CalledProcessError as exc:
            print(f"error: assembling {src} failed:\n{exc.stderr}", file=sys.stderr)
            raise SystemExit(1)
        return binf.read_bytes()


def readline(ser: serial.Serial, deadline: float) -> str:
    """one response line, skipping the console's echo of what we just sent."""
    buf = bytearray()
    while time.time() < deadline:
        b = ser.read(1)
        if not b:
            continue
        if b in (b"\n", b"\r"):
            line = buf.decode("utf-8", errors="replace").strip()
            buf.clear()
            # the console echoes the command and reprints its prompt; neither is a reply
            if not line or line.startswith("bio ") or line.startswith("[console]"):
                continue
            return line
        buf += b
    return ""


def write_paced(ser: serial.Serial, line: bytes, piece: int = 24, gap: float = 0.03) -> None:
    """write a line in a few sizeable pieces.

    two failure modes bracket this. writing the whole line back-to-back with the next
    one overruns the console's keyboard buffer ("Input overflow to N, dropping keys!").
    writing a byte at a time is *worse*: each tiny write becomes its own USB packet and
    the firmware mis-samples it, so `ver` echoes back as `vrr`. corrupted input that
    still parses is far more dangerous than input that is dropped loudly.

    measured on the badge: 24-byte pieces echo correctly, and the gap between lines is
    what actually prevents the overflow.
    """
    for i in range(0, len(line), piece):
        ser.write(line[i:i + piece])
        ser.flush()
        time.sleep(gap)


def command(ser: serial.Serial, line: str, expect: tuple[str, ...], timeout: float = 5.0) -> str:
    """send, then drain lines until one matches. the badge emits log lines and
    multi-line acks (pad answers OK *then* SUCCESS), so first-line matching desyncs."""
    write_paced(ser, line.encode() + b"\n")
    deadline = time.time() + timeout
    seen = []
    while time.time() < deadline:
        resp = readline(ser, deadline)
        if not resp:
            break
        seen.append(resp)
        if resp in expect:
            return resp
    raise RuntimeError(f"{line!r} -> {seen}, expected one of {expect}")


def upload(ser: serial.Serial, code: bytes, pins: str | None, clk: int | None,
           delay: float = 0.2) -> None:
    if not code:
        raise RuntimeError("empty program")
    if len(code) > MAX_CODE_BYTES:
        raise RuntimeError(f"program is {len(code)} bytes, max {MAX_CODE_BYTES}")

    command(ser, "bio ready", ("OK",))
    if pins:
        command(ser, f"bio pin {pins.replace(',', ' ')}", ("OK",))
    if clk:
        command(ser, f"bio clk {clk}", ("OK",))

    n = -(-len(code) // CHUNK_DATA_SIZE)
    print(f"[*] {len(code)} bytes -> {n}/{NUM_CHUNKS} chunks")
    for i in range(n):
        piece = code[i * CHUNK_DATA_SIZE:(i + 1) * CHUNK_DATA_SIZE].ljust(CHUNK_DATA_SIZE, b"\x00")
        wire = base64.b64encode(make_chunk(i, piece)).decode()
        resp = None
        for attempt in range(4):
            write_paced(ser, f"bio {wire}\n".encode())
            # drain until an actual verdict. the firmware interleaves log lines
            # (keyboard overflow warnings, lightgenes chatter) with its replies, and
            # taking the first line reads one of those as the answer.
            deadline = time.time() + 5.0
            resp = None
            while time.time() < deadline:
                line = readline(ser, deadline)
                if not line:
                    break
                if line in ("OK", "SUCCESS", "ERR"):
                    resp = line
                    break
            if resp in ("OK", "SUCCESS"):
                break
            time.sleep(0.5)
        if resp not in ("OK", "SUCCESS"):
            raise RuntimeError(f"chunk {i} -> {resp!r}")
        if resp == "SUCCESS":
            break
        # the console's keyboard buffer overflows and drops input if we push chunks
        # back to back ("Input overflow to N, dropping keys!"). pace them.
        time.sleep(delay)

    if n < NUM_CHUNKS:
        # the published loader documents SUCCESS here; this badge answers OK and
        # then SUCCESS once the pad actually fills the last slot. accept either.
        command(ser, "bio pad", ("SUCCESS", "OK"))
    command(ser, "bio reload", ("BIO load successful", "OK"))
    print("[+] loaded and running")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--asm", type=pathlib.Path, help="assembly source to build and send")
    src.add_argument("--bin", type=pathlib.Path, help="pre-built raw binary to send")
    src.add_argument("--clear", action="store_true", help="wipe the loaded program and exit")
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--pins", help="comma or space separated pad numbers")
    ap.add_argument("--clk", type=int, help="quantum clock in Hz")
    ap.add_argument("--slow", action="store_true",
                    help="one byte at a time with a long gap; use on a freshly booted "
                         "badge, whose console wedges under fast input")
    ap.add_argument("--delay", type=float, default=0.2,
                    help="seconds between chunks; the console drops input if pushed too fast")
    ap.add_argument("--listen", type=float, default=0.0,
                    help="seconds to keep reading the console after load")
    args = ap.parse_args()

    try:
        ser = serial.Serial(args.port, BAUD, timeout=0.2)
    except serial.SerialException as exc:
        print(f"error: cannot open {args.port}: {exc}", file=sys.stderr)
        return 1

    with ser:
        # prime the link: a stale half-line in the console's buffer makes the first
        # command land as a fragment, and the reply that comes back belongs to
        # whatever it completed rather than to us.
        time.sleep(0.4)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.write(b"\r\n")
        ser.flush()
        time.sleep(0.8)
        ser.read(200000)
        try:
            if args.clear:
                command(ser, "bio clear", ("CLEAR",))
                print("[+] cleared")
                return 0
            code = assemble(args.asm) if args.asm else args.bin.read_bytes()
            upload(ser, code, args.pins, args.clk, args.delay)
        except (RuntimeError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if args.listen:
            print(f"[*] listening {args.listen}s")
            end = time.time() + args.listen
            while time.time() < end:
                chunk = ser.read(4096)
                if chunk:
                    sys.stdout.write(chunk.decode("utf-8", errors="replace"))
                    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
