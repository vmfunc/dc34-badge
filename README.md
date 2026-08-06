# dc34 badge

def con 34, august 6-9 2026, las vegas convention center west hall.
notes, dumps, tooling and solves for the badge and its embedded CTF challenge.

everything here is written for one reader: me, at 04:00 on day three, having slept
four hours since tuesday. so it is blunt, it is timestamped, and it assumes past-me
was an unreliable narrator who wrote things down anyway.

---

## the badge

it is a **baochip-1x**: bunnie huang's "mostly open" 22nm SoC, and the first def con
badge whose RTL you can actually read. that inverts the usual first day. instead of
guessing the peripheral map from a disassembly, you read the verilog.

| | |
| --- | --- |
| main core | VexRiscv **rv32imac** with MMU, 350 MHz |
| io coprocessor | quad PicoRV32 "BIO" @ 700 MHz |
| memory | 2 MiB ECC SRAM, **4 MiB RRAM** (nonvolatile, 32-byte pages) |
| usb | USB 2.0 HS |
| os | **Xous**, pure-rust microkernel |
| security | TRNG, crypto accelerators, secure mesh, **glitch sensors**, hardware key slots, one-way counters |
| add-ons | SAO v2.0 |

defcon.org: *"a hardware CTF challenge is embedded in the badge firmware."* the stock
firmware is not published until after the con.

full detail, and the parts that are still unconfirmed, in [notes/hardware.md](notes/hardware.md).

---

## rules of engagement

self-imposed, not negotiable. every one exists because someone lost a badge or a day.

1. **do not flash this badge, and never enter developer mode.** the flag is RRAM data
   slot 260, written once at final test, and it is a member of `KEY_SLOTS`: the set of
   keys **erased on entry to developer mode**. developer mode is what running unsigned
   code requires. so flashing destroys this badge's flag permanently, with nothing to
   restore it from. our own code *and* the challenge means two badges, not one. chapter
   and verse in [notes/the-flag.md](notes/the-flag.md). the UF2 bootloader is a write
   path with no readback either way, and `tools/dump-firmware.sh baochip` refuses on
   purpose.
2. **read the source before the disassembly.** the RTL is public and xous is public.
   on an open chip, reversing something you could have read is self-inflicted.
3. **passive before active.** console and usb descriptors before you write anything,
   receive before you transmit. this is a con floor, not a lab.
4. **hash everything you do capture, at capture time.** a blob with no hash and no date
   is a rumour. `firmware/MANIFEST.md` is the ledger.
5. **failures go in the log.** a dead lead you wrote down is a lead you only walk once.
6. **no flags in git history before they're public.** `git log -p` is forever.
7. **offline first.** the DC network is hostile by design. the toolchain is pinned in
   `flake.lock` and pre-warmed before we need it.

> the reflex move on an MCU CTF is voltage/clock glitching. this part has explicit
> glitch sensors and a secure mesh. read the sensor RTL before burning a day on it.

---

## layout

```
notes/          the thinking. hand-written, append-only where it says so.
  00-log.md     running log, newest at bottom, timestamped. the spine.
  leads.md      hypothesis queue, ranked. dead leads kept, struck through.
  hardware.md   the baochip: what's confirmed, what isn't, and the bootloader trap.
  firmware.md   image layout, load address, strings, crypto. the understanding.
  rf.md         bands, modulation, frame format, capture workflow.

firmware/
  MANIFEST.md   the ledger. every blob, hashed, dated, provenance stated.
  dumps/        raw images. committed when small, immutable once written.
  extracted/    binwalk output. gitignored, regenerable from the dump.

re/
  scripts/      loaders, parsers, openocd.cfg, ghidra headless scripts.
  ghidra/       project state. gitignored, merge-hostile, regenerable.
  strings/      raw strings/entropy dumps. interesting ones get promoted to notes/.

captures/       logic/, rf/, uart/. gitignored (big), hashed in a sibling manifest.
hw/             photographs of the board. both sides, high res, before any rework.
solves/         one dir per challenge. _template/ is the shape.
tools/          host-side scripts. all of them safe to run half asleep.
docs/           the writeup, drafted as we go rather than from memory on sunday.
```

### why captures are gitignored but dumps are not

a firmware dump is *evidence* and it is small. it belongs in history so a later diff
can prove what changed. a logic or SDR capture is *observation*, hundreds of MB, and
worth exactly as much as the notes derived from it. so the bytes stay local and the
conclusions get committed. no git-lfs on purpose: lfs needs a network round trip and
the premise is that the network will not be there.

---

## the shell

nix flake, pinned, evaluates on the framework (linux) and the mac.

```
nix develop
```

carries: rustup + `pkgsCross.riscv32-embedded` gcc/binutils/gdb for rv32 ·
ghidra, radare2, binwalk, yara · openocd, probe-rs, picotool, esptool, dfu-util for
the arm/xtensa badges and SAOs on the floor · picocom, sigrok-cli, flashrom ·
rtl-sdr, hackrf · python with pwntools, capstone, keystone, unicorn, pycryptodome.

xous builds against `riscv32imac-unknown-xous-elf`, a custom target that is not in
upstream rust, which is why the toolchain comes from `rustup` rather than nixpkgs'
pinned rustc.

the rf gui tools (pulseview, inspectrum, urh) are linux-only in nixpkgs and gated
accordingly. visual RF work happens on the framework, the mac does static RE.

**pre-warm before you need it**, while there is still real bandwidth:

```
nix develop --profile ./.dc34-profile -c true
```

that materialises the whole closure and roots it against gc, so the shell opens with
no network at all.

---

## tools

```
./tools/serial-log.sh /dev/ttyACM0            # console @ 1000000 8n1, timestamped
./tools/uf2.py info apps.uf2                  # base address + flags, no guessing
./tools/uf2.py carve apps.uf2 -o apps.bin     # flatten for ghidra at the right base
./tools/new-solve.sh some-challenge           # scaffold a challenge dir
./tools/dump-firmware.sh 01-baseline rp2040   # for other badges. baochip mode refuses
```

the console is **1000000 baud**, not 115200. wrong baud looks exactly like "this badge
has no console", which is how you walk past the most informative surface on the board.

---

## links

- def con 34: https://defcon.org/html/defcon-34/dc-34-index.html
- bunnie on the baochip-1x: https://www.bunniestudios.com/blog/2026/baochip-1x-a-mostly-open-22nm-soc-for-high-assurance-applications/
- baochip RTL + hardware: https://github.com/baochip
- xous, the OS on it: https://github.com/betrusted-io/xous-core
- baochip build/flash workflow: https://github.com/betrusted-io/xous-core/blob/main/README-baochip.md
- community teardown report: https://github.com/doublegate/DEFCON34-Baochip-1x-Report
- def con CTF quals (the separate contest): https://bbbirds.org/
- vault project note: `~/vault/projects/dc34-badge-ctf.md`

---

*not affiliated with the badge designers. my own work on my own badge.*
