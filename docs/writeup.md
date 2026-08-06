# dc34 badge .. writeup

> draft. nothing here goes public until the CTF closes.

write this *as you go*, not after. the version written on sunday from memory is
always worse than the one assembled from `notes/00-log.md` in real time.

## the badge

what it is, what it does, what the CTF asked of you. one paragraph, no suspense.

## getting the firmware off

the path that worked, and the ones that did not. the refusals are the interesting
part: they describe the protection model.

## the target

architecture, load address, layout, and how each was established. "the vector table
at 0x0 pointed into 0x10000000-ish and the string xrefs resolved" is a reason.
"ghidra said so" is not.

## the bug

mechanism first, exploit second. if the mechanism does not fit in a paragraph you
have not finished understanding it.

## the solve

link the script in `solves/<name>/`. it should run from a clean checkout inside
`nix develop`, against a badge in a stated starting state. if it needs a human to
press a button, the script says so and waits.

## what i would do differently

the honest section. the two hours lost to the wrong base address, the lead walked
twice because it was not written down. this is the part future-me actually reads.

## credit

anyone who handed you a probe, a hint, or a spare badge. name them.
