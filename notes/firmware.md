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

- arch:
- base:
- endianness:

## interesting strings / symbols

`re/strings/` holds the raw output. the *interesting* ones get pulled up here with
a note on why they are interesting.

## crypto

anything that looks like a key, a nonce, or a checksum. name the algorithm before
you name the vulnerability.
