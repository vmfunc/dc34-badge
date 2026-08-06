# is a BIO core actually in the tx/rx data path?
#
# "bio tx <v>" then "bio rx" already round-trips v unchanged, which proves the host
# FIFO plumbing but not that any core executes. so: pop a word, add one, push it
# back. if "bio tx 1" then "bio rx" yields 2, a core is running our code and we have
# a bidirectional channel. if it yields 1, the cores are idle and the round trip was
# just the host talking to itself.
#
# pushes to all four queues so it does not matter which one "bio rx" drains.
# tiled across the instruction space because the four cores start at different
# offsets. norvc keeps every instruction 4 bytes wide.

.option norvc
.text
.globl _start
_start:
.rept 130
1:
    mv   a0, x16              # pop FIFO0, core halts here until the host sends
    addi a0, a0, 1
    mv   x16, a0
    mv   x17, a0
    mv   x18, a0
    mv   x19, a0
    j    1b
.endr
