# running log

append-only. newest at the bottom. timestamp everything, local vegas time.

the point of this file is that at 04:00 on day three, past-you is a stranger and
this is the only thing that remembers what you already tried. write the failures
down too, they are half the map.

format, one line per event, no ceremony:

```
[fri 14:22] uart on tp4/tp5, 115200 8n1, boot banner dumps a version string
[fri 14:41] tried picotool save, denied .. RDP-ish? see notes/firmware.md
```

## wed

## thu

```
[thu 15:10] badge plugged into minnow (fw12), port 3-5. it DOES enumerate over usb,
            so the earlier guess that xous might not present a usb device class was
            wrong. 1d50:6198 "Baochip Baosec-lite", serial H88Y1M, high speed.
            1d50 is openmoko's shared VID, the usual open-hardware allocation.
[thu 15:11] 4 interfaces: if0 HID/CTAPHID (fido2), if1 HID boot keyboard,
            if2+if3 CDC ACM -> /dev/ttyACM0. bus powered, 100mA.
            full descriptors saved to hw/usb-descriptors.txt.
[thu 15:12] two descriptor defects in shipped firmware, see notes/hardware.md:
            keyboard EP 0x02 has bInterval 100 (out of spec, kernel clamps to 10),
            and if1 declares Boot Keyboard subclass while its report descriptor is
            a 25-byte NKRO bitmap, not the 8-byte boot report.
[thu 15:13] BLOCKED on console: /dev/ttyACM0 is root:dialout 0660 and quaver is not
            in dialout. no passwordless sudo. nothing read from the console yet.
[thu 15:20] cloned xous-core + baochip-1x to ~/workspace/. grepped for "baosec".
[thu 15:22] FOUND THE CHALLENGE IN THE SOURCE. bao1x-api/src/offsets/baosec.rs:151,
            THE_FLAG_1 = RRAM data slot 260, PartitionAccess::Fw0, written at FT.
            "if you can read the original value, you've captured a flag!" plus a
            second flag elsewhere, not yet located.
[thu 15:24] LANDMINE: THE_FLAG_1 is in KEY_SLOTS, which is the set erased on entry to
            developer mode (sigcheck.rs:762, store.rs:303). dev mode is what running
            unsigned code requires. so flashing this badge destroys its flag with no
            way back, the value is FT-programmed and not regenerable. see
            notes/the-flag.md. rule 1 in the readme is now load-bearing, not caution.
[thu 15:18] console open. azzie chmod'd /dev/ttyACM0. 20s passive capture: silent.
[thu 15:19] read the boot1 REPL command table BEFORE typing anything, which was worth
            it: it has "self_destruct void_my_warrantee", permanent brick, no returns.
            do not go near it. boot1 also has "peek" and "ifr" (dumps 0x6040_0000+0x400,
            with deliberate black_box asserts to stop it being a glitchable dump
            primitive, which tells you what bunnie expected people to try).
[thu 15:20] bare newline -> prompt is "[console] ". this is userland bao-console, not
            the boot1 REPL. `help` -> "Commands: echo, ver, test, image, bio".
[thu 15:22] "image" and "bio" are NOT in the public bao-console source (clone current
            to 2026-08-03, no dc34 branch on the remote). unpublished verbs = the
            challenge surface.
[thu 15:24] bio is documented in a sibling repo, baochip/bio-loader: plain-text upload
            of BIO programs over this same port. ARBITRARY CODE EXECUTION on the four
            picorv32 cores with no flash and no dev mode, so it does not cost the flag.
[thu 15:26] BIO's bus access is gated by a 4-entry page whitelist at 0x501240e0.
            SFR_CONFIG bit6/bit7 disable that filter outright, and the reference window
            setup deliberately stops at HW_BIO_BDMA_BASE so BIO can't reach its own
            config. plus a documented erratum: FILTER regs are write-only, readback is
            undefined. see notes/the-flag.md for the ranked kill tests.
```

```
[thu 15:47] replug. badge does NOT re-enumerate. port 3-5 sees a device and keeps
            trying: "device descriptor read/64, error -110" (timeout), then "device
            not accepting address, error -62", then "unable to enumerate USB device"
            after an automatic port power cycle. four attempts, device numbers 29-32.
[thu 15:48] so: electrically present, not answering enumeration. that is a hung usb
            stack on the badge, not a cable and not a dead port. the port itself is
            fine, it detected the device and power-cycled it on its own.
            the flag is unaffected: RRAM is non-volatile, we never flashed, never
            entered developer mode, and never wrote any slot. nothing we did can
            reach the stored value.
            suspected cause: the lightgenes warning loop was writing several hundred
            log lines a second when it was unplugged, or the replug was too quick for
            the rails to collapse.
```

