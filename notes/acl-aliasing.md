# the ACL read index aliases two slots onto one entry

the strongest lead we have, found by reading the RRAM controller RTL rather than by
poking the badge. it is arithmetic, so it can be checked without hardware.

## the asymmetry

`baochip-1x/rtl/modules/rrc/rtl/rrc.sv:392-395`, the ACRAM address mux:

```systemverilog
assign acram_addr = ( brfsm == 4 ) ? {bridx_acv,acram_idx} :
                        acram_wrbusy ? {haddr_reg[13:5],acram_idx} :   // write path
                        ahb_read_acram ? ahbarray.haddr[16:6] :
                        acram_rdbusy ? haddr_reg[16:6] : 11'h0;        // read path
```

the two paths do not derive their index the same way:

| path | index | granularity |
| --- | --- | --- |
| write | `{haddr[13:5], acram_idx[1:0]}` | bit 5, so **32 bytes**, plus a 2-bit sub-index |
| read | `haddr[16:6]` | bit 6, so **64 bytes** |

a data slot is `SLOT_ELEMENT_LEN_BYTES` = **32 bytes**. so the read path drops the bit
that distinguishes one slot from its neighbour.

## what that means for the flag

data slots start at `DATA_SLOT_START = 0x603E_0000`, so slot *n* sits at
`0x603E_0000 + n*32`, and the ACL read index is `(addr >> 6) & 0x7FF`, which reduces to
**`n >> 1`**.

| slot | address | ACL read index |
| --- | --- | --- |
| 259 `RESERVED_1` | `0x603E_2060` | `0x081` |
| **260 `THE_FLAG_1`** | `0x603E_2080` | **`0x082`** |
| **261 `COLLATERAL[0]`** | `0x603E_20A0` | **`0x082`** |
| 262 `COLLATERAL[1]` | `0x603E_20C0` | `0x083` |

**slot 260 and slot 261 share one access-control entry on the read path.** the hardware
cannot tell them apart when deciding whether a read is permitted.

## why that pairing is the interesting one

slot 261 is the first `COLLATERAL` slot, and COLLATERAL is the one region in the whole
map that is explicitly designed to be written by someone other than baochip.
`offsets/common.rs:349`:

> "The third-party firmware must generate and populate all the COLLATERAL data slots."

and the reference implementation of doing exactly that, boot1's `rand_collateral`
(`repl.rs:870`), **clears the ACL as its first step**:

```rust
// clear the ACL so we can operate on the data
slot_mgr.set_acl(&mut rram, slot, &AccessSettings::Data(DataSlotAccess::new_with_raw_value(0)))
```

so the documented, intended, third-party workflow is to clear COLLATERAL's ACL. and
because of the read-path aliasing, clearing the ACL for slot 261 clears the entry that
also governs reads of slot 260.

the flag was placed at 260, immediately below COLLATERAL. that is either a very
pointed coincidence or the shape of the intended solve.

## what still has to be true

this is a hypothesis with two unproven legs, and neither should be assumed:

1. **can we reach an ACL clear on COLLATERAL from a path we control?** `rand_collateral`
   lives in boot1 behind `#[cfg(feature = "test-boot0-keys")]`, so almost certainly not
   in the shipped image. the keystore service (PID 3, running) is the other candidate:
   it knows COLLATERAL, calls `is_collateral_erased()` at startup, and exposes an IPC
   surface including `AesOracle` and `AesKwp`. what it does *not* obviously expose is a
   "clear the ACL" opcode. needs the opcode list read properly.
2. **once the ACL is open, who actually reads the address?** the BDMA whitelist is empty,
   so BIO still cannot. boot1's `peek` refuses the address range outright. so a cleared
   ACL is necessary but not sufficient, and the read has to come from a CPU-side mapping
   we can influence.

## kill tests

- [ ] enumerate the keystore's full `Opcode` enum. anything that writes an ACL, erases
      collateral, or takes a caller-supplied slot index is the win.
- [ ] check whether `acram_idx` on the write path can be driven to make a *write* land
      on entry `0x082` from a slot we are allowed to touch.
- [ ] confirm the aliasing empirically: read slot 261 and slot 260 under the same ACL
      state and see whether they behave identically.
- [ ] check the same arithmetic for the second flag, wherever it turns out to live.

## related

- [[the-flag]] for the flag itself and the developer-mode landmine
- [[hardware]] for the memory map these addresses come from

## applying the aliasing across the whole slot map <2026-08-06 17:10>

if the ACL read index really is `slot >> 1`, then every even/odd pair shares one entry,
and the interesting pairs are the ones that **straddle a privilege boundary**. walking
the full map:

| pair | slots | access | straddles? |
| --- | --- | --- | --- |
| 0 | `SERIAL_NUMBER` / `UUID` | Open / Open | no |
| 1 | `IFR_HASH` / `CP_ID` | Open / Open | no |
| 2 | `BAO1_PUBKEY` / `BAO2_PUBKEY` | All / All | no |
| 3 | `BETA_PUBKEY` / `DEV_PUBKEY` | All / All | no |
| **130** | **`THE_FLAG_1` / `COLLATERAL[0]`** | **Fw0 / Fw0** | no |
| **132** | **`COLLATERAL[3]` (264) / `BOOT1_PK_RECEIPT_SLOT0` (265)** | **Fw0 / Open** | **yes** |

pair 132 is the one that matters structurally: slot 264 is a COLLATERAL key with
`PartitionAccess::Fw0`, and slot 265 is a boot1 public-key receipt with
`PartitionAccess::Open`. they share one access-control entry on the read path. if the
permissive side wins, **slot 264 is readable from an open context and should not be**.

that is a genuine access-control bypass, and it is a *checkable prediction* rather than
a theory: read slot 264 from an unprivileged context and see whether it answers.

the bad news for us: it yields `COLLATERAL[3]`, not the flag. the flag's own pair (130)
is Fw0 on both sides, so the aliasing buys nothing there. slot 260 was placed next to
another Fw0 slot, which reads like the placement was thought about.

it is still worth proving, for two reasons. it is a real finding about the silicon that
is worth reporting to baochip regardless of the CTF. and if the *write* path can be made
to land an ACL on the wrong row, the same mechanism could open pair 130.

**blocked on the same thing as everything else:** we have no read primitive from an open
context. BDMA is filtered, `peek` is absent, and every CPU-side read needs code we cannot
run without erasing the flag. so this stays a prediction until something else opens.
