#!/usr/bin/env python3
"""put a picture on the badge's 128x128 OLED via the console's `image` verb.

  ./tools/oled.py --ascii art/ud2.txt
  ./tools/oled.py --ascii art/ud2.txt --invert --preview out.png
  ./tools/oled.py --test-pattern

framebuffer format, from `libs/bao1x-hal/src/sh1107.rs`: the buffer is
`[u32; WIDTH*HEIGHT/32]` and the blitter maps a linear index with
`dst_x = dl % WIDTH; dst_y = dl / WIDTH`, so it is **linear row-major**, one bit per
pixel, 128*128/8 = 2048 bytes. that is exactly the payload `image` accepts (32 chunks
of 64 bytes). bit order within a byte is LSB-first, which is what packing a u32 array
little-endian gives you.

the wire framing is the same as `bio`:
  [0:2] u16 big-endian chunk index | [2:66] 64 bytes | [66:70] u32 big-endian crc32

writes are paced inside the line. the console's input runs through the keyboard
service, whose buffer overflows on a fast full-length line and then takes the whole
console down with it.
"""

import argparse
import base64
import pathlib
import struct
import sys
import time
import zlib

import serial
from PIL import Image, ImageDraw, ImageFont

DEFAULT_PORT = "/dev/ttyACM0"
BAUD = 1_000_000
W = H = 128
FB_BYTES = W * H // 8
CHUNK = 64
N_CHUNKS = FB_BYTES // CHUNK          # 32


# real monospace faces, best first. PIL's built-in default is a ~6x11 bitmap, far too
# coarse to survive being scaled down; a proper outline face keeps the strokes.
FONT_CANDIDATES = [
    "/nix/store/6sxv3pjlx8xb73jbnfgplbdn1qb42i7k-dejavu-fonts-2.37/share/fonts/truetype/DejaVuSansMono.ttf",
    "/nix/store/f674l7sdlbyxddm6va02dp1gfjwprfmy-hack-font-3.003/share/fonts/truetype/Hack-Regular.ttf",
]


