#!/usr/bin/env python3
"""wait for the badge to come up in boot1 and drive its REPL, read-only.

bootwait is enabled, so after a cold boot (hold power 6s, release, ~1s press to
power on) the bootloader stops at its own prompt instead of launching Xous. the USB
CDC re-enumerates as boot1's console, which is a *different* console from the Xous
one, with a different and much more powerful command set.

  ./tools/boot1.py                 # wait for the port, then run the safe read set
  ./tools/boot1.py --only ifr

what this sends, and nothing else:

  help        the real command list
  boardtype   which board the bootloader thinks this is
  idmode      identity mode state
  bootwait    check, so we know the counter state without spending another
  audit       boot integrity report
  ifr         dumps 0x6040_0000 for 0x400 bytes: per rrc.sv this is the RRAM
              partition and permission configuration. it ships (not feature-gated),
              and it is the best candidate we have for where the *second* flag lives.

everything destructive is refused outright, not merely omitted: self_destruct
(permanent brick), lockdown, ate (factory test entry, unknown blast radius next to
an FT-programmed flag), publock, uf2, altboot, paranoid and skipping. `peek` is not
sent because it is gated behind unsafe-debug and refuses the flag's address range
anyway.
"""

import argparse
import datetime
import pathlib
import sys
import time

import serial

DEFAULT_PORT = "/dev/ttyACM0"
BAUD = 1_000_000
CAPTURE = pathlib.Path(__file__).resolve().parent.parent / "captures" / "uart"

SAFE_SEQUENCE = ["help", "boardtype", "idmode", "bootwait check", "audit", "ifr"]

REFUSED = {
    "self_destruct": "permanent brick, no returns",
    "void_my_warrantee": "the self_destruct confirmation token",
    "lockdown": "irreversible boot lockdown",
    "ate": "factory test entry, unknown blast radius near the FT-programmed flag",
    "atecheck": "factory test adjacent, same reasoning",
    "publock": "irreversibly locks pubkey slots",
    "uf2": "writes firmware, which is the one thing that destroys the flag",
    "altboot": "changes the boot path",
    "paranoid": "one-way counter, spends budget",
    "skipping": "one-way counter, spends budget",
    "toggle": "one-way counter, spends budget",
    "enable": "one-way counter, spends budget",
    "disable": "one-way counter, spends budget",
}


def check(cmd: str) -> None:
    low = cmd.lower()
    for needle, why in REFUSED.items():
        if needle in low:
            raise SystemExit(f"refusing {cmd!r}: contains {needle!r} ({why})")


def wait_for_port(port: str, timeout: float) -> bool:
    print(f"[*] waiting up to {timeout:.0f}s for {port}")
    deadline = time.time() + timeout
    while time.time() < deadline:
        p = pathlib.Path(port)
        if p.exists():
            try:
                with open(port, "rb"):
                    pass
                print("[+] port is present and readable")
                time.sleep(1.5)   # let the CDC settle before the first write
                return True
            except PermissionError:
                print(f"[!] {port} exists but is not readable.")
                print("    the device node is recreated on every boot, so the chmod is gone:")
                print(f"      sudo chmod o+rw {port}")
                return False
            except OSError:
                pass
        time.sleep(0.5)
    print(f"[!] {port} never appeared. is bootwait still enabled, and did it cold boot?")
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--wait", type=float, default=180.0)
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--settle", type=float, default=2.5)
    args = ap.parse_args()

    sequence = args.only or SAFE_SEQUENCE
    for cmd in sequence:
        check(cmd)

    if not wait_for_port(args.port, args.wait):
        return 1

    CAPTURE.mkdir(parents=True, exist_ok=True)
    log = CAPTURE / f"{datetime.datetime.now():%Y%m%d-%H%M%S}-boot1.log"

    try:
        ser = serial.Serial(args.port, BAUD, timeout=0.3)
    except serial.SerialException as exc:
        print(f"error: cannot open {args.port}: {exc}", file=sys.stderr)
        return 1

    transcript = bytearray()
    with ser:
        time.sleep(0.4)
        ser.reset_input_buffer()
        ser.write(b"\r\n")
        ser.flush()
        time.sleep(1.0)
        banner = ser.read(200_000)
        transcript += banner
        text = banner.decode("utf-8", errors="replace")
        print(f"--- banner ---\n{text.strip()[:600]}\n")
        if "[console]" in text:
            print("[!] this is the XOUS console, not boot1. the badge booted through.")
            print("    bootwait may not have taken, or this is a warm boot.")

        for cmd in sequence:
            ser.write(cmd.encode() + b"\r\n")
            ser.flush()
            time.sleep(args.settle)
            out = ser.read(400_000)
            transcript += f"\n>>> {cmd}\n".encode() + out
            print(f"===== {cmd} =====")
            print(out.decode("utf-8", errors="replace").strip())
            print()

    log.write_bytes(transcript)
    print(f"[log: {log}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
