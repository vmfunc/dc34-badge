# hardware

fill this the moment the badge is in hand, before any software.
photograph both sides at high res into `hw/` first, the silkscreen is the map.

## bill of materials

| ref | part | package | notes |
| --- | --- | --- | --- |
| U1 | ? | ? | main SoC, read the laser mark |

## test points / headers

| label | guess | confirmed | notes |
| --- | --- | --- | --- |
| TP? | ? | no | |

the order to identify things in, cheapest first:

1. read every laser mark and silkscreen label under a loupe. half the answer is printed.
2. continuity from suspect pads to SoC pins with the multimeter. no power needed.
3. scope/logic on boot: uart shouts, swd is silent, i2c/spi are periodic.
4. only then start probing actively.

## power

- input: usb-c / battery / ?
- notable rails, and what browns out first when you draw on them.

## radio

- antenna(s) on the board, and what band their length implies.
- see [rf.md](rf.md) for the actual capture work.

## debug interfaces

- **swd/jtag:** present? readout protection on?
- **uart:** which pads, what baud, does it drop a shell or just print?
- **usb:** what descriptor does it enumerate as. `lsusb -v` output goes here.
