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

## confirmed on hardware <2026-08-06 15:30..16:00>

**the flag's address.** `DATA_SLOT_START = 0x603E_0000` and `SLOT_ELEMENT_LEN_BYTES = 32`
(`libs/bao1x-api/src/offsets.rs:80`), so slot 260 is at **`0x603E_2080`**, 32 bytes.
the per-slot ACL table is at `ACRAM_DATASLOT_START = 0x603D_C000`, 4 bytes per slot, so
slot 260's ACL entry is at `0x603D_C410`. one-way counters live at `0x603D_A000` and
`0x603D_B000`. the IFR that boot1's `ifr` command dumps is at `0x6040_0000`.

**the console's real command surface.** `help` under-reports. brute forcing subcommands
found two that matter, neither documented anywhere public:

```
bio tx <decimal|0xhex> [repeat]   push a word to the BIO
bio rx                            pop a word, printed as hex
```

on an empty queue `bio rx` prints `timeout` and then the sentinel `eb1f646f`. the log
messages carry their own source line, and that is load bearing: an rx result comes from
`src/cmds/bio.rs:508` and the tx echo from `:542`. matching on the value alone reads your
own transmission back and looks exactly like a successful memory read.

**code execution is real and was proven, not assumed.** `probe.S` pushes `0x0BADF00D`
unconditionally; `echo_inc.S` pops a word, adds one, pushes it back. loading the second
over the first and draining gave **`badf00e`**. that value can only exist if both
programs actually ran on a core. so: arbitrary RV32 code on the BIO, bidirectional data
channel, no flashing, no developer mode, flag untouched.

**the loader's real behaviour**, versus the published `bio-loader`:
- `bio pad` answers `OK` then `SUCCESS`, and `bio reload` answers `SUCCESS`, so a
  first-line response match desynchronises. drain until a match instead.
- chunks must be paced. back to back uploads produce
  `Input overflow to N, dropping keys!` from the keyboard service and silently lose code.
- `MAX_CODE_BYTES` is `0xF00` = 3840, so 60 chunks, not the 64 the README implies.
- the four cores start at different offsets, so a small program at offset 0 leaves the
  others running zeros. tile the whole space and use `.option norvc` so a core entering
  mid-block still lands on an instruction boundary.

**the read is blocked, as predicted.** `peek.S` (pop address, `lw`, push word) never
returns a loaded value. instrumenting it with a marker word showed the marker never
arrives either, and the core stops popping entirely after the first `lw`. that is the
signature of a load that never retires: **the BDMA whitelist is empty and the access is
filtered**, exactly as `ch02-00-bio-overview.md:70` describes. this is now measured
rather than inferred.

### the thing that changes the picture: `lightgenes`

flooding the queue made the firmware start logging
`WARN:dc34_console::bio::lightgenes: errant Rx in express (src/bio/lightgenes/mod.rs:167)`.

so the BIO is **not idle hardware we borrowed**. the badge runs its own BIO program
called a *lightgene*, and `express` is its run loop. `bio tx`/`bio rx` are that
subsystem's protocol, and our raw words are being fed to it and rejected.

that reframes the whole challenge. the intended path is almost certainly to write a
*lightgene*, not to hijack the BIO as a bare coprocessor. and the DMA windows that
matter are whichever ones the lightgene runtime configures for itself.

### state right now

the badge is healthy and the console still answers, but the lightgenes task is stuck in
a warning loop from the words we left in its queue, several hundred lines a second.
`bio clear` is accepted and draining the queue does not stop it. **a replug clears it**,
and a replug is completely safe here: RRAM is non-volatile, nothing was flashed, no
developer-mode path was touched.

### the filter, from the RTL rather than the prose <2026-08-06 16:05>

`baochip-1x/rtl/modules/bio_bdma/rtl/bio_bdma.sv:2470`, module `axil_filter`:

```systemverilog
bounds_unchecked[k] = base[k] + length[k];
bounds[k] = bounds_unchecked[k] > 21'h0_FFFFF ? 20'hFFFFF : bounds_unchecked[k][19:0];
match_read[k] = (s_axi_araddr[31:12] >= base[k]) && (s_axi_araddr[31:12] < bounds[k]);
...
allow_read = |match_read | disable_filter;
assign m_axi_araddr = allow_read ? s_axi_araddr : gutter;
```

