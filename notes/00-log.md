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
```

## fri

## sat

## sun
