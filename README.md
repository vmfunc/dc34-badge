# dc34 badge

def con 34 badge ctf. notes, dumps, tooling, solves.

everything here is written for one reader: me, at 04:00 on day three, having slept
four hours since tuesday. so it is blunt, it is timestamped, and it assumes past-me
was an unreliable narrator who wrote things down anyway.

---

## rules of engagement

these are self-imposed and they are not negotiable, because every one of them exists
because someone lost a badge or a day to breaking it.

1. **dump before you poke.** the first write is the one you cannot undo. `tools/dump-firmware.sh`
   exists so this takes ten seconds and no thinking.
2. **hash at dump time.** a blob with no hash and no date is a rumour, not evidence.
   `firmware/MANIFEST.md` is the ledger.
3. **passive before active.** receive before you transmit, read before you write, scope
   before you inject. this is a con floor, not a lab, and the RF is shared.
4. **failures go in the log.** a dead lead you wrote down is a lead you only walk once.
5. **no flags in git history before they're public.** if the CTF has a submission window,
   solves stay local until it closes. `git log -p` is forever.
6. **offline first.** the DC network is hostile by design and the wifi is a joke.
   the toolchain is pinned in `flake.lock` and pre-warmed before we fly.

---

## layout

```
notes/          the thinking. hand-written, append-only where it says so.
  00-log.md     running log, newest at bottom, timestamped. the spine.
  leads.md      hypothesis queue, ranked. dead leads kept, struck through.
  hardware.md   teardown: chips, test points, pinout, power, debug interfaces.
  firmware.md   image layout, load address, strings, crypto. the understanding.
  rf.md         bands, modulation, frame format, capture workflow.

firmware/
  MANIFEST.md   the ledger. every blob, hashed, dated, provenance stated.
  dumps/        raw images. committed when small, immutable once written.
  extracted/    binwalk output. gitignored, regenerable from the dump.

re/
  scripts/      loaders, parsers, openocd.cfg, ghidra headless scripts.
  ghidra/       project state. gitignored, merge-hostile, regenerable.
  strings/      raw strings/entropy dumps. the interesting ones get promoted to notes/.

captures/       logic/, rf/, uart/. gitignored (big), hashed in a sibling manifest.
hw/             photographs of the board. both sides, high res, before any rework.
solves/         one dir per challenge. _template/ is the shape.
tools/          host-side scripts. all of them safe to run half asleep.
docs/           the writeup, once there's something to write up.
```

### why captures are gitignored but dumps are not

a firmware dump is *evidence* and it is small (a few MB). it belongs in history so a
later diff can prove what changed. a logic or SDR capture is *observation*, it is
hundreds of MB, and it is worth exactly as much as the notes derived from it. so the
bytes stay local and the conclusions get committed. no git-lfs, because lfs needs a
network round trip to be useful and the whole point is that the network will not be there.

---

## the shell

nix flake, pinned, works on the framework (linux) and the mac.

```
nix develop            # everything below is on PATH
```

carries: radare2, ghidra, binwalk, yara · openocd, probe-rs, picotool, esptool, dfu-util ·
picocom, sigrok-cli, pulseview, flashrom · rtl-sdr, hackrf, inspectrum, urh ·
python with pwntools, pyserial, capstone, keystone, unicorn, pycryptodome.

**pre-warm before flying**, while there is still real bandwidth:

```
nix develop --profile ./.dc34-profile -c true
```

that materialises the whole closure and roots it against gc, so the shell opens
offline in the hotel with no network at all.

---

## workflow

```
./tools/dump-firmware.sh 01-baseline rp2040      # before anything else
./tools/serial-log.sh /dev/ttyACM0 115200        # leave running in a second pane
./tools/new-solve.sh rf-replay                   # scaffold a challenge dir
```

then, roughly:

1. photograph the board, both sides, into `hw/`. read the silkscreen and the laser marks.
2. dump. hash. write the manifest row.
3. `binwalk -E` for entropy before `binwalk -e` for extraction. flat and high means
   encrypted or compressed, and which one changes everything after it.
4. find the load address before you disassemble anything. wrong base is the classic
   two hours down the drain.
5. uart shouts on boot, swd is silent. listen first.
6. everything you learn goes in `notes/`, everything you try goes in `00-log.md`.

---

## badge facts

> filled in as they're confirmed. anything unconfirmed is marked as such, because a
> guess that hardens into an assumption is how you spend a day disassembling the
> wrong architecture.

- **soc:** unknown, badge not in hand yet
- **debug:** unknown
- **radio:** unknown
- **official CTF rules:** see below

---

## links

- def con badge, official: https://defcon.org/
- vault project note: `~/vault/projects/dc34-badge-ctf.md`

---

*not affiliated with the badge designers. everything here is my own work on my own badge.*