def _mono_font(size: int):
    import subprocess
    paths = list(FONT_CANDIDATES)
    try:
        found = subprocess.run(["fc-match", "-f", "%{file}", "monospace"],
                               capture_output=True, text=True, timeout=5).stdout.strip()
        if found:
            paths.append(found)
    except (OSError, subprocess.SubprocessError):
        pass
    for candidate in paths:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_ascii(path: pathlib.Path, margin: int = 2) -> Image.Image:
    """rasterise ascii art, then scale the whole block to fit the panel.

    the art is a picture made of characters, not text to be read, so it is rendered
    at the font's native size and scaled as a block. individual glyphs blur; the
    silhouette survives, which is the part that matters.
    """
    lines = path.read_text(encoding="utf-8", errors="replace").rstrip("\n").split("\n")
    if not lines:
        raise SystemExit(f"error: {path} is empty")

    font = _mono_font(size=24)
    box = font.getbbox("M")
    cw, ch = box[2] - box[0], int((box[3] - box[1]) * 1.35)
    cols = max(len(ln) for ln in lines)

    big = Image.new("1", (max(cols * cw + cw, 1), max(len(lines) * ch + ch, 1)), 0)
    d = ImageDraw.Draw(big)
    for row, line in enumerate(lines):
        d.text((0, row * ch), line, font=font, fill=1)

    # crop to the ink. the art has leading whitespace and a ragged right edge, so the
    # nominal grid is much larger than the drawn glyphs and scaling by it wastes the
    # panel.
    ink = big.getbbox()
    if ink:
        big = big.crop(ink)

    avail = W - 2 * margin
    scale = min(avail / big.width, avail / big.height)
    new = (max(1, int(big.width * scale)), max(1, int(big.height * scale)))
    # BILINEAR then threshold keeps strokes that NEAREST would drop entirely
    shrunk = big.convert("L").resize(new, Image.BILINEAR).point(lambda v: 255 if v > 60 else 0, "1")

    canvas = Image.new("1", (W, H), 0)
    canvas.paste(shrunk, ((W - new[0]) // 2, (H - new[1]) // 2))
    return canvas


def test_pattern() -> Image.Image:
    """unambiguous orientation reference: filled top-left quadrant plus a border."""
    img = Image.new("1", (W, H), 0)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=1)
    d.rectangle([4, 4, W // 2 - 1, H // 2 - 1], fill=1)
    d.line([0, 0, W - 1, H - 1], fill=1)
    return img


def pack(img: Image.Image, invert: bool, msb_first: bool) -> bytes:
    """pack row-major, one bit per pixel, into the firmware's word layout.

    the framebuffer is [u32; 512] and pixel i is bit (i % 32) of word (i / 32),
    LSB-first, per sh1107.rs. but cmds/image.rs rebuilds each word with
    `u32::from_be_bytes([d0, d1, d2, d3])`, so within every 4-byte group the byte
    order is **big-endian**: d0 supplies bits 31..24, not 7..0. packing those four
    bytes in natural order silently transposes the image in 8-pixel blocks.
    """
    px = img.load()
    out = bytearray(FB_BYTES)
    for y in range(H):
        for x in range(W):
            on = bool(px[x, y])
            if invert:
                on = not on
            if not on:
                continue
            i = y * W + x
            word, k = divmod(i, 32)
            byte_in_word = 3 - (k // 8)          # big-endian within the word
            bit = (7 - (k % 8)) if msb_first else (k % 8)
            out[word * 4 + byte_in_word] |= 1 << bit
    return bytes(out)


def frame(index: int, data: bytes) -> str:
    payload = struct.pack(">H", index) + data
    return base64.b64encode(payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFF_FFFF)).decode()


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


def send_chunk(ser: serial.Serial, fb: bytes, idx: int):
    """offer one chunk, return the verdict once the prompt comes back."""
    wire = frame(idx, fb[idx * CHUNK:(idx + 1) * CHUNK])
    ser.reset_input_buffer()
    write_paced(ser, f"image {wire}\n".encode())
    deadline = time.time() + 8.0
    buf = ""
    verdict = None
    while time.time() < deadline:
        got = ser.read(4096)
        if got:
            buf += got.decode("utf-8", errors="replace")
        verdict = _verdict(buf)
        if verdict and buf.rstrip().endswith("[console]"):
            break
    return verdict or "ERR"


def _verdict(buf: str):
    """the device's answer is a line that is *exactly* a token.

    matching a bare substring does not work: the console echoes the command back, and
    a base64 payload happily contains "OK" or "ERR" inside it. that is what made the
    failures look random, they tracked the image data rather than the link.
    """
    for raw in buf.splitlines():
        line = raw.strip()
        if line.startswith("[console]"):
            line = line[len("[console]"):].strip()
        if line in ("SUCCESS", "OK", "ERR"):
            return line
    return None


def resync(ser: serial.Serial, fb: bytes):
    """find the chunk index the device expects, by offering each in turn.

    an accepted probe also *consumes* that index, so the return value is the next one
    to send. sending the same image means the chunks already banked from an aborted
    run are the ones we wanted anyway, so resuming mid-sequence still yields the right
    framebuffer.
    """
    for idx in range(N_CHUNKS):
        verdict = send_chunk(ser, fb, idx)
        if verdict == "SUCCESS":
            return N_CHUNKS
        if verdict == "OK":
            return idx + 1
        time.sleep(0.15)
    return None


def upload(ser: serial.Serial, fb: bytes, delay: float) -> bool:
    time.sleep(0.4)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(b"\r\n")
    ser.flush()
    time.sleep(0.8)
    ser.read(200_000)

    # not a sequence after all: image_probe showed every index below 32 is accepted
    # on its own, so an ERR is line corruption rather than a position mismatch. retry
    # the same index; there is nothing to resynchronise.
    for i in range(N_CHUNKS):
        verdict = None
        for _ in range(6):
            verdict = send_chunk(ser, fb, i)
            if verdict in ("OK", "SUCCESS"):
                break
            time.sleep(0.1)
        if verdict not in ("OK", "SUCCESS"):
            print(f"\nerror: chunk {i} rejected after retries", file=sys.stderr)
            return False
        print(f"\r[*] chunk {i + 1}/{N_CHUNKS}", end="", flush=True)
        if verdict == "SUCCESS":
            break
        time.sleep(delay)

    print("\n[+] image accepted")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--ascii", type=pathlib.Path, help="ascii-art text file to rasterise")
    src.add_argument("--image", type=pathlib.Path, help="any image file, scaled and dithered")
    src.add_argument("--test-pattern", action="store_true")
    ap.add_argument("--invert", action="store_true", help="flip black and white")
    ap.add_argument("--msb-first", action="store_true", help="flip bit order within each byte")
    ap.add_argument("--preview", type=pathlib.Path, help="write a png of exactly what is sent")
    ap.add_argument("--dry-run", action="store_true", help="render and preview, send nothing")
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--delay", type=float, default=0.15)
    args = ap.parse_args()

    if args.ascii:
        img = render_ascii(args.ascii)
    elif args.image:
        src_img = Image.open(args.image).convert("L")
        src_img.thumbnail((W, H), Image.LANCZOS)
        canvas = Image.new("L", (W, H), 0)
        canvas.paste(src_img, ((W - src_img.width) // 2, (H - src_img.height) // 2))
        img = canvas.convert("1")
    else:
        img = test_pattern()

    if args.preview:
        img.save(args.preview)
        print(f"[*] preview written to {args.preview}")

    fb = pack(img, args.invert, args.msb_first)
    print(f"[*] {len(fb)} bytes, {sum(bin(b).count('1') for b in fb)} pixels lit")

    if args.dry_run:
        return 0

    try:
        ser = serial.Serial(args.port, BAUD, timeout=0.3)
    except serial.SerialException as exc:
        print(f"error: cannot open {args.port}: {exc}", file=sys.stderr)
        return 1
    with ser:
        return 0 if upload(ser, fb, args.delay) else 1


if __name__ == "__main__":
    sys.exit(main())
