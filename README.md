# dc34 badge

my findings and custom stuff for the def con 34 badge.

it's a **baochip-1x**, bunnie's mostly-open 22nm soc. vexriscv rv32imac + mmu at 350mhz,
quad picorv32 "bio" coprocessor at 700mhz, 2mib ecc sram, 4mib rram, usb 2.0 hs, running
xous. enumerates as `1d50:6198` "baosec-lite".

first dc badge whose rtl you can actually read, which changes the job. reversing something
you could have read is self-inflicted here.

## the ctf

flag 1 is stated outright in `bao1x-api/src/offsets/baosec.rs:151`:

```rust
/// A test value placed by FT into the memory array. If you can read the original value,
/// you've captured a flag!
/// There is a second flag stored somewhere else. Can you find it?
pub const THE_FLAG_1: SlotIndex = SlotIndex::Data(260, PartitionAccess::Fw0, RwPerms::ReadWrite);
```

32 bytes at `0x603E_2080`, burned at final test, `Fw0` so only boot1 and the keystore touch
it. not derived from anything, so it can't be computed. only read.

and it's in `KEY_SLOTS`, the set boot1 wipes on entry to developer mode. `sigcheck.rs:735`
runs `erase_secrets()` *before* unsigned code executes, so the erase is a precondition of
running your own image, not a consequence. no window, no ordering trick. flashing the badge
isn't a risk to the flag, it's the destruction of it.

that's the whole design, and it's a good one.

## every software path, and what killed it

measured on hardware, not inferred.

| path | why it's dead |
| --- | --- |
| bio bdma read | whitelist entirely empty. a filtered read gets redirected to `gutter` (resets to 0), nothing answers there, the core hangs. the hang is the oracle |
| boot1 `peek` | refuses `0x603D_A000`..`0x6040_0000` by address, *and* it's behind `unsafe-debug` and not in the shipped build |
| boot1 `uf2` | write path, bounded below `0x603D_A000`, can't address the flag, and unsigned use triggers the erase anyway |
| `image` verb | bounded 2048-byte framebuffer, 32 chunks, sequence enforced. the u16 index is not an oob write |
| ctaphid | init-only stub. init allocates channels and advertises caps `0x05`, then ping/wink/msg/cbor all return nothing |
| jtag | fused off, checked against `secboot.rs`'s hardcoded ifr reference at `0x6040_0180` |
| sign our own image | only `bao1`/`bao2`/`beta` avoid the erase, none of those private keys are public |

bio code execution *does* work. `bio` is an undocumented console verb that turns out to be
`baochip/bio-loader`'s protocol. proved it by loading a program that pushes `0x0BADF00D`,
then one that pops-adds-one-pushes, and reading back `badf00e`. it just can't reach memory.

so flag 1 is physical, and bunnie says so himself in the comment right above it: the
nuisance keys exist "to annoy microscopists trying to read the secret key by directly
imaging the rram array", and he concedes any readout above 97% accuracy gets repaired by
ecc. he named the attack, the tool and the pass mark. it's an iris job.

i gave up flag 1 on this badge on purpose, no microscope on hand, and flashed my own
firmware instead. slot 260 is erased here. for an unflashed badge the answer is still iris.

## the bug worth reporting

`rrc.sv:392-395` derives the acram index differently on its two paths. writes use
`{haddr[13:5], acram_idx}`, granular to 32 bytes. reads use `haddr[16:6]`, granular to 64.
a data slot is 32 bytes, so the read path drops the bit separating a slot from its
neighbour and the acl read index collapses to `slot >> 1`.

| pair | slots | access |
| --- | --- | --- |
| 130 | `THE_FLAG_1` (260) / `COLLATERAL[0]` (261) | fw0 / fw0 |
| **132** | **`COLLATERAL[3]` (264) / `BOOT1_PK_RECEIPT_SLOT0` (265)** | **fw0 / open** |

pair 132 straddles a privilege boundary. if the permissive side wins, slot 264 is readable
from a context that should never see it. arithmetic, checkable, worth telling baochip
regardless of the ctf. details in [notes/acl-aliasing.md](notes/acl-aliasing.md).

also a plain overflow in `test hue`: `base + 32` on a `u8` wraps, so asking for deep magenta
silently hands you green. fixed in my build.

## flag 2

still open, and it's the interesting one. from `vendor/dc34-vault/README.md`: light patterns
are traded between badges by qr and encrypted with a key **shared across the entire
population**. extract it and you're a seeder for arbitrary patterns. no microscope needed.
ranked leads and kill tests in [notes/leads.md](notes/leads.md).

## my firmware

reproduces bunnie's build, `loader.uf2` and `swap.uf2` byte-identical in size to the
official release, `xous.uf2` bigger by exactly what i added. deviations:

- `dc34-console` with `--features qa-test --features misc-test`. there are five feature
  gates in `cmds/test.rs`, not one, and `hue` is behind the second. `misc-test` carries
  `hue`/`autogamy`/`qrshow`/`qrget`/`cam`/`accel`/`adc`, `qa-test` carries
  `rate`/`transmute`/`bt`/`mate`. left `owc-test` and `wfi-stress-test` off, the first
  spends finite one-way counters and the second can hang the badge
- idle screen is mine: pfp, `vmfunc`, `it/its`. dc logo gone. regenerate with
  `tools/make_badge_art.py`
