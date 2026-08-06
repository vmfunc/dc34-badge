# address-space oracle.
#
# per the RTL (bio_bdma.sv:2576) an out-of-window read is redirected to `gutter`,
# which resets to 0x00000000. nothing answers at 0, so the AXI read never completes
# and the core waits on it forever. that makes the hang a clean one-bit oracle.
#
# the marker is pushed BEFORE the load, which is the whole trick: it separates
#   "core took the address, then hung on the read"   -> marker, then silence  -> FILTERED
#   "core took the address and the read returned"    -> marker, then a value  -> ALLOWED
#   "core was already dead"                          -> nothing at all
# without the marker those first and third cases look identical.

.option norvc
.text
.globl _start
_start:
.rept 130
1:
    mv   a0, x16              # address from host
    li   a2, 0x11111111       # marker: address received, about to attempt the read
    mv   x16, a2
    lw   a1, 0(a0)            # hangs forever if this page is outside every window
    mv   x16, a1              # only reached when the read retired
    j    1b
.endr
