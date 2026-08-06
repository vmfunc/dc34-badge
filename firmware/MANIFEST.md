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
| _example.bin_ | `deadbeefcafe0000` | badge #1 | `picotool save -a` | 2026-08-06 | pre-anything baseline |

## rules

- **dump before you poke.** the first write you make is the one you cannot undo.
- one dump per state transition. baseline, post-challenge-1, post-brick. name them so the order is obvious: `01-baseline.bin`, `02-after-unlock.bin`.
- keep the *original* blob immutable. carve, patch and pad into `extracted/`, never in place.
- a dump with no hash and no date is a rumour.