## fri

## sat

## sun

```
[thu 16:20] bootwait ENABLED (authorised). one-way counter spent. `test bootwait
            check` -> true. no software reset verb exists: brute-forced 47 plausible
            top-level console verbs, zero hits beyond echo/ver/test/image/bio. so
            reaching boot1 needs a physical 6s power-button hold.
[thu 16:35] `image` fully mapped: 32 chunks x 64 bytes = 2048 bytes = 128x128 mono,
            the sh1107 panel. sequence enforced, every out-of-range index rejected.
            the u16 chunk index is NOT an arbitrary write offset. idea dead.
            it does give us the screen as an output channel.
[thu 16:45] CTAPHID on /dev/hidraw0 (interface 1.0, logind uaccess, no root needed):
            INIT works and allocates channels (0x3, 0x4, 0x5 across attempts), reports
            protocol 2, device 1.0.0, caps 0x05 = WINK|CBOR. but PING, WINK, MSG and
            every CBOR command return NOTHING, even at 6s timeouts. the fido stack is
            an INIT-only stub. dead end, and notably the advertised caps are a lie.
[thu 16:50] state of play: every software path we control is exhausted except boot1.
            BDMA filtered, image bounded, ctap stubbed, no acl-write opcode in the
            keystore, no software reset. boot1 needs a power cycle.
```

```
[thu 17:20] project-sync run. dc34 note reconciled against 21 commits, badger-badge's
            "not a git repo yet" corrected, daily-log-harvest browser source closed.
[thu 17:40] bio.h from bio-sim documents the whole reserved-register map we had been
            half-guessing: x16-x19 fifos, x20 quantum, x26 gpio mask, x27 event mask,
            x28/x29 set/clear event bits, x30 event status, and x31 = core id in
            [31:30] plus aclk counter in [29:0]. wrote coreid.S to finally answer
            which cores execute our uploads.
[thu 17:55] **REPRODUCIBLE WEDGE.** uploading BIO chunks to a freshly-booted badge
            overflows the console's input path ("Input overflow to 17, dropping keys!"
            from the keyboard service) and then the console goes fully silent: usb
            still enumerated as 1d50:6198, ttyACM0 present, zero bytes out, no reply
            to a bare newline. this is the second time. the first was the lightgenes
            warning flood.
            two real bugs of mine found while chasing it: writes must be paced INSIDE
            the line, not just between lines, and the chunk loop was taking the first
            response line rather than draining to a verdict, so a log line got read as
            the answer. both fixed.
            recovery is another 6s power hold. after a cold boot the badge is busier
            (lightgene running) and needs much gentler input than it did earlier.
```

```
[thu 18:27] sent `boot` from boot1 to hand control to xous. the badge did NOT come
            back: "Device not responding to setup address", error -71, retried at
            FULL speed (it is a high-speed device), device numbers into the 70s.
            third wedge of the day, and the first one triggered by the boot1->xous
            transition rather than by console traffic. the same `boot` worked cleanly
            at 16:53, so it is intermittent, not deterministic.
            note the speed downgrade: full-speed retries on a HS-capable device mean
            the link is renegotiating badly, not just that firmware is slow to answer.
[thu 18:30] consequence worth acting on: with bootwait ENABLED every cold boot lands
            in boot1, and every boot1->xous transition risks this. we have already
            taken everything boot1 has to give (audit + the full ifr dump are
            captured), so bootwait is now pure cost. disable it on the next boot.
            it spends another one-way increment, but it also means cold boots land
            straight in a usable xous, and if the counter ever saturates, saturating
            while DISABLED is the better terminal state: the badge boots normally
            forever rather than stopping at the bootloader forever.
```

```
[thu 19:0x] ud2 logo upload via `image`. three of my own bugs, then the real cause.
            mine: (1) byte-at-a-time pacing CORRUPTS input, `ver` echoes as `vrr`,
            because each tiny write becomes its own usb packet. whole-ish lines
            (24-byte pieces) echo correctly. (2) matched "ERR"/"OK" as a SUBSTRING of
            the response, but the console echoes the command back and a base64 payload
            contains those letters, so failures tracked the image data, not the link.
            (3) invented a "sequence resync" for a verb that image_probe had already
            shown is not sequential.
            the real cause, from finally capturing raw bytes instead of guessing:
              ERR :bao1x_hal::sh1107: timeout in draw (sh1107.rs:808)
              INFO:bao_video: resetting display spim block (bao-video/src/main.rs:1083)
            the OLED's SPI is timing out badge-side and bao-video is resetting the
            SPIM block. a good chunk answers a clean bare "OK"; a slow one produces
            that, and the retry cost is what made the upload crawl.
            so the protocol side is right now and the bottleneck is the panel driver.
```