- strip reads `ud2.rip`
- boots lavender and breathing, nothing to type
- `test hue <val> [width]`, width 0 for one flat colour

on the breathing: the bio renderer computes brightness as
`cos(cd_period * 2pi * i/(count-1) +/- indextime/tau(cd_rate) * 2pi)`. `cd_period = 0` puts
every led in phase so the strip rises and falls together. `cd_rate` maps 0..255 onto tau
60..700, high is slow. that's the whole effect, no new code.

the default uses `force()` instead of setting the gene, so the heritable gene survives and
qr trading still works. it holds through repaints until you run `test hue`, trade, or breed,
then hands over for good.

## layout

```
notes/          the thinking. 00-log is the spine, leads.md is the hypothesis queue
firmware/       dumps/ is the vendor's signed release, built/ is mine, MANIFEST.md hashes both
vendor/         the six official bunnie repos, pinned, with provenance
tools/          host side, all of it safe to run half asleep
re/             ghidra scripts, bio programs, strings
art/            the ud2 wordmark and the generated badge card
captures/       gitignored. big, and worth exactly as much as the notes taken off them
solves/         one dir per challenge
docs/           the writeup
```

images get committed, captures don't. a firmware image is small evidence worth having in
history so a later diff can prove what changed. a logic capture is hundreds of mb of
observation. no git-lfs, it wants a network round trip and the whole premise is the network
won't be there.

## toolchain

```
nix develop
```

pinned flake, evaluates on x86_64-linux and aarch64-darwin. rv32 cross toolchain, ghidra,
radare2, binwalk, openocd, probe-rs, picotool, esptool, picocom, sigrok, rtl-sdr, hackrf,
python with pwntools/capstone/keystone/unicorn. rf gui tools are linux-only in nixpkgs and
gated accordingly.

pre-warm before you lose network:

```
nix develop --profile ./.dc34-profile -c true
```

## tools

```
./tools/console.py "help" "ver"                   talk to the console, refuses the fatal verbs
./tools/bio_upload.py --asm re/scripts/x.S        assemble + upload a bio program
./tools/sweep.py --range 0x603E0000 0x603F0000    map what bio may read
./tools/oled.py --ascii art/ud2.txt               picture onto the panel
./tools/leds.py --palette rose-pine               colours through the running lightgene
./tools/ctap.py info                              ctaphid
./tools/boot1.py                                  drive the bootloader, read-only
./tools/flash.sh firmware/built                   flash. makes you type FLASH
./tools/make_badge_art.py --pfp x.jpg             regenerate the idle screen
```

three things that cost me real time:

**console is 1000000 baud**, not 115200. wrong baud is indistinguishable from no console.

**pace writes inside the line.** console input goes through the keyboard service and its
buffer overflows on a fast full-length line, then takes the whole console silent. but
byte-at-a-time is worse: each tiny write becomes its own usb packet and the firmware
mis-samples it, so `ver` echoes back as `vrr`. corrupted input that still parses wastes far
more time than input that's loudly dropped. 24-byte pieces.

**`bio tx` is not a host-to-core path.** it feeds the queue the core pushes *to*, so anything
you send comes straight back on `bio rx` without a core ever seeing it. bake what a program
needs into the program. and a value pushed once gets eaten by the badge's own lightgenes
loop, so only continuous pushing survives.

## building the firmware

needs `xous-core` as a **sibling** dir, on **`dev`**, not the rev `dc34-console` pins.
`dc34-console` wants `keystore/owc-inc` which only exists on dev. tag the checkout or the
signer dies with `SemVer::from_git: no major version`.

```
cargo xtask install-toolkit          # prebuilt riscv32imac-unknown-xous std, no build-std
cargo xtask baosec-lite \
  ../dc34-console/target/riscv32imac-unknown-xous-elf/release/dc34-console~flash \
  ../dc34-vault/target/riscv32imac-unknown-xous-elf/release/dc34-vault \
  --no-timestamp --feature usb --kernel-feature debug-proc --no-verify
```

cratespec syntax matters: bare name is a workspace crate, `name^ver` is crates.io,
`name#url` is prebuilt, anything with a `/` is a prebuilt elf on disk, and
`name~swap|flash|ram` pins the region. out-of-tree apps go in as built binaries without
joining the xous workspace.

flash: hold `PROG` while plugging in, `./tools/flash.sh <dir>`, press `PROG` again.
back to stock: `./tools/flash.sh firmware/dumps/dc34-badge-latest`.

## links

- badge: https://defcon.org/34b/
- bunnie on the soc: https://www.bunniestudios.com/blog/2026/baochip-1x-a-mostly-open-22nm-soc-for-high-assurance-applications/
- sources: https://github.com/bunnie (dc34-console, dc34-vault, dc34-api, dc34-image, dc34-bio)
- rtl: https://github.com/baochip/baochip-1x
- xous: https://github.com/betrusted-io/xous-core
- iris: https://bunnie.org/iris

---

not affiliated with the badge designers. `vendor/` is their code, vendored with provenance in
`vendor/README.md`. `dc34-console`, `dc34-vault` and `dc34-api` ship no licence file, so
that's public-but-unlicensed, worth an email to `dc34@baochip.com` before anyone builds on
this.
