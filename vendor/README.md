# vendor

upstream source for the DEF CON 34 badge, vendored here so this repo builds and reads
offline at a con with no network. **none of this is my work.** it is copied verbatim,
`.git` stripped, at the commits recorded below.

every one of these is linked from the official badge page, <https://defcon.org/34b/>.

| directory | upstream | commit | what it is | licence |
| --- | --- | --- | --- | --- |
| `dc34-console/` | [bunnie/dc34-console](https://github.com/bunnie/dc34-console) | `bf64e03` | the REPL, power management, LED drivers. **`src/bio/lightgenes/` lives here** | none in tree |
| `dc34-vault/` | [bunnie/dc34-vault](https://github.com/bunnie/dc34-vault) | `3d5cbf7` | the badge app: vault, TOTP, FIDO, the UI that owns the panel | none in tree |
| `dc34-api/` | [bunnie/dc34-api](https://github.com/bunnie/dc34-api) | `617f0f3` | shared IPC types, opcodes, PDDB key names | none in tree |
| `dc34-image/` | [bunnie/dc34-image](https://github.com/bunnie/dc34-image) | `b0ffa9a` | **official** image upload tool | `LICENSE` in tree |
| `dc34-bio/` | [bunnie/dc34-bio](https://github.com/bunnie/dc34-bio) | `bc02395` | **official** BIO program upload tool | `LICENSE` in tree |
| `dc34-core-hw/` | [bunnie/dc34-core-hw](https://github.com/bunnie/dc34-core-hw) | `4cfabe5` | badge hardware design files | `LICENSE` in tree |

> [!wired] licence status, stated rather than assumed
> `dc34-image`, `dc34-bio` and `dc34-core-hw` carry their own `LICENSE` files, preserved
> as-is. `dc34-console`, `dc34-vault` and `dc34-api` ship **no licence file** at the
> commits above. they are published publicly by the author and linked from defcon.org,
> but "public" is not "licensed". keep this repo private, and if any of it is ever
> republished or built on for something public, ask bunnie first
> (`dc34@baochip.com`). that is a five minute email, not a blocker.

## the related repos, not vendored

these are large and equally public; clone them next to this repo rather than into it:

```
git clone https://github.com/betrusted-io/xous-core     # the OS, the HAL, bio-lib
git clone https://github.com/baochip/baochip-1x         # the SoC RTL and docs
git clone https://github.com/baochip/bio-sim            # BIO verilator harness + examples
git clone https://github.com/baochip/bio-loader         # BIO upload reference
```

## the shipping firmware

`../firmware/dumps/dc34-badge-latest.zip`, from
<https://ci.betrusted.io/releases/latest/baochip/dc34-badge/latest.zip>, hashed in
`../firmware/MANIFEST.md`. that is the vendor's signed build: `loader.uf2`, `swap.uf2`,
`xous.uf2`. it is the **restore path**, and the only image that carries a signature this
badge accepts without erasing its key slots.
