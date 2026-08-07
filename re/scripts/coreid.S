# which BIO cores actually run our uploaded code?
#
# `bio-sim/sw/include/bio.h` documents the full reserved-register map, which we had
# been half-guessing at:
#
#   x16..x19  FIFO0..3, pop on read, push on write
#   x20       wait_quantum (write zero)
#   x26       gpio mask          x27  event mask
#   x28       set event bits     x29  clear event bits
#   x30       event status       x31  core id in bits [31:30], aclk counter in [29:0]
#
# so x31 answers it directly. each tile computes its own core id and pushes it
# forever, on every queue. whatever comes back on `bio rx` names the core that is
# executing, and if several distinct values appear, several cores are running.
#
# event mask is cleared first so that reading the event register never halts, which
# is what the ws2812 reference does before it polls.

.option norvc
.text
.globl _start
_start:
.rept 100
    li   a2, 0
    mv   x27, a2              # set_event_mask(0): reads of x30 must not halt us
    mv   a0, x31              # [31:30] = core id, [29:0] = aclk counter
    srli a0, a0, 30           # keep just the core id
1:
    mv   x16, a0
    mv   x17, a0
    mv   x18, a0
    mv   x19, a0
    j    1b
.endr
