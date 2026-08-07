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

```
[thu 19:4x] ud2 logo LANDED. all 32 chunks accepted, "image accepted". the panel only
            redraws on the final chunk, so every earlier capped run was invisible by
            design rather than mis-packed.
[thu 19:5x] I WAS WRONG ABOUT THE FIRMWARE BEING PRIVATE. it is all public, under the
            `bunnie` org, which I never searched (I checked betrusted-io and baochip).
            https://defcon.org/34b/ lists everything:
              bunnie/dc34-console  the REPL, power, LED drivers  <- lightgenes lives here
              bunnie/dc34-vault    the vault app
              bunnie/dc34-api      shared api
              bunnie/dc34-image    OFFICIAL image upload tool (I reimplemented it)
              bunnie/dc34-bio      OFFICIAL bio upload tool (I reimplemented it too)
              ci.betrusted.io/releases/latest/baochip/dc34-badge/latest.zip
            hours of protocol reverse engineering that a single correct search would
            have skipped. lesson: when a vendor ships an open badge, find the vendor's
            own link page BEFORE reversing anything.
[thu 20:0x] LED colours: dc34-console/src/leds.rs shows the strip is 10 LEDs (18 on
            "uber" badges) on BIO pin 15, driven by a *genetics simulation*: haploid /
            diploid genes, meiosis, syngamy, mutation, `express`. badges breed light
            patterns with each other. that is the badge game.
            but every gene command (`test hue`, `test transmute`, `test autogamy`,
            `test mate`, `test rate`) is behind `#[cfg(feature = "qa-test")]` and is
            NOT in the shipped build. confirmed on the badge: all of them fall through
            to the usage string. so there is no stock console path to custom colours.
            changing them means building firmware, and building firmware means the
            dev key, which means erase_secrets, which means flag 1 is gone.
```

```
[thu 20:2x] DECISION, azzie's, explicit and informed: flag 1 is not worth keeping on
            this badge. she has no microscope, IRIS is the only route to it, and she
            would rather have a badge that is hers. so we build and flash custom
            firmware, which runs erase_secrets() first and destroys THE_FLAG_1
            permanently. recorded here because it is irreversible and the reasoning
            should outlive the conversation.
            the restore path still exists for the *stock* image:
            firmware/dumps/dc34-badge-latest.zip is vendor-signed and re-flashable.
            what cannot be restored is the FT-programmed slot 260 value.
[thu 20:3x] why the ud2 logo did not appear, from vendor/dc34-console/src/cmds/image.rs
            rather than guessing: on the 32nd chunk it writes the bitmap to the PDDB
            key DC34_IMAGE and pokes "_Vault2_" with scalar opcode 1024 arg1=1 to
            reload. so it is the *vault app's* stored image, shown on one of its
            pages, not a direct panel blit. it may well be stored correctly and simply
            not on the page azzie was looking at.
            separately my packing WAS wrong: the firmware assembles words with
            u32::from_be_bytes, so bytes are big-endian within each 32-bit word, while
            I packed little-endian. the fix is to reverse byte order within each
            4-byte group.
[thu 20:4x] custom firmware build plan. dc34-console's build.sh is:
              cargo build --release --target riscv32imac-unknown-xous-elf \
                --features board-baosec --features bao1x --features oem-baosec-lite \
                --features utralib/bao1x
            and `qa-test = []` is a real declared feature. building with it ADDS,
            from the vendor's own source and with no code written by us:
              test hue / transmute / mate / autogamy / rate   the LED gene commands
              test qrshow / qrget / cam / accel / temp / adc  camera, QR, sensors
            that is the cheapest possible custom firmware and it is what unlocks
            custom LED colours. riscv32imac-unknown-xous-elf is a tier-3 rust target,
            so it needs nightly + rust-src + -Z build-std.
```

```
[thu 21:0x] custom firmware build, the real recipe (from xous-core/xtask/src/main.rs):
              cargo xtask install-toolchain     installs the riscv32imac-unknown-xous-elf
                                                std properly; supersedes my -Z build-std guess
              cargo xtask baosec-lite [apps]    THE badge target. baosec_common() puts
                                                ticktimer/log/names/usb-bao1x/hal-service/
                                                modals/pddb/bao-video in flash, swapper in
                                                PID2, keystore in PID3, and every extra
                                                cratespec into the SWAP region.
            cratespec syntax: bare name = workspace-local crate; "name^ver" = crates.io;
            "name#url" = prebuilt; anything containing "/" = a prebuilt ELF on disk;
            "name~swap|flash|ram" pins the region.
            so an out-of-tree app like dc34-console can go in as a built ELF path,
            without adding it to the xous workspace.
[thu 21:1x] two build blockers, both resolved:
            (1) the vendored copy cannot build in place: dc34-console's Cargo.toml
                [patch] section redirects every xous dep to ../xous-core/<path>, so it
                needs xous-core as a SIBLING. build in ~/workspace, keep vendor/ pristine.
            (2) dc34-console needs keystore feature "owc-inc", which does NOT exist at
                the rev its Cargo.toml pins (616bf65) nor on origin/main. it exists only
                on **origin/dev**. the `rev` pin only binds unpatched deps; the [patch]
                paths expect a current dev checkout. xous-core now at 5d5bbbf (dev).
