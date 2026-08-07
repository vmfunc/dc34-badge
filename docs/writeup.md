# dc34 badge .. flag 1

> draft. nothing here goes public until the CTF closes.
> written during day one, 2026-08-06, from `notes/00-log.md` rather than from memory.

## the badge

DEF CON 34's badge is a **Baochip-1x**: bunnie huang's "mostly open" 22 nm SoC, and the
first DC badge whose RTL you can read. VexRiscv rv32imac with an MMU at 350 MHz, a quad
PicoRV32 "BIO" I/O coprocessor at 700 MHz, 2 MiB of ECC SRAM, 4 MiB of RRAM, USB 2.0 HS,
running **Xous**, a pure-rust microkernel. it enumerates as `1d50:6198` "Baosec-lite".

it is a security token, a password manager and an HSM, and it is designed to be verified
under an infrared microscope. that last property turns out to be the point.

## what the challenge actually is

not found by reverse engineering. found by reading the public source, which is the whole
advantage of an open chip. `xous-core/libs/bao1x-api/src/offsets/baosec.rs:151`:

```rust
/// A test value placed by FT into the memory array. If you can read the original value,
/// you've captured a flag!
/// There is a second flag stored somewhere else. Can you find it?
pub const THE_FLAG_1: SlotIndex = SlotIndex::Data(260, PartitionAccess::Fw0, RwPerms::ReadWrite);
```

so flag 1 is **the original 32-byte contents of RRAM data slot 260**. with
`DATA_SLOT_START = 0x603E_0000` and 32 bytes per slot, that is **`0x603E_2080`**.
`PartitionAccess::Fw0` means only the bootloader and key manager may touch it, and FT is
final test, so the value was programmed at manufacture and is derived from nothing on
the device. it cannot be computed, guessed, or regenerated. it can only be read.

## the trap, which is the real design

`THE_FLAG_1` is a member of `KEY_SLOTS`. `KEY_SLOTS` is defined as *the set of keys
erased on entry to developer mode*. and developer mode is what running your own code
requires.

`libs/bao1x-hal/src/sigcheck.rs:735-775` is the exact mechanism. `erase_secrets()` walks
`KEY_SLOTS`, erases every slot, stores the erasure proof, and **only then** advances the
counter:

```rust
// once all secrets are erased, advance the DEVELOPER_MODE state
if owc.get(DEVELOPER_MODE).unwrap() < 15 {
    unsafe { owc.inc(DEVELOPER_MODE).unwrap() };
}
```

the erase is a *precondition* of running unsigned code, not a consequence of it. there
is no window and no ordering trick. **flashing the badge is not a risk to the flag, it
is the destruction of the flag**, and there is no restore path because the value only
ever existed on that one die.

this is why the first rule in this repo, written before the badge was even plugged in,
is "do not flash this badge". it turned out to be the entire game.

## every software path, and why each is closed

all of these were measured on the badge, not inferred.

**BIO code execution works.** `bio` is an undocumented console verb that turns out to be
`baochip/bio-loader`'s protocol: base64 chunks of RV32 code uploaded over the serial
console onto the four PicoRV32 cores. no flashing, no developer mode, the flag untouched.
proven by loading a program that pushes `0x0BADF00D`, then a second that pops-adds-one-
pushes, and reading back `badf00e`, a value neither the host nor either program alone
could produce.

**but BIO cannot read memory.** BDMA access is gated by a four-entry page whitelist, and
`bio_bdma.sv:2576` shows what a miss does:

```systemverilog
assign m_axi_araddr = allow_read ? s_axi_araddr : gutter;
```

a filtered read is *redirected*, not rejected. `gutter` resets to `0x00000000`, nothing
answers there, the read never retires, and the core hangs forever. that hang is a clean
oracle, and sweeping with it showed **not one window is open**: the flag page, RRAM base,
SRAM base and the crypto segment are all filtered. the badge drives its LEDs over GPIO,
not DMA, so nothing ever configures a window for us to inherit.

**boot1's `peek` is closed twice over.** it refuses `0x603D_A000`..`0x6040_0000` by
address, a range that begins exactly at the one-way counters and covers every data slot
including the flag. and it is behind `#[cfg(feature = "unsafe-debug")]`, absent from the
shipped build, which the bootloader's own command list confirms.

**boot1's `uf2` is a write path**, bounded below `0x603D_A000`, so it cannot address the
flag, and using it with an unsigned image triggers the erase anyway.

**`image` is a bounded framebuffer.** 32 chunks of 64 bytes = 2048 bytes = 128x128
monochrome, matching the sh1107 panel. sequence enforced, every out-of-range index
rejected. the u16 chunk index is not an arbitrary write offset.

