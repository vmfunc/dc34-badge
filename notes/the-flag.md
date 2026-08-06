# the flag

found by reading the source, not the badge. `xous-core/libs/bao1x-api/src/offsets/baosec.rs:151`:

```rust
/// A test value placed by FT into the memory array. If you can read the original value, you've captured a
/// flag!
/// There is a second flag stored somewhere else. Can you find it?
///
/// <slot-map targets="baosec,dabao" registered="primary" in-key-slots="yes" in-data-slots="no"/>
pub const THE_FLAG_1: SlotIndex = SlotIndex::Data(260, PartitionAccess::Fw0, RwPerms::ReadWrite);
```

so the challenge is: **read RRAM data slot 260**, which carries `PartitionAccess::Fw0`,
meaning only the bootloader and the key manager may touch it. FT is final test, so the
value is programmed at manufacture and is not derived from anything on the device.

there is a **second flag** somewhere. not located yet. it is not in the baochip-1x RTL
repo under any obvious spelling, and not in `offsets/common.rs`.

## the landmine

> [!wired] developer mode erases the flag. permanently.
> `THE_FLAG_1` is a member of `KEY_SLOTS`, and `KEY_SLOTS` is defined as *the set of
> keys erased upon entry to developer mode*. `bao1x-hal/src/sigcheck.rs:762` is
> explicit: "once all secrets are erased, advance the DEVELOPER_MODE state".
>
> and `keystore/src/platform/baosec/store.rs:303` confirms it from the other side, in
> the dev-mode branch: *"check that 'the flag' is erased in this mode by leaking the
> first few bytes"*.
>
> the value is written once at FT. it is not regenerable. entering developer mode
> destroys this badge's flag with no way back.

developer mode is what you need to run your own unsigned code. so "don't flash the
badge" is not caution any more, it is the whole game: **flashing means dev mode means
the flag is gone.** if we want to run our own code, it is a second badge or nothing.

`system_init_inner` (store.rs:99) special-cases the flag so first boot does *not*
overwrite it: `if *key_range == THE_FLAG_1 { continue; }`, commented "don't overwrite
the flag, it's pre-loaded from static data". so a factory-fresh badge still has it.

## what the design says about the intended attack

bunnie documented the threat model he was defending against, in the `NUISANCE_KEYS`
comment right above the flag. that is a gift, it tells us which attacks he considered
worth spending silicon on:

- **direct imaging of the RRAM array under a microscope.** the nuisance keys exist "to
  annoy microscopists trying to read the secret key by directly imaging the RRAM
  array". he even hands over the success metric: "there is ECC on the data (2C2D on top
  of 128 bits) so any readout with better than 97% accuracy can trivially rely on ECC
  to repair the results".
- **power side channels on key readout.** `CHAFF_KEYS` are read in a random permutation
  each boot and XOR'd, specifically to break correlation across repeated reboots. the
  readout is meant to be constant time.

both of those are defended. the places he did *not* obviously defend are more
interesting.

## leads, ranked

1. **the 8-slot access-control stride.** the comment on `NUISANCE_KEYS_0` says IFR
   access control "happens on a stride of 8 slots at a time". slot 260 sits in the
   group 256..263, alongside `ROOT_SEED` (256), `RMA_KEY` (257), `CP_COOKIE` (258),
   `RESERVED_1` (259) and the COLLATERAL keys (261..264). if permission is enforced per
   group but *addressed* per slot, a granularity mismatch is exactly where a read of
   260 leaks. kill test: read the IFR access-control RTL and see whether the compare is
   on the group index or the slot index.
2. **the A1 silicon ECO.** "due to an ECO in the A1 spin of silicon that effectively
   removes the key bank, meaning only data banks exist", and "the first 8 keys in bank 0
   of NUISANCE_KEYS alias with data slots 0..7". an aliasing erratum introduced by a
   late metal fix is a classic source of an access-control hole. kill test: work out
   whether any *other* alias pair exists that maps a `Fw0` slot onto an `Open` one.
