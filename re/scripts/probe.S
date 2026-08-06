# BIO probe: prove a core is executing and find the queue "bio rx" drains.
#
# the console reported "DBG_Core1", so the queue it reads is likely fed by core 1,
# not core 0. the four cores start at different offsets in the 0xF00-byte BIO
# instruction space, so a 16-byte blob at offset 0 leaves cores 1..3 running zeros.
# fix: tile the whole space with the same block, so wherever a core starts it lands
# in a valid stream and loops.
#
# norvc keeps every instruction 4 bytes, so a core entering mid-block still lands on
# an instruction boundary rather than a misparsed compressed pair.
#
# x16..x19 alias FIFO0..FIFO3. writing them pushes toward the host.

.option norvc
.text
.globl _start
_start:
.rept 130
    li   a0, 0x0BADF00D
1:
    mv   x16, a0
    mv   x17, a0
    mv   x18, a0
    mv   x19, a0
    j    1b
.endr