**CTAPHID is a stub.** INIT works and allocates channels, advertising protocol 2 and
caps `0x05`. PING, WINK, MSG and every CBOR command return nothing at all. the advertised
capabilities are not real.

**JTAG is fused off**, confirmed against `secboot.rs`'s hardcoded IFR reference: the
bytes at `0x6040_0180` read `00 00 00 00 82 8c 42 6a 00 ...`, matching exactly, which is
the check that asserts the Cortex-M7 and hardware debug are both disabled.

**signing our own image does not help.** `audit` shows boot1 and the next stage are
signed with the *beta* key rather than production, and xous-core ships a public
`devkey/`. but a dev-key-signed image runs only after `erase_secrets()`, per above. the
only keys that would not erase are `bao1`, `bao2` and `beta`, and none of those private
keys are public.

## the one genuine bug we found

`rtl/modules/rrc/rtl/rrc.sv:392-395` derives the ACRAM index differently on its two
paths. writes use `{haddr[13:5], acram_idx}`, granular to 32 bytes. reads use
`haddr[16:6]`, granular to 64. a data slot is **32 bytes**, so the read path drops the
bit that distinguishes a slot from its neighbour and the ACL read index collapses to
`slot >> 1`:

| slot | address | ACL read index |
| --- | --- | --- |
| 260 `THE_FLAG_1` | `0x603E_2080` | **`0x082`** |
| 261 `COLLATERAL[0]` | `0x603E_20A0` | **`0x082`** |

the flag shares one access-control entry with the first COLLATERAL slot, and COLLATERAL
is the one region explicitly designed to be written by third parties, whose reference
workflow *clears the ACL* as its first step. the flag sits immediately below it.

it did not turn into an exploit here, because the routine that clears that ACL
(`rand_collateral`) is behind `test-boot0-keys` and is not in the shipped bootloader, and
the keystore exposes no ACL-write opcode. but the aliasing is real, arithmetic, and
checkable without hardware. see [../notes/acl-aliasing.md](../notes/acl-aliasing.md).

## conclusion: flag 1 is a physical challenge

every software door is shut, and each by a *different* deliberate mechanism. that is not
the signature of an accidentally-hard challenge.

the design says what it expects instead. the badge's headline feature is that it is built
for **IRIS**, infrared in-situ inspection, so an owner can verify the die against the
published RTL with a $180 camera. the flag is "a test value placed by FT into **the memory
array**". and the countermeasure placed immediately above it in the source, `NUISANCE_KEYS`,
exists in bunnie's own words

> "to annoy microscopists trying to read the secret key by directly imaging the RRAM array"

with the concession that

> "there is ECC on the data (2C2D on top of 128 bits) so any readout with better than 97%
> accuracy can trivially rely on ECC to repair the results"

he named the attack, the tool, and the pass mark. **flag 1 is meant to be read off the
die**, not out of a terminal. the software surface is hardened precisely so that the
imaging path is the one that works.

## what would actually finish it

- IR imaging of the RRAM array, targeting slot 260 at `0x603E_2080`, 32 bytes.
- readout accuracy above 97%; the on-die ECC (2C2D over 128 bits) repairs the remainder.
- the nuisance keys around it are noise by design, so the array position has to be
  located precisely rather than read opportunistically.

## the second flag

hinted in the same comment and **not** present anywhere in the public tree, nor in the
1 KiB IFR region (`hw/ifr.bin`, whose only ASCII is the lot code `94912066M06T`). it is
most likely inside the unpublished `dc34_console` firmware, which fits the split: flag 2
is the software half of the pair, flag 1 is the physical half. the way in is the
`lightgenes` runtime, `src/bio/lightgenes/mod.rs`, which we only half-mapped.

## what i would do differently

- the tx/rx queue on `bio` is not a host-to-core path, it is the queue the core pushes
  *to*. a value sent with `bio tx` comes straight back on `bio rx` without any core
  seeing it. i spent real time reading my own transmissions back and nearly believed
  them. the fix was matching on the log line number, `bio.rs:508` for an rx result
  versus `:542` for the tx echo.
- a value pushed once is eaten by the badge's own lightgenes `express` loop. only
  continuous pushing survives to be read, so every one-shot marker scheme reads as
  "nothing happened", which is an excellent way to draw the wrong conclusion.
- the badge has a battery. unplugging USB does not power-cycle it, and a wedged firmware
  stays wedged. hold power for 6 s.

## credit

badge and silicon: andrew "bunnie" huang and baochip. the RTL, the HAL, the OS and the
threat-model comments are all public, and reading them was faster than reversing anything.