3. **`ERASE_PROOF` at slot 255.** bunnie names the risk himself: "it might be possible
   to glitch all the way to the end and just have this one erased". that is a glitch
   target he flagged as probably-unlikely, which is an invitation. note this is about
   faking dev-mode-ness, not reading the flag, so it is a means, not the end.
4. **`hazardous-debug`.** the four-byte leak at store.rs:303 is behind that feature
   gate. confirm it is off in the shipped build before assuming it is off.

## the BIO path <2026-08-06 15:25>

the live console (`[console] ` prompt, userland `bao-console`) offers
`echo, ver, test, image, bio`. **`image` and `bio` do not exist in the public
bao-console source**, which is current to 2026-08-03. so the badge runs verbs that
were not published, and those are the challenge surface.

`bio` is documented after all, just in a different repo: `baochip/bio-loader`, "load
BIO programs into devices with BIO console support". its protocol is plain text over
this same serial port:

```
bio <base64>       chunk upload
bio pin <n> [n..]  set I/O pin list
bio clk <hz>       set clock rate
bio clear          wipe stored program
bio reload         -> "BIO load successful"
bio ready          -> "OK"
```

**this is arbitrary code execution on the four PicoRV32 BIO cores, over the console,
with no flashing and no developer mode.** which means it does not touch the flag.
that is the single most important property of this path: it is the only code-execution
primitive we have found that is not self-destructive. `baochip/bio-sim` produces
`.bin` files that the loader takes directly.

### what stops BIO reading the flag, and where that might give

BIO cores reach the SoC bus through the BDMA extension, and bunnie states the defense
outright in `docs/src/ch02-00-bio-overview.md:70`:

> "access to main memory is blocked by a whitelist, which by default is empty. So,
> before attempting to use the BDMA feature, one must first declare which regions of
> memory the BIO is allowed to access. **This also helps prevent abuse of the BDMA as a
> method for bypassing host CPU security features.**"

so the whitelist is the only thing between a BIO program and the key slots. it is four
base/bounds pairs, expressed in 4KiB pages, at `0x501240e0`..`0x501240fc`.

two things about it are worth a lot:

1. **the filter can simply be switched off.** `SFR_CONFIG` (`0x50124008`) bit 6 is
   `DISABLE_FILTER_PERI` and bit 7 is `DISABLE_FILTER_MEM`, documented as "when 1,
   disables the host ... range whitelist filter. Setting this is strongly discouraged
   in secure applications." so the whole question becomes: can a BIO core reach
   `0x50124008`? in the reference setup it deliberately cannot, window 1 is
   `base 0x4000_0000`, `bounds = HW_BIO_BDMA_BASE - 0x4000_0000`, which stops exactly
   at the BIO's own register block. that exclusion is not an accident, it exists to
   stop BIO reprogramming its own filter. **if the badge's unpublished `bio` verb sets
   up a window that runs past `0x5012_4000`, the filter disables itself and the whole
   bus is open.**
2. **there is a documented silicon erratum in the filter registers.** from
   `ch02-00-bio-overview.md:1460`: *"there is a bug in the Baochip-1x which prevents the
   `FILTER` series of registers from being read back. Writes succeed, but the value
   returned when inspecting the FILTER registers is undefined."* undefined readback
   means no software can verify its own filter, and any read-modify-write against those
   registers produces an arbitrary window rather than the intended one. that is a
   classic shape for an access-control hole.

### kill tests, in order

- [ ] what windows does the badge's `bio` verb program? if it opens anything at or past
      `0x5012_4000`, go straight for `SFR_CONFIG` bits 6/7 from a BIO core.
- [ ] does any code path do a read-modify-write on `SFR_FILTER_*`? given the erratum
      that yields an attacker-influenced window.
- [ ] where do the RRAM key slots and the IFR region (`0x6040_0000`, per boot1's `ifr`
      command) sit relative to the default windows?
- [ ] `image`: entirely unknown, not in public source. get its usage before invoking.

## what would be self-inflicted

- entering developer mode. see above.
- glitching in a way that trips the on-chip glitch sensors into a state that erases.
- assuming the badge must be attacked physically because the RTL is public. reading the
  RTL is the cheap path and it is right there.
