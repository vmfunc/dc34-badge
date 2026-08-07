# firmware manifest

the ledger. every blob in `dumps/` gets a row here **at dump time**, not later.
if a file is not in this table its provenance is gone and it is worthless as evidence.

record the hash before you touch the badge again, so a re-dump proves whether
you changed something.

```
sha256sum firmware/dumps/<file> | tee -a firmware/dumps/.sha256
```

| file | sha256 (first 16) | source | method | date | notes |
| --- | --- | --- | --- | --- | --- |
| `dc34-badge-latest.zip` | `17f0f4d08debe248` | ci.betrusted.io | official release download | 2026-08-06 | the shipping firmware, 3,316,160 B |
| `dc34-badge-latest/loader.uf2` | `916704a57f766b41` | ^ | unzip | 2026-08-06 | 353,280 B |
| `dc34-badge-latest/swap.uf2` | `54c400cb37da0a87` | ^ | unzip | 2026-08-06 | 2,343,424 B |
| `dc34-badge-latest/xous.uf2` | `098c2566b8e2fdd9` | ^ | unzip | 2026-08-06 | 6,358,528 B |

> [!wired] this is a *download*, not a dump
> the badge still cannot be read out. this is the vendor's own signed release, from
> `https://ci.betrusted.io/releases/latest/baochip/dc34-badge/latest.zip` (mirrored at
> `https://defcon.org/34b/latest.zip`). it is byte-identical to what ships, and it is
> signed with a key the badge accepts, which is exactly why re-flashing *this* is safe
> and flashing anything we build is not.

## rules

- **dump before you poke.** the first write you make is the one you cannot undo.
- one dump per state transition. baseline, post-challenge-1, post-brick. name them so the order is obvious: `01-baseline.bin`, `02-after-unlock.bin`.
- keep the *original* blob immutable. carve, patch and pad into `extracted/`, never in place.
- a dump with no hash and no date is a rumour.
