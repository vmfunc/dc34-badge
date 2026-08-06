# firmware

blob provenance lives in [firmware/MANIFEST.md](../firmware/MANIFEST.md). this file is
the *understanding*: what the image is, how it is laid out, what runs when.

## how it was obtained

which path worked, and which paths were tried and refused. the refusals matter, they
describe the protection.

## image layout

| offset | size | what | confidence |
| --- | --- | --- | --- |
| 0x0 | | | |

start with entropy: `binwalk -E` before `binwalk -e`. a flat high-entropy region is
encrypted or compressed, and which one it is changes everything downstream.

## load address / architecture

the single most common way to waste two hours is disassembling at the wrong base.
write the base address here the moment you are sure, and say *why* you are sure
(vector table pointing into a sane range, string cross-refs resolving, etc).

- arch: **rv32imac** (VexRiscv). the BIO coprocessor cores are PicoRV32, also rv32.
- base: read it out of the UF2 header rather than guessing, `tools/uf2.py info`.
- endianness: little.

ghidra handles RISC-V natively, pick the `RISCV:LE:32:RV32IC` variant and check that
compressed instructions decode, `c.*` mnemonics everywhere is the tell that the `c`
extension is being honoured.

xous is rust, so expect the rust symbol mangling (`_ZN...17h<hash>E`) and fat panic
strings carrying source paths. those paths are free structure, they tell you the crate
layout before you read a single instruction.

## interesting strings / symbols

`re/strings/` holds the raw output. the *interesting* ones get pulled up here with
a note on why they are interesting.

## crypto

anything that looks like a key, a nonce, or a checksum. name the algorithm before
you name the vulnerability.
