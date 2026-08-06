#!/usr/bin/env python3
"""solve for <challenge>.

runs standalone under the repo devshell:  nix develop -c python solve.py
keep it reproducible: no hardcoded /dev/ttyUSB0 without a fallback, no manual steps
buried in comments. if a human has to press a button, print() and wait.
"""

import argparse
import sys

# the badge speaks over this. adjust per challenge, do not scatter it through the file.
DEFAULT_PORT = "/dev/ttyACM0"
BAUD = 115200


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=DEFAULT_PORT)
    args = ap.parse_args()

    raise NotImplementedError(f"solve not written yet (port={args.port})")


if __name__ == "__main__":
    sys.exit(main())