the important part is the last line. **a filtered access is not rejected, it is
redirected.** the transaction still goes out, with its address replaced by `gutter`.
there is no error response and no abort.

and `gutter` is itself a software register: `sfr_mem_gutter` at APB offset `0xA0`,
`sfr_peri_gutter` at `0xA4`, both reset to zero.

so the default behaviour of an out-of-window read is: **redirect to address
0x00000000**. if nothing is mapped there, the AXI read never gets a response, and the
BIO core waits on it forever. that is a complete, RTL-grounded explanation of what we
measured: the core swallowed one address and never produced another word.

consequences that actually change how we work:

- an out-of-window read **hangs the core permanently**. so an address sweep has to
  treat a timeout as "filtered" and reload the program before the next probe. one
  probe per load.
- with base and length both zero at reset, `addr >= 0 && addr < 0` is false for every
  address, so an unconfigured filter rejects everything. the whitelist really is empty
  by default, as documented.
- the only way a BIO core reads RRAM is if the host opened a window covering page
  `0x603E2`. the host is the only thing that can write `SFR_FILTER_*`, and BIO's own
  peripheral accesses go through the second filter instance, so it cannot reach its own
  configuration to widen it.

which makes the real question empirical: **what windows does the lightgenes runtime
open for itself?** whatever they are, we inherit them. that is a sweep, not a guess.

### measured: the BDMA whitelist is completely empty <2026-08-06 16:30>

swept with the address baked into the program (there is no host->core data path,
see below), continuous-push oracle, control program verified live immediately before:

| address | region | verdict |
| --- | --- | --- |
| `0x603E_2080` | the flag, RRAM data slot 260 | filtered |
| `0x6000_0000` | RRAM base | filtered |
| `0x6100_0000` | SRAM base | filtered |
| `0x4000_0000` | crypto segment | filtered |

not one window is open. so the lightgenes runtime does **not** leave a DMA window
configured that we could inherit, and BIO cannot widen its own. **the BDMA route to
the flag is closed.** that is a real result rather than a failure: it eliminates the
whole branch and it matches the RTL exactly.

two protocol facts learned the hard way, both worth keeping:

- **there is no host to core data path.** `bio tx` injects into the same queue the
  core pushes *to*, so a value sent with tx returns on rx without any core seeing it.
  anything a program needs must be assembled into it. that is why the sweep is one
  upload per probe.
- **a value pushed once gets eaten.** the badge's own lightgenes `express` loop pops
  the same queue, which is where the `errant Rx` warnings come from. only a program
  that pushes *continuously* keeps a value in the queue long enough for `bio rx`.
  every one-shot marker scheme silently reads as "nothing happened".

### measured: boot1's `peek` refuses the flag by address

the privileged fallback does not work either, and the refusal is explicit.
`bao1x-boot/boot1/src/repl.rs:968`:

```rust
#[cfg(feature = "unsafe-debug")]
"peek" => {
    ...
    if addr >= utralib::HW_RERAM_MEM + bao1x_api::RRAM_STORAGE_LEN
        && addr < utralib::HW_RERAM_MEM + utralib::HW_RERAM_MEM_LEN
    {
        return Err(Error::help("Peek disallowed for security-related sectors"));
    }
```

with `HW_RERAM_MEM = 0x6000_0000`, `RRAM_STORAGE_LEN = 0x3D_A000` and
`HW_RERAM_MEM_LEN = 0x40_0000`, the blocked window is
**`0x603D_A000` .. `0x6040_0000`**. that begins exactly at `ONEWAY_START` and covers
the one-way counters, the ACL table, and every data slot including the flag at
`0x603E_2080`. and the command is feature-gated behind `unsafe-debug`, so it is
probably not even compiled into the shipped boot1.

so the two obvious doors are both deliberately shut, by two different mechanisms, by
someone who clearly expected us. that is a good sign about where the real answer is:
somewhere less direct.

### next, reranked after the two dead ends

