#!/usr/bin/env python3
"""talk to the badge console, with a guard rail on the commands that end the game.

  ./tools/console.py help
  ./tools/console.py "bio ready" "bio clear"
  ./tools/console.py --raw-log run.log ver

everything sent and received is appended to captures/uart/ so the log is the record,
not this terminal's scrollback.
"""

import argparse
import datetime
import pathlib
import sys
import time

import serial

DEFAULT_PORT = "/dev/ttyACM0"
BAUD = 1_000_000
PROMPT = b"[console] "
CAPTURE_DIR = pathlib.Path(__file__).resolve().parent.parent / "captures" / "uart"

# commands that permanently destroy the badge or the flag. sending any of these is
# never a thing we want to do by reflex at 4am, so it takes an explicit override.
# matched as a substring against the lowercased command.
FORBIDDEN = {
    "self_destruct": "permanently wipes and bricks the chip, boot1 repl. no returns.",
    "void_my_warrantee": "the confirmation token for self_destruct.",
    "erase_secrets": "erases KEY_SLOTS, which contains THE_FLAG_1.",
    "lockdown": "irreversible boot lockdown, unclear blast radius.",
    "ate": "factory test entry, unknown blast radius near the FT-programmed flag.",
    "publock": "locks pubkey slots, irreversible.",
}


def check_forbidden(cmd: str, force: bool) -> None:
    low = cmd.lower()
    for needle, why in FORBIDDEN.items():
        if needle in low:
            if not force:
                print(f"refusing {cmd!r}: contains {needle!r}, {why}", file=sys.stderr)
                print("pass --i-know-what-this-does to override.", file=sys.stderr)
                raise SystemExit(1)
            print(f"!! sending forbidden command {cmd!r} because you insisted", file=sys.stderr)


def converse(port: str, cmds: list[str], settle: float, force: bool) -> int:
    for c in cmds:
        check_forbidden(c, force)

    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    log = CAPTURE_DIR / f"{datetime.datetime.now():%Y%m%d-%H%M%S}-console.log"

    try:
        ser = serial.Serial(port, BAUD, timeout=0.2)
    except serial.SerialException as exc:
        print(f"error: cannot open {port}: {exc}", file=sys.stderr)
        return 1

    transcript = bytearray()
    with ser:
        ser.reset_input_buffer()
        for cmd in cmds:
            ser.write(cmd.encode() + b"\r\n")
            ser.flush()
            transcript += f"\n>>> {cmd}\n".encode()

            # read until the prompt comes back, or we run out of patience. the badge
            # is fast; settle only bounds the pathological case.
            deadline = time.time() + settle
            got = bytearray()
            while time.time() < deadline:
                chunk = ser.read(4096)
                if chunk:
                    got += chunk
                    if got.rstrip().endswith(PROMPT.strip()):
                        break
            transcript += got
            sys.stdout.write(got.decode("utf-8", errors="replace"))
            sys.stdout.flush()

    log.write_bytes(transcript)
    print(f"\n[log: {log}]", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmds", nargs="+", help="commands to send, in order")
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--settle", type=float, default=2.0, help="seconds to wait per command")
    ap.add_argument("--i-know-what-this-does", dest="force", action="store_true")
    args = ap.parse_args()
    return converse(args.port, args.cmds, args.settle, args.force)


if __name__ == "__main__":
    sys.exit(main())
