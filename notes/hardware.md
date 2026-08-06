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