1. **the `image` verb.** still completely unexamined and it is the other unpublished
   command. it takes the same 70-byte chunked base64 framing as `bio` (the loader's own
   docstring says the format is "identical to send_image.py" and calls the payload
   "pixel data"). an image path that writes pixels somewhere is a write primitive, and
   write primitives are worth more than read primitives when the read is filtered.
2. **write a real lightgene rather than a raw BIO blob.** we have been loading bare
   programs into a runtime that expects genes. if the runtime configures anything on
   behalf of a gene it recognises, we only get it by speaking its language.
   `baochip/bio-sim` has working examples in `sw/`, including `test-ws2812`.
3. **[[acl-aliasing|the ACL read index aliases slot 260 onto slot 261]]** .. now the
   strongest lead, and arithmetically confirmed. see its own note.
4. **the A1 ECO aliasing.** "an ECO in the A1 spin of silicon effectively removes the
   key bank, meaning only data banks exist", and the first 8 nuisance keys "alias with
   data slots 0..7". an aliasing erratum from a late metal fix is exactly the shape of
   an access-control hole. work out whether any alias maps a `Fw0` slot onto an open
   one. this is a paper exercise against the RTL, no hardware needed.
5. **the ACL table itself** at `0x603D_C410` for slot 260. changing a permission is a
   different operation from reading a secret and may be guarded differently.
6. **IRIS.** the badge is explicitly built to be inspected under infrared, and bunnie's
   own comment concedes RRAM imaging works above 97% accuracy because ECC repairs the
   rest. it is the one path the design openly admits to. it needs a microscope, so it
   is a last resort, but it is not a joke.

## the boot1 REPL, and what it costs to get there <2026-08-06 16:55>

boot1 prints its own command list at `repl.rs:1135`:

> altboot, audit, boot, boardtype, bootwait, echo, idmode, ifr, localecho, lockdown,
> paranoid, require-pq, reset, self_destruct, skipping, uf2, usb_speed

cross-referencing the `#[cfg]` gates, what actually ships versus what is compiled out:

| available in the shipped boot1 | gated out |
| --- | --- |
| `ifr`, `audit`, `boardtype`, `idmode`, `reset`, `boot`, `localecho`, `bootwait`, `paranoid`, `skipping`, `altboot`, `lockdown`, `self_destruct`, `ate`, `atecheck`, `usb_speed` | `peek` (`unsafe-debug`), `rand_collateral` and `publock` (`test-boot0-keys`), `pq`, `qe`, `bogomips` |

so **`peek` is almost certainly not even present**, which retires that idea entirely, and
`rand_collateral` (the one thing that would clear COLLATERAL's ACL for us) is gated out
too. that closes the easy version of [[acl-aliasing]].

`ifr` does ship. it dumps `0x6040_0000` for `0x400` bytes, which per `rrc.sv` is where
the RRAM partition and permission configuration lives (`nvrcfgdata.cfgrrsub`, the
`PM_READ_DIS` / `PM_WRITE_DIS` bytes). that is the access-control configuration itself,
which is worth reading even though it is not the flag.

### the cost, which is why this is not an automatic yes

boot1 is entered by holding a button at power-on, but reaching its prompt reliably means
enabling `bootwait`, and **bootwait is stored in a one-way counter**
(`repl.rs:456-490`): enable and disable both work by *incrementing* until the coded
value lands on the state you want.

```rust
} else if args[0] == "enable" {
    while one_way.get_decoded::<BootWaitCoding>()... != BootWaitCoding::Enable {
        one_way.inc_coded::<BootWaitCoding>().unwrap();
    }
```

one-way counters do not go backwards and they are finite. elsewhere in the tree the
developer-mode counter is bounds-checked at `< 15`. so every enable/disable cycle
permanently consumes part of a budget, and if the counter saturates while bootwait is
*enabled*, this badge waits at the bootloader on every power-on for the rest of its life.
recoverable in the sense that `boot` still boots it, but it is a permanent change to
azzie's badge.

**this one is her call, not mine.** it is the first genuinely irreversible thing we have
come to.

## what would be self-inflicted

- entering developer mode. see above.
- glitching in a way that trips the on-chip glitch sensors into a state that erases.
- assuming the badge must be attacked physically because the RTL is public. reading the
  RTL is the cheap path and it is right there.
