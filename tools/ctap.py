#!/usr/bin/env python3
"""talk CTAPHID to the badge's FIDO2 interface.

interface 0 is CTAPHID (report descriptor opens 06 d0 f1, the FIDO usage page), 64
byte interrupt in/out, exposed as /dev/hidraw0. logind's uaccess already grants the
console user access, so this needs no root.

  ./tools/ctap.py info
  ./tools/ctap.py vendor        # probe the vendor command range 0x40..0x7f

CTAPHID framing:
  init packet: CID(4) | CMD|0x80 (1) | BCNTH(1) | BCNTL(1) | payload(57)
  cont packet: CID(4) | SEQ(1)                            | payload(59)

authenticatorReset (CBOR 0x07) is never sent by this tool. it wipes credentials and
on some tokens is irreversible; there is no reason to touch it while hunting a flag.
"""

import argparse
import os
import struct
import sys
import time

DEVICE = "/dev/hidraw0"
REPORT = 64
BROADCAST = 0xFFFFFFFF

CMD_PING = 0x01
CMD_MSG = 0x03
CMD_INIT = 0x06
CMD_CBOR = 0x10
CMD_ERROR = 0x3F

CTAP_ERRORS = {
    0x01: "INVALID_COMMAND",
    0x02: "INVALID_PARAMETER",
    0x03: "INVALID_LENGTH",
    0x04: "INVALID_SEQ",
    0x05: "TIMEOUT",
    0x06: "CHANNEL_BUSY",
    0x0A: "LOCK_REQUIRED",
    0x0B: "INVALID_CHANNEL",
    0x7F: "OTHER",
}


class Ctap:
    def __init__(self, path: str = DEVICE):
        try:
            # non-blocking is required: the read loop below polls with a deadline,
            # and a blocking read on a device that never answers hangs forever.
            self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        except OSError as exc:
            raise SystemExit(f"error: cannot open {path}: {exc}")
        self.cid = BROADCAST

    def close(self) -> None:
        os.close(self.fd)

    def _write(self, data: bytes) -> None:
        os.write(self.fd, data.ljust(REPORT, b"\x00"))

    def _read(self, timeout: float = 2.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                return os.read(self.fd, REPORT)
            except BlockingIOError:
                time.sleep(0.01)
            except OSError:
                return None
        return None

    def send(self, cmd: int, payload: bytes = b"", timeout: float = 2.0):
        """-> (cmd, payload) or None. handles continuation packets both ways."""
        head = struct.pack(">IBH", self.cid, cmd | 0x80, len(payload))
        self._write(head + payload[:REPORT - 7])

        rest = payload[REPORT - 7:]
        seq = 0
        while rest:
            self._write(struct.pack(">IB", self.cid, seq) + rest[:REPORT - 5])
            rest = rest[REPORT - 5:]
            seq += 1

        pkt = self._read(timeout)
        if not pkt:
            return None
        _cid, rcmd, blen = struct.unpack(">IBH", pkt[:7])
        body = bytearray(pkt[7:])
        while len(body) < blen:
            more = self._read(timeout)
            if not more:
                break
            body += more[5:]
        return rcmd & 0x7F, bytes(body[:blen])

    def init(self):
        nonce = os.urandom(8)
        self.cid = BROADCAST
        got = self.send(CMD_INIT, nonce)
        if not got or got[0] != CMD_INIT:
            raise SystemExit(f"error: INIT failed: {got}")
        body = got[1]
        if body[:8] != nonce:
            raise SystemExit("error: INIT nonce mismatch, another client is talking")
        self.cid = struct.unpack(">I", body[8:12])[0]
        return {
            "channel": self.cid,
            "protocol": body[12],
            "device": f"{body[13]}.{body[14]}.{body[15]}",
            "caps": body[16],
        }


def decode(cmd: int, body: bytes) -> str:
    if cmd == CMD_ERROR and body:
        return f"CTAPHID_ERROR {body[0]:#04x} {CTAP_ERRORS.get(body[0], '?')}"
    return f"cmd={cmd:#04x} len={len(body)} {body[:48].hex()}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["info", "vendor", "ping"])
    ap.add_argument("--device", default=DEVICE)
    args = ap.parse_args()

    dev = Ctap(args.device)
    try:
        meta = dev.init()
        print(f"channel  0x{meta['channel']:08x}")
        print(f"protocol {meta['protocol']}   device {meta['device']}   caps 0x{meta['caps']:02x}")
        caps = meta["caps"]
        print(f"  WINK={bool(caps & 0x01)} CBOR={bool(caps & 0x04)} NMSG={bool(caps & 0x08)}")

        if args.action == "ping":
            payload = bytes(range(32))
            got = dev.send(CMD_PING, payload)
            print("ping ->", "echo ok" if got and got[1] == payload else f"unexpected {got}")

        elif args.action == "info":
            got = dev.send(CMD_CBOR, bytes([0x04]))   # authenticatorGetInfo
            if not got:
                print("getInfo: no response")
            else:
                cmd, body = got
                print(f"\ngetInfo -> {decode(cmd, body)}")
                if cmd == CMD_CBOR and body:
                    print(f"  status 0x{body[0]:02x}")
                    print(f"  cbor   {body[1:].hex()}")
                    printable = "".join(chr(b) if 32 <= b < 127 else "." for b in body[1:])
                    print(f"  ascii  {printable}")

        elif args.action == "vendor":
            print("\nprobing vendor command range 0x40..0x7f")
            hits = []
            for cmd in range(0x40, 0x80):
                got = dev.send(cmd, b"", timeout=1.0)
                if not got:
                    continue
                rcmd, body = got
                if rcmd == CMD_ERROR and body and body[0] == 0x01:
                    continue          # INVALID_COMMAND: not implemented
                hits.append((cmd, rcmd, body))
                print(f"  0x{cmd:02x} -> {decode(rcmd, body)}")
            print(f"\n{len(hits)} vendor command(s) answered something other than INVALID_COMMAND")
    finally:
        dev.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
