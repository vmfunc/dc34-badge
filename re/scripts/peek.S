# arbitrary-address peek primitive on a BIO core.
#
# protocol: host pushes a 32-bit address with "bio tx <addr>", the core loads that
# word over the BDMA path and pushes it back, host collects it with "bio rx".
#
#   bio tx 0x603E2080   ->   bio rx   ->   the first word of RRAM data slot 260
#
# whether the load actually completes depends on the BDMA whitelist. an address
# outside every configured window is filtered, and the expected symptom is the core
# stalling or the queue staying empty rather than a wrong value coming back. that
# distinction is the whole experiment.
#
# x16 aliases FIFO0. tiled across the instruction space because the four cores start
# at different offsets; norvc keeps every instruction 4 bytes wide so a core entering
# mid-block still lands on an instruction boundary.

.option norvc
.text
.globl _start
_start:
.rept 200
1:
    mv   a0, x16              # address from the host; core halts here until sent
    lw   a1, 0(a0)            # the read under test
    mv   x16, a1              # hand the word back
    j    1b
.endr
