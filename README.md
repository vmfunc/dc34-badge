# dc34 badge

def con 34, august 6-9 2026, las vegas convention center west hall.
notes, images, tooling and solves for the badge and its embedded CTF challenge.

everything here is written for one reader: me, at 04:00 on day three, having slept
four hours since tuesday. so it is blunt, it is timestamped, and it assumes past-me
was an unreliable narrator who wrote things down anyway.

> **where this is up to, end of day one.** flag 1 (RRAM data slot 260) is an IRIS
> microscopy challenge, and it was given up on purpose: no microscope, so the badge was
> flashed with our own build and the slot is erased. flag 2 is live and needs no
> microscope, it is the population-wide key encrypting the QR-traded light patterns.
> one real silicon finding along the way, an ACL read-index aliasing in `rrc.sv`.
> [jump to the state of the challenge](#the-state-of-the-challenge).

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

defcon.org: *"a hardware CTF challenge is embedded in the badge firmware."*

**the firmware is public, and it was public the whole time.** it lives under the
[`bunnie`](https://github.com/bunnie) github org, linked from
[defcon.org/34b](https://defcon.org/34b/): `dc34-console` (the REPL, power and LED
drivers), `dc34-vault` (the app), `dc34-api`, and the official `dc34-image` /
`dc34-bio` host tools. signed release zips are on ci.betrusted.io. all six are vendored
in [`vendor/`](vendor/) with provenance and licence status stated per repo.

this repo spent most of a day reverse engineering two console protocols that the vendor
already ships tools for, because the search stopped at `betrusted-io` and `baochip`. so:
**when a vendor ships an open badge, find the vendor's own link page before reversing
anything.**

full detail, and the parts that are still unconfirmed, in [notes/hardware.md](notes/hardware.md).

---

## rules of engagement

self-imposed, not negotiable. every one exists because someone lost a badge or a day.

1. ~~**do not flash this badge, and never enter developer mode.**~~ **retired on
   2026-08-06, deliberately.** it stood for the whole first day and it was right: the
   flag is RRAM data slot 260, written once at final test, and it is a member of
   `KEY_SLOTS`, the set of keys **erased on entry to developer mode**. developer mode is
   what running unsigned code requires, so flashing does not *risk* the flag, it
   destroys it, with nothing to restore it from. chapter and verse in
   [notes/the-flag.md](notes/the-flag.md).

   it was retired because the rule had done its job and the answer it protected was one
   we could not use: every software route to slot 260 was measured and closed (see
   below), leaving IRIS microscopy, and there was no microscope. so the badge was
   flashed on purpose with our own build, and `THE_FLAG_1` is gone from it. the reasoning
   is logged at `[thu 20:2x]` in [notes/00-log.md](notes/00-log.md), and the rule stays
   written here rather than deleted, because anyone repeating this with a badge they
   still want the flag on needs to read it first.

   the UF2 bootloader is a write path with no readback either way, and
   `tools/dump-firmware.sh baochip` still refuses on purpose. `tools/flash.sh` is the
   deliberate path and it demands a typed confirmation.
2. **read the source before the disassembly, and find *all* of it first.** the RTL is
   public, xous is public, and so is the badge firmware. on an open chip, reversing
   something you could have read is self-inflicted. this rule was in place from day one
   and still got broken, because the search stopped one github org too early.
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
  the-flag.md   flag 1: the address, the landmine, and every closed door, measured.
  acl-aliasing.md  the one real silicon bug: the ACL read index collapses to slot >> 1.
  hardware.md   the baochip: what's confirmed, what isn't, and the bootloader trap.
  firmware.md   where the images come from, how they're laid out, what runs when.
  rf.md         bands, modulation, frame format, capture workflow.

vendor/         the six official `bunnie` dc34 repos, vendored. provenance + licence
                status stated per repo. never edited in place: the build wants
                `xous-core` as a sibling, not this copy.

firmware/
  MANIFEST.md   the ledger. every blob, hashed, dated, provenance stated.
  dumps/        vendor-signed release images. downloads, not dumps, and labelled so.
  built/        our own build + README with the recipe and every deviation from stock.
  extracted/    binwalk output. gitignored, regenerable from the dump.

re/
  scripts/      loaders, parsers, BIO programs (.S), ghidra headless scripts.
  ghidra/       project state. gitignored, merge-hostile, regenerable.
  strings/      raw strings/entropy dumps. interesting ones get promoted to notes/.

art/            what goes on the badge: the ud2 wordmark, the generated card source.
captures/       logic/, rf/, uart/. gitignored (big), hashed in a sibling manifest.
hw/             observed state: usb descriptors, the boot1 audit, the IFR dump.
                photographs of the board go here too, both sides, before any rework.
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
./tools/console.py "help" "ver"               # talk to the console, refuses fatal verbs
./tools/bio_upload.py --asm re/scripts/x.S    # assemble + upload a BIO program
./tools/peek.py 0x603E2080 --words 8          # read memory through a loaded BIO peek
./tools/sweep.py --range 0x603E0000 0x603F0000  # map which pages BIO may read
./tools/oled.py --ascii art/ud2.txt           # put a picture on the 128x128 panel
./tools/leds.py --palette rose-pine           # recolour the strip through the running
                                              #   lightgene: no upload, no flashing
./tools/ctap.py info                          # talk CTAPHID to the FIDO interface
./tools/image_probe.py --scan                 # bounds-check the image verb
./tools/boot1.py                              # drive the bootloader REPL, read-only
./tools/uf2.py carve xous.uf2 -o xous.bin     # flatten a UF2 for ghidra
./tools/serial-log.sh /dev/ttyACM0            # raw timestamped console capture
./tools/make_badge_art.py --pfp me.png \
  --out .../src/bitmaps/dc_logo.rs            # regenerate the vault's idle bitmap
./tools/flash.sh firmware/built               # write UF2s to boot1. IRREVERSIBLE,
                                              #   demands a typed confirmation
```

three things that will bite anyone repeating this:

- the console is **1000000 baud**, not 115200. wrong baud is indistinguishable from
  "this badge has no console".
- **writes must be paced inside the line, not just between lines.** console input runs
  through the keyboard service, whose buffer overflows on a fast full-length line
  (`Input overflow to N, dropping keys!`) and then takes the whole console silent. every
  tool here dribbles 4 bytes per 10 ms.
- **`bio tx` is not a host-to-core path.** it feeds the queue the core pushes *to*, so a
  value you send comes straight back on `bio rx` without any core seeing it. bake
  anything a program needs into the program. and a value pushed once is eaten by the
  badge's own lightgenes loop, so only continuous pushing survives to be read.

`art/ud2.txt` is the ud2 wordmark from ud2.rip, rendered to the panel by `oled.py`.

---

## building and flashing custom firmware

the badge's own firmware is public and vendored in `vendor/`. building it needs
`xous-core` as a **sibling** directory (its `[patch]` section redirects every xous
dependency to `../xous-core/...`), on the **`dev`** branch, not the rev its `Cargo.toml`
pins: `dc34-console` needs the `keystore` feature `owc-inc`, which exists only on `dev`.

the recipe below is the vendor's own, from `vendor/dc34-vault/README.md`, not one we
derived. run it from inside `xous-core`, with `dc34-console` and `dc34-vault` as
siblings:

```
git clone https://github.com/betrusted-io/xous-core && cd xous-core && git checkout dev
git tag v0.10.1                        # see below: the signer needs a describable tag
cargo xtask install-toolkit            # fetches a prebuilt riscv32imac-unknown-xous std
cargo xtask baosec-lite \
  ../dc34-console/target/riscv32imac-unknown-xous-elf/release/dc34-console~flash \
  ../dc34-vault/target/riscv32imac-unknown-xous-elf/release/dc34-vault \
  --no-timestamp --feature usb --kernel-feature debug-proc --no-verify
```

`baosec-lite` is the badge (it matches the `Baosec-lite` USB identity). extra app crates
are passed as cratespecs: a bare name is a workspace crate, `name^ver` is crates.io,
`name#url` is prebuilt, **anything containing `/` is a prebuilt ELF on disk**, and
`name~swap|flash|ram` pins the region. so an out-of-tree app goes in as a built binary
without joining the xous workspace. note the console goes in `~flash` and the vault takes
the default region.

**the git tag is not optional.** `xous-create-image` stamps a version from `git describe`,
so a shallow or tagless checkout dies in the swap signer with *"Can't sign swap image:
SemVer::from_git: no major version"*, a message that discards its own cause. the badge's
own `audit` reports `v0.10.1-0-gbcfdca404`, so the tag shape is real.

**the console's test commands sit behind five separate feature gates, not one**, and the
LED colour command is behind the second of them:

| feature | unlocks |
| --- | --- |
| `misc-test` | **`hue`**, `autogamy`, `qrshow`, `qrget`, `cam`, `accel`, `adc`, `shipmode`, `reset`, `wdt`, `wup` |
| `qa-test` | `rate`, `transmute`, `bt`, `mate` |

so `--features qa-test --features misc-test`. `owc-test`, `hazardous-test` and
`wfi-stress-test` stay off on purpose: the first spends finite one-way counters, the last
can hang the badge.

**sizes are the reproducibility proof.** ours came out with `loader.uf2` and `swap.uf2`
byte-identical in size to the official release and `xous.uf2` larger by exactly the code
added. that is how you know you built the vendor's image and not something adjacent.
the exact numbers, and every deviation from stock, are in
[firmware/built/README.md](firmware/built/README.md).

then:

```
# hold PROG while plugging in -> 1d50:6196, BAOCHIP volume appears
./tools/flash.sh <dir with the .uf2 files>
# press PROG again to run it
```

> [!wired] flashing anything not vendor-signed destroys the flag, and it already has
> boot1 runs `erase_secrets()` *before* unsigned code executes, wiping `KEY_SLOTS`,
> and `THE_FLAG_1` (RRAM data slot 260) is in that set. this badge was flashed on
> 2026-08-06, so its slot 260 is erased. the stock image is restorable with
> `./tools/flash.sh firmware/dumps/dc34-badge-latest`; the FT-programmed flag value is
> not, and never will be.

---

## the state of the challenge

**flag 1 is a physical challenge, and it is off the table on this badge.** every
software route to slot 260 was measured on hardware, not inferred, and every one is
closed by a *different* deliberate mechanism: the BIO BDMA whitelist is entirely empty
(and a filtered read is redirected to a gutter address, not rejected, so it *looks*
like it succeeded), boot1's `peek` refuses the address range **and** is compiled out of
the shipped build, `image` is a bounded 2048-byte framebuffer with no OOB, CTAPHID is
an INIT-only stub whose advertised capabilities are a lie, the keystore exposes no
ACL-write opcode, and JTAG is fused off. what is left is IRIS: infrared imaging of the
RRAM array, which the badge is *packaged* for, with a ~$180 kit and >97% readout
accuracy (on-die ECC repairs the rest). the full argument is in
[docs/writeup.md](docs/writeup.md) and [notes/the-flag.md](notes/the-flag.md).

**flag 2 is the live one, and it needs no microscope.** from
`vendor/dc34-vault/README.md`, the badge's actual game: light patterns are bred by a
genetics simulation and traded between badges **by scanning QR codes**, and those
payloads are

> "encrypted using a common, shared key across the entire population - if you can
> extract that key, then you can effectively be a seeder for arbitrary light patterns"

every badge starts with a limited colour range and the only sanctioned way to widen it
is to meet someone who has more. so the intended software challenge is key extraction,
we hold the full source of both ends of the exchange, and this badge is now running a
build with `qrshow` / `qrget` / `cam` enabled. that is where to start.

**one real silicon finding fell out along the way.** `rrc.sv` derives the ACL index
differently on its read and write paths (`haddr[16:6]` versus
`{haddr[13:5], acram_idx}`), so with 32-byte data slots the read index collapses to
`slot >> 1` and **two adjacent slots share one access-control entry**. slot 260
(`THE_FLAG_1`) pairs with 261 (`COLLATERAL[0]`, the region designed to be written by
third parties), and pair 132 is worse: slot 264 (`COLLATERAL[3]`, `Fw0`) shares its
entry with slot 265 (`BOOT1_PK_RECEIPT_SLOT0`, `Open`), so if the permissive side wins
an `Fw0` key is readable from an open context. it did not turn into an exploit here,
but it is arithmetic,
checkable without hardware, and worth disclosing to baochip regardless of the CTF.
[notes/acl-aliasing.md](notes/acl-aliasing.md).

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
