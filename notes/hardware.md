# hardware

## what the badge is

**baochip-1x**, bunnie huang's "mostly open" SoC, TSMC 22nm. this is the first time the
DC badge is a chip whose RTL you can read, which changes the whole shape of the work:
the usual first day of *guessing* the peripheral map is replaced by reading it.

confirmed from bunnie's writeup and the baochip repos:

| | |
| --- | --- |
| main core | VexRiscv, **rv32imac**, with MMU, 350 MHz |
| io coprocessor | "BIO", **quad PicoRV32 @ 700 MHz** |
| sram | 2 MiB, ECC protected |
| nonvolatile | **4 MiB RRAM**, 32-byte page size, faster writes than flash |
| usb | USB 2.0 HS (PHY is one of the closed blocks) |
| os | **Xous**, pure-rust microkernel, `betrusted-io/xous-core` |
| security | TRNG, crypto accelerators, secure mesh, **glitch sensors**, hardware key slots, one-way counters |
| aes | AES instructions in the main core, used with chaffing as a side-channel countermeasure |
| add-ons | SAO v2.0 headers |

**open vs closed:** everything that computes on data is open and simulatable. closed
are the AXI bus framework, the USB PHY, and the analog (PLL, regulators, IO pads).
bunnie's framing is that the closed parts are "wires". worth testing that claim rather
than accepting it, but it does mean the interesting attack surface is readable RTL.

> [!wired] the glitch sensors are the headline for us
> a 22nm part with explicit glitch detection and a secure mesh is not the usual
> badge target. voltage/clock glitching is the reflex move on an MCU CTF and here it
> is *anticipated*. read the sensor RTL before burning a day on chipwhisperer work.

## the bootloader, and the thing that will bite

firmware arrives as **UF2**. hold `PROG` (the button nearest USB) while plugging in,
the badge enumerates as a mass storage volume named `BAOCHIP`, you copy UF2 files on,
press `PROG` again to run.

three artifacts, from `cargo xtask dabao` in xous-core, built for
`riscv32imac-unknown-xous-elf`:

- `loader.uf2`
- `xous.uf2`
- `apps.uf2`

first flash takes all three; after that only `apps.uf2` if the kernel is unchanged.

**UF2 mass storage is a write path, not a read path.** there is no `picotool save`
equivalent here. so:

- you cannot take a baseline dump of the shipped image before touching it.
- copying `apps.uf2` over the stock app **destroys the CTF challenge on that badge**,
  and the stock firmware is not published until after the con.
- `tools/dump-firmware.sh baochip` exists solely to stop you doing this by reflex.

if we want our own code *and* the challenge, that is two badges, not one.

## console

serial over USB, **1000000 baud 8N1**. on the dabao dev board the pins are PB14 (TX)
and PB13 (RX); on the badge, find the equivalent pads before assuming.

wrong baud presents as "there is no console", which is exactly how you walk past the
single most informative surface on the board. `tools/serial-log.sh` defaults to
1000000 for this reason.

## usb, as observed <2026-08-06 15:10>

it **does** enumerate. `1d50:6198`, `Baochip / Baosec-lite`, serial `H88Y1M`, high
speed, bus powered, 100mA, bcdUSB 2.10, IAD composite. `1d50` is openmoko's shared
VID, the usual open-hardware allocation. full dump in [../hw/usb-descriptors.txt](../hw/usb-descriptors.txt).

so "baosec-lite" is the product identity, which is the name to search the xous tree
for, not "badge".

| if | class | what it is | endpoints |
| --- | --- | --- | --- |
| 0 | HID | **CTAPHID / FIDO2**, report desc starts `06 d0 f1` (FIDO alliance usage page 0xF1D0), usage 0x01 | 0x81 IN / 0x01 OUT, interrupt, 64 B, bInterval 5 |
| 1 | HID | keyboard, boot subclass declared | 0x82 IN 32 B bInterval 10, 0x02 OUT 8 B bInterval **100** |
| 2 | CDC | ACM control, AT-commands protocol | 0x83 IN interrupt 16 B |
| 3 | CDC data | the console, `/dev/ttyACM0` | 0x84 IN / 0x04 OUT, **bulk, 512 B** |

the fido2 + keyboard + console combination is the "security token, password manager,
HSM" pitch made concrete: if0 is how it does webauthn, if1 is how it types your
passwords at you.

> [!wired] two descriptor defects in shipped firmware
> 1. interface 1 endpoint 0x02 declares `bInterval 100`. for a high-speed interrupt
>    endpoint the legal range is 1..16 (encoded as 2^(n-1) microframes), so 100 is
>    out of spec and linux clamps it to 10 with a warning.
> 2. interface 1 declares **Boot Interface Subclass / Keyboard**, which contractually
>    means the 8-byte boot report. its actual report descriptor is 1 modifier byte,
>    56 bits of padding, then a **136-bit NKRO key bitmap**, 25 bytes total. a host
>    that trusted the boot-protocol claim would mis-parse it.
>
> neither is exploitable on its own. both say the usb stack is homegrown and was not
> checked against a descriptor validator, which is a reason to look harder at the
> device-side CTAPHID and CDC parsers than you otherwise would.

### console access, on nixos

`/dev/ttyACM0` is `root:dialout 0660` and quaver is not in `dialout`. durable fix in
the nixfiles:

```nix
users.users.quaver.extraGroups = [ "dialout" ];
```

that needs a rebuild and a re-login, so at a con the throwaway is `sudo chmod o+rw
/dev/ttyACM0`, which evaporates on replug anyway.

## power, and why unplugging does not reset it

the badge carries an **AXP2101 PMU with a battery**, configured in
`libs/bao1x-hal/src/axp2101.rs`. so **pulling the USB cable does not power the badge
off**: it keeps running on the battery, and a wedged firmware stays wedged across a
replug. this cost us a diagnostic loop.

the button press timings the firmware programs (`axp2101.rs:373-381`):

```rust
// pwron 16s to shut the enable
i2c.i2c_write(AXP2101_DEV, REG_PMUCOMMON, &[0b00110100]).unwrap();
// level timings: irq 1.5s, offlevel 6s, onlevel 1s
i2c.i2c_write(AXP2101_DEV, REG_LEVELTIMES, &[0b0_01_01_10]).unwrap();
```

| press | effect |
| --- | --- |
| ~1 s | power **on** (onlevel) |
| 1.5 s | interrupt to firmware (irq) |
| **6 s** | forced power **off** (offlevel). this is the reset you want |
| 16 s | hard kill, shuts the enable outright |

`REG_BATFET` is set to `0`, "disable on pwroff", so a real power-off actually
disconnects the battery rather than leaving rails floating. that is what makes the 6
second hold a genuine cold boot.

none of this touches RRAM, so none of it can affect the flag.

## test points / headers

fill from the physical badge. photograph both sides into `hw/` first.

| label | guess | confirmed | notes |
| --- | --- | --- | --- |
| SAO | v2.0 add-on header | no | i2c + gpio per spec, a legitimate injection surface |
| PROG | bootloader entry | no | hold while plugging usb |

## debug interfaces

- **jtag:** unconfirmed on the badge. the RTL is public, so whether a debug module is
  instantiated and whether it is fused off is a *readable* question, not a guessable one.
- **usb:** capture `lsusb -v` output into this file on first plug.

## the order to work in

1. photograph both sides, read the laser marks and silkscreen.
2. `lsusb -v`, then console at 1000000. write down everything it prints on boot.
3. read the RTL and the xous source for the parts you would otherwise reverse. this is
   the whole point of an open chip and it is faster than the disassembler.
4. only then start writing to anything.
