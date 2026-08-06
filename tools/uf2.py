#!/usr/bin/env python3
"""uf2 inspect / carve.

the baochip bootloader takes UF2, so every artifact we handle (loader, xous, apps)
arrives in this container. ghidra wants a flat image at the right base, and UF2
carries that base in every block header, so this reads it out rather than guessing.

  ./tools/uf2.py info  apps.uf2
  ./tools/uf2.py carve apps.uf2 -o apps.bin
"""

import argparse
import struct
import sys
from pathlib import Path

# microsoft UF2 spec: fixed 512-byte blocks, 32-byte header, 476-byte payload area.
BLOCK_SIZE = 512
HEADER_FMT = "<8I"
HEADER_SIZE = struct.calcsize(HEADER_FMT)
PAYLOAD_MAX = 476
MAGIC_START0 = 0x0A324655  # "UF2\n"
MAGIC_START1 = 0x9E5D5157
MAGIC_END = 0x0AB16F30

FLAG_NOT_MAIN_FLASH = 0x00000001
FLAG_FILE_CONTAINER = 0x00001000
FLAG_FAMILY_ID = 0x00002000
FLAG_MD5_PRESENT = 0x00004000
FLAG_EXTENSION_TAGS = 0x00008000


class Uf2Error(Exception):
    """malformed container. never guess past one, a bad base address is hours lost."""


def parse_blocks(raw: bytes):
    """yield (target_addr, payload) per block, validating every magic as we go."""
    if len(raw) % BLOCK_SIZE != 0:
        raise Uf2Error(f"length {len(raw)} is not a multiple of {BLOCK_SIZE}")

    for index in range(len(raw) // BLOCK_SIZE):
        block = raw[index * BLOCK_SIZE:(index + 1) * BLOCK_SIZE]
        start0, start1, flags, addr, size, _blkno, _total, famid = struct.unpack(
            HEADER_FMT, block[:HEADER_SIZE]
        )

        if start0 != MAGIC_START0 or start1 != MAGIC_START1:
            raise Uf2Error(f"block {index}: bad start magic")
        if struct.unpack("<I", block[-4:])[0] != MAGIC_END:
            raise Uf2Error(f"block {index}: bad end magic")
        if size > PAYLOAD_MAX:
            raise Uf2Error(f"block {index}: payload size {size} exceeds {PAYLOAD_MAX}")

        # blocks flagged not-main-flash carry metadata, not image bytes. skipping them
        # is what keeps the carved image byte-accurate.
        if flags & FLAG_NOT_MAIN_FLASH:
            continue

        yield addr, flags, famid, block[HEADER_SIZE:HEADER_SIZE + size]


def cmd_info(path: Path) -> int:
    raw = path.read_bytes()
    blocks = list(parse_blocks(raw))
    if not blocks:
        print("no flashable blocks", file=sys.stderr)
        return 1

    addrs = [a for a, _, _, _ in blocks]
    total = sum(len(p) for _, _, _, p in blocks)
    flags = blocks[0][1]
    famid = blocks[0][2]

    print(f"file        {path}")
    print(f"blocks      {len(blocks)} flashable / {len(raw) // BLOCK_SIZE} total")
    print(f"base addr   0x{min(addrs):08x}")
    print(f"end addr    0x{max(addrs) + len(blocks[-1][3]):08x}")
    print(f"payload     {total} bytes")
    if flags & FLAG_FAMILY_ID:
        print(f"family id   0x{famid:08x}")
    for name, bit in (
        ("file container", FLAG_FILE_CONTAINER),
        ("md5 present", FLAG_MD5_PRESENT),
        ("extension tags", FLAG_EXTENSION_TAGS),
    ):
        if flags & bit:
            print(f"flag        {name}")

    gaps = 0
    for (a, _, _, p), (b, _, _, _) in zip(blocks, blocks[1:]):
        if a + len(p) != b:
            gaps += 1
    if gaps:
        print(f"note        {gaps} non-contiguous gap(s), carve pads them with 0xff")
    return 0


def cmd_carve(path: Path, out: Path) -> int:
    blocks = list(parse_blocks(path.read_bytes()))
    if not blocks:
        print("no flashable blocks", file=sys.stderr)
        return 1

    base = min(a for a, _, _, _ in blocks)
    end = max(a + len(p) for a, _, _, p in blocks)
    # 0xff is erased-state for flash-alikes, so padding reads as "not programmed"
    # rather than as plausible zeroed code.
    image = bytearray(b"\xff" * (end - base))

    for addr, _flags, _famid, payload in blocks:
        image[addr - base:addr - base + len(payload)] = payload

    out.write_bytes(image)
    print(f"wrote {len(image)} bytes to {out}")
    print(f"load at 0x{base:08x}  (ghidra: rv32imac, little endian, this base)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_info = sub.add_parser("info", help="header summary, base address, flags")
    p_info.add_argument("file", type=Path)

    p_carve = sub.add_parser("carve", help="flatten to a raw image for disassembly")
    p_carve.add_argument("file", type=Path)
    p_carve.add_argument("-o", "--out", type=Path, required=True)

    args = ap.parse_args()

    if not args.file.is_file():
        print(f"error: {args.file} is not a file", file=sys.stderr)
        return 2

    try:
        if args.cmd == "info":
            return cmd_info(args.file)
        return cmd_carve(args.file, args.out)
    except Uf2Error as exc:
        print(f"error: not a valid uf2: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
