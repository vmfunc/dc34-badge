# peek, with a sync marker, to find out what a filtered load actually returns.
#
# the first version handed back exactly the address it was given, which has two very
# different explanations:
#   a) the load never executed and something echoed a0
#   b) the load executed against an unmapped/filtered address and the bus returned
#      the address phase value, which some AHB fabrics do
#
# so push a fixed marker first, then the loaded word. the host reads two values per
# request: 0x11111111 proves this block ran to completion, and whatever follows is
# genuinely what lw produced.

.option norvc
.text
.globl _start
_start:
.rept 130
1:
    mv   a0, x16              # address from host
    lw   a1, 0(a0)            # the read under test
    li   a2, 0x11111111       # marker: this block completed
    mv   x16, a2
    mv   x16, a1
    j    1b
.endr
