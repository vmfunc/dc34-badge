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

## what would be self-inflicted

- entering developer mode. see above.
- glitching in a way that trips the on-chip glitch sensors into a state that erases.
- assuming the badge must be attacked physically because the RTL is public. reading the
  RTL is the cheap path and it is right there.
