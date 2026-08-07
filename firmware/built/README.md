# built

custom firmware for the badge, built from the vendored sources.

| file | bytes | official | note |
| --- | --- | --- | --- |
| `loader.uf2` | 353,280 | 353,280 | identical size |
| `swap.uf2` | 2,343,424 | 2,343,424 | identical size |
| `xous.uf2` | 6,374,912 | 6,358,528 | +16,384, our `qa-test` code |

built with the official recipe from `dc34-vault/README.md`, from inside `xous-core`
(on `dev`, tagged `v0.10.1` so the signer can derive a semver):

```
cargo xtask baosec-lite \
  ../dc34-console/target/riscv32imac-unknown-xous-elf/release/dc34-console~flash \
  ../dc34-vault/target/riscv32imac-unknown-xous-elf/release/dc34-vault \
  --no-timestamp --feature usb --kernel-feature debug-proc --no-verify
```

the one deviation from stock: `dc34-console` is built with **`--features qa-test`**,
which compiles in the vendor's own commands that the shipped build omits:

- `test hue`, `test transmute`, `test mate`, `test autogamy`, `test rate` .. the LED
  gene controls, which is what makes custom colours possible at all
- `test qrshow`, `test qrget`, `test cam`, `test accel`, `test temp`, `test adc`

signed with `devkey/dev.key`, so **boot1 will run `erase_secrets()` before this
image executes** and wipe `KEY_SLOTS`, including `THE_FLAG_1`. that is understood and
accepted; see `notes/the-flag.md`.

to flash: hold `PROG` while plugging in, then `./tools/flash.sh firmware/built`.
to go back: `./tools/flash.sh firmware/dumps/dc34-badge-latest`.
