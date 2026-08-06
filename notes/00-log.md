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
