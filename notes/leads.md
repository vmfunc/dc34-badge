# leads

the hypothesis queue. one line each, kept ranked. a lead is a *falsifiable guess plus
the cheapest experiment that kills it*, not a vibe.

promote to a `solves/<name>/` dir the moment a lead survives its first test.
strike it through when it dies, do not delete .. a dead lead stops you re-walking it.

## hot

- [ ] **the light-pattern key is recoverable from the QR exchange, and it is the same key
      on every badge at the con** (`vendor/dc34-vault/README.md` says so outright) ..
      kill test: read the QR encode/decode path in `dc34-vault` and find where the key is
      sourced. if it is a compile-time constant or derived from public per-badge data,
      it is already ours from the vendored source. if it comes out of a key slot, that is
      a different and much harder problem.
- [ ] **our own build can be made to dump the key it uses**, since we are already running
      a custom image with `qrshow`/`qrget`/`cam` enabled .. kill test: add a print to the
      key-load site, rebuild, flash, read it off the console. costs nothing that has not
      already been spent, because the flag is already gone from this badge.
- [ ] **the ACL read-index aliasing lets an `Open` context read an `Fw0` slot** (pair 132:
      slot 264 `COLLATERAL[3]` shares its entry with slot 265 `BOOT1_PK_RECEIPT_SLOT0`)
      .. kill test: read slot 264 from an unprivileged context and see whether it answers.
      see [acl-aliasing.md](acl-aliasing.md).

## warm

- [ ] the `lightgenes` BIO runtime uses **FIFO1 with event-mask polling**, not the
      blocking FIFO0 pops the first programs here were written around (per the
      `test-ws2812` reference) .. kill test: rewrite one program against FIFO1 + event
      mask and see whether the core actually observes a host-side value.
- [ ] there is a second flag *literal* somewhere in the shipped images that a plain search
      of the source tree misses .. kill test: strings/entropy sweep across the vendored
      release `.uf2`s, now that we have them, rather than across the source.

## dead

- ~~BIO BDMA can be pointed at the flag page~~ .. killed 2026-08-06, the whitelist is
  **entirely empty**; the flag page, RRAM base, SRAM base and the crypto segment are all
  filtered, and the badge drives its LEDs over GPIO rather than DMA so nothing ever
  configures a window to inherit. a filtered read is redirected to a gutter address, not
  rejected, which made the hang itself the oracle.
- ~~boot1's `peek` reads the flag~~ .. killed 2026-08-06, closed twice: it refuses
  `0x603D_A000`..`0x6040_0000` by address, *and* it is behind `#[cfg(feature =
  "unsafe-debug")]` and absent from the shipped build.
- ~~boot1's `uf2` command is an arbitrary write~~ .. killed 2026-08-06, bounded below
  `0x603D_A000`, so it cannot address the flag, and using it unsigned triggers the erase.
- ~~the `image` verb's u16 chunk index is an OOB write offset~~ .. killed 2026-08-06,
  it is a bounded 2048-byte framebuffer (32 chunks x 64 bytes = 128x128 mono), sequence
  enforced, every out-of-range index rejected.
- ~~CTAPHID exposes something~~ .. killed 2026-08-06, INIT-only stub: it allocates
  channels and advertises caps `0x05`, then PING, WINK, MSG and every CBOR command return
  nothing at all. the advertised capabilities are a lie.
- ~~JTAG / hardware debug is reachable~~ .. killed 2026-08-06, fused off, confirmed
  against `secboot.rs`'s hardcoded IFR reference at `0x6040_0180`.
- ~~sign our own image with a key that does not trigger the erase~~ .. killed 2026-08-06,
  only `bao1`, `bao2` and `beta` would qualify and none of those private keys are public;
  the shipped `devkey/` runs only after `erase_secrets()`.
- ~~a top-level console verb exists that resets the badge in software~~ .. killed
  2026-08-06, brute-forced 47 plausible verbs, zero hits beyond `echo`, `ver`, `test`,
  `image`, `bio`. reaching boot1 needs a physical 6 s power hold.
- ~~voltage / clock glitching~~ .. not attempted on purpose: the part has explicit glitch
  sensors and a secure mesh, and `ifr` carries deliberate `black_box` asserts to stop it
  being a glitchable dump primitive. bunnie anticipated the reflex move.
- ~~flag 1 is reachable at all on **this** badge~~ .. killed 2026-08-06 by choice, not by
  the challenge: custom firmware was flashed, boot1 ran `erase_secrets()`, slot 260 is
  erased. IRIS remains the correct answer for an unflashed badge.
