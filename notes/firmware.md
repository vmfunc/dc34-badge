# firmware

blob provenance lives in [firmware/MANIFEST.md](../firmware/MANIFEST.md). this file is
the *understanding*: what the images are, where they came from, and what runs when.

## how it was obtained: it was never dumped, and it never could be

the refusals matter here more than the successes, because they describe the protection.

- **readback: none.** the UF2 bootloader is a write path with no read verb. boot1's
  `peek` refuses the flag address range *and* is compiled out of the shipped build.
  JTAG is fused off. `tools/dump-firmware.sh baochip` refuses on purpose and explains
  why rather than pretending.
- **so every image here is a download or a build, not a dump.** the shipping firmware
  came from the vendor's own signed release,
  `https://ci.betrusted.io/releases/latest/baochip/dc34-badge/latest.zip` (mirrored at
  `defcon.org/34b/latest.zip`), hashed into the manifest and labelled a download.
- **and the sources are public**, under the [`bunnie`](https://github.com/bunnie) github
  org, linked from defcon.org/34b: `dc34-console`, `dc34-vault`, `dc34-api`, plus the
  official `dc34-image` / `dc34-bio` host tools. all vendored in `../vendor/`. this was
  found late, after a day spent reversing console protocols the vendor ships tools for.

## the three image sets in this repo

| where | what | signed with |
| --- | --- | --- |
| `firmware/dumps/dc34-badge-latest/` | the vendor's shipping release, unmodified | a production key the badge accepts, so re-flashing it is safe |
| `firmware/built/` | our build: stock plus a `qa-test`+`misc-test` console and a custom idle screen | `devkey/dev.key`, so boot1 runs `erase_secrets()` before it executes |
| `vendor/` | the sources both of the above come from | n/a |

`firmware/built/README.md` carries the exact recipe, the size comparison against the
official release, and every deviation from stock.

## image layout

three UF2s, and the split is the xous process model rather than a flat image:

| file | bytes (stock) | what |
| --- | --- | --- |
| `loader.uf2` | 353,280 | the loader |
| `xous.uf2` | 6,358,528 | kernel + the flash-resident services |
| `swap.uf2` | 2,343,424 | the swap region |

`cargo xtask baosec-lite` lays out the process table the badge's own `audit` reports:
kernel, swapper in PID2, keystore in PID3, then ticktimer, log, names, usb-bao1x,
hal-service, modals, pddb, bao-video. extra app crates are placed by cratespec, with
`~flash` / `~swap` / `~ram` pinning the region.

**build size is a reproducibility proof.** our `loader.uf2` and `swap.uf2` came out
byte-identical in size to the release and `xous.uf2` larger by exactly the added code.
if those numbers drift, you are not building the vendor's image.

## load address / architecture

the single most common way to waste two hours is disassembling at the wrong base.

- arch: **rv32imac** (VexRiscv). the BIO coprocessor cores are PicoRV32, also rv32.
- base: read it out of the UF2 header rather than guessing, `tools/uf2.py info`.
  `tools/uf2.py carve` flattens a UF2 at the right base for ghidra.
- endianness: little **on the bus**, but note the trap below.

> [!wired] the endianness trap that cost an evening
> the `image` verb assembles its framebuffer words with `u32::from_be_bytes`
> (`dc34-console/src/cmds/image.rs`), so bytes are **big-endian within each 32-bit
> word** even though the machine is little-endian. pack little-endian and the panel
> renders noise that looks exactly like a protocol bug.

ghidra handles RISC-V natively, pick the `RISCV:LE:32:RV32IC` variant and check that
compressed instructions decode, `c.*` mnemonics everywhere is the tell that the `c`
extension is being honoured.

xous is rust, so expect the rust symbol mangling (`_ZN...17h<hash>E`) and fat panic
strings carrying source paths. those paths are free structure, they tell you the crate
layout before you read a single instruction. with `vendor/` in hand, though, prefer the
source: on an open badge, reversing something you could have read is self-inflicted.

## interesting strings / symbols

`re/strings/` holds the raw output. the *interesting* ones get pulled up here with a note
on why they are interesting.

- `hw/ifr.bin`, the full 1 KiB IFR region, contains exactly one piece of ASCII: the lot
  code `94912066M06T`. no flag literal, which is part of why flag 2 is not a hidden
  string.

## crypto

name the algorithm before you name the vulnerability.

- **image signing:** the badge accepts `bao1`, `bao2` and `beta` keys; `audit` reports
  boot1 and the next stage signed with **beta**, not production. xous-core ships a public
  `devkey/`, but a dev-key-signed image runs only *after* `erase_secrets()` wipes
  `KEY_SLOTS`. post-quantum signing is in the mix (`--no-pq` exists as a flag and made no
  difference to the signing failure we chased, which was a missing git tag).
- **the one that matters now:** the light patterns traded between badges over QR are
  encrypted with a key **shared across the entire population**
  (`vendor/dc34-vault/README.md`). extracting it makes you a seeder for arbitrary
  patterns, and that is almost certainly flag 2. see [the-flag.md](the-flag.md) and
  [leads.md](leads.md).
- the SoC has AES instructions used with chaffing, a TRNG, glitch sensors and a secure
  mesh. see [hardware.md](hardware.md).