```

```
[thu 21:3x] image build got all the way to signing, twice, then died with a message
            that discards its own cause. patched swap_writer.rs:175 to surface it:
              "Can't sign swap image: SemVer::from_git: no major version"
            xous-create-image stamps a version derived from `git describe`, and my
            xous-core checkout is a SHALLOW DETACHED FETCH_HEAD with no tags, so
            describe has nothing to name. fix: `git tag v0.10.1` locally.
            worth noting the badge's own audit reports Semver v0.10.1-0-gbcfdca404,
            so the tag shape is real, not invented.
            also: --no-pq made no difference, which was the right experiment to rule
            out post-quantum signing as the cause before chasing keys further.
[thu 21:3x] the base image otherwise builds clean and lays out the exact process table
            the real badge reports: kernel, swapper PID2, keystore PID3, ticktimer,
            log, names, usb-bao1x, hal-service, modals, pddb, bao-video.
            xous std came prebuilt from betrusted's rust fork via
            `cargo xtask install-toolchain` (riscv32imac-unknown-xous 1.97.1), so no
            -Z build-std and no compiling std from source. my nightly detour was
            unnecessary.
```

```
[thu 21:5x] FULL IMAGE BUILDS. loader.uf2 353,280 bytes, byte-for-byte the same SIZE
            as the official release's loader.uf2, which is good evidence we are
            building the same thing. adding dc34-console as a cratespec grew swap.uf2
            from 24,576 to 780,800, so the prebuilt-ELF cratespec path works.
[thu 21:5x] and dc34-vault's README carries the OFFICIAL recipe, which I should have
            looked for before deriving my own:
              cargo xtask baosec-lite \
                ../dc34-console/target/riscv32imac-unknown-xous-elf/release/dc34-console~flash \
                ../dc34-vault/target/riscv32imac-unknown-xous-elf/release/dc34-vault \
                --no-timestamp --feature usb --kernel-feature debug-proc --no-verify
            note the console goes in **~flash**, not ~swap as I had it, and the vault
            takes the default region. also `cargo xtask install-toolkit`, not
            install-toolchain (they alias to the same arm).
[thu 21:5x] THE BADGE GAME, from that same README, and it is the real hack:
            light patterns are mixed between badges by scanning QR codes, and they are
            "encrypted using a common, shared key across the entire population - if you
            can extract that key, then you can effectively be a seeder for arbitrary
            light patterns". every badge starts with a limited colour range and the
            only sanctioned way to get more colours is to interact with someone who
            has them.
            so the intended *software* challenge is key extraction, and it is very
            likely where the second flag lives. worth returning to: it needs no
            microscope, unlike flag 1.
```

```
[thu 20:30] FLASHED. badge held in boot1 via PROG, volume mounted with
            `udisksctl mount -b /dev/sda1` (no root needed, polkit allows it for the
            seat user) at /run/media/quaver/BAOCHIP.
            wrote loader.uf2 (353,280), xous.uf2 (6,374,912), swap.uf2 (2,343,424),
            syncing after each. our build = the vendor's build plus dc34-console
            compiled with --features qa-test.
            THE_FLAG_1 is gone from this badge as of the first boot of this image:
            boot1 runs erase_secrets() on a dev-key-signed image before it executes.
            azzie's decision, made explicitly, recorded earlier.
            way back: ./tools/flash.sh firmware/dumps/dc34-badge-latest
```

```
[thu 20:4x] the badge is HERS now, confirmed on hardware: her card renders on the idle
            screen, the DEF CON logo is gone, and the developer-mode strip shows our
            text instead of "DEV MODE".
            tools/make_badge_art.py regenerates dc34-vault/src/bitmaps/dc_logo.rs from
            any image (pfp thresholded inside a circle, "vmfunc" set large, "it/its"
            beneath, sparkles in the corners); the stock bitmap is preserved next to it
            as dc_logo.rs.orig and a copy of the generated source lives in art/.
            thresholding over dithering was an experiment, not a guess: the pfp is flat
            pastel line art and error diffusion turned it to noise.
            and the feature gating was wrong in the plan above. src/cmds/test.rs has
            FIVE gates, not one, and `hue` (the LED colour command, the whole reason we
            built anything) is behind misc-test, not qa-test:
              misc-test  hue, autogamy, qrshow, qrget, cam, accel, adc, shipmode,
                         reset, wdt, wup
              qa-test    rate, transmute, bt, mate
            so the shipped build is --features qa-test --features misc-test. owc-test,
            hazardous-test and wfi-stress-test stay off deliberately: the first spends
            finite one-way counters and the last can hang the badge.
[thu 20:5x] one-line change in dc34-vault/src/ux.rs:875, the strip now reads "ud2.rip"
            rather than "ud2". image rebuilt and firmware/built restaged with fresh
            hashes. NOT YET FLASHED: the build actually running on the badge is the
            previous one, which says "ud2". costs one PROG hold whenever it is worth
            interrupting her for four characters.
[thu 20:5x] state at the close of day one, for whoever reads this at 04:00 on day three:
            flag 1 is gone from this badge and that was a choice, not an accident. the
            IRIS route is still the correct answer to that challenge, it just needs a
            badge nobody has flashed.
            the live challenge is flag 2, and it is NOT the lightgenes runtime for its
            own sake. from dc34-vault/README.md: light patterns are traded between
            badges by scanning QR codes, and the payloads are "encrypted using a common,
            shared key across the entire population - if you can extract that key, then
            you can effectively be a seeder for arbitrary light patterns". we now hold
            the full source of both ends of that exchange, plus a badge running our own
            build with qrshow/qrget/cam enabled. no microscope required. start there.
```
