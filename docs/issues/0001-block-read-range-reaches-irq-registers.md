# 0001: block-transfer reads of `$1402`/`$1403` reach the interrupt registers

Raised 2026-10-24 by `pcengine-python` M1 (Aubrey asked for it to be raised on the core). Status: resolved 2026-10-24 (parenthesis reading adopted; see Resolution).

## What the core does

`src/huc6280/_block.py` returns 0 without asking the device for a block-transfer read of physical
`$1FE800`-`$1FF3FF` (hardware page `$0800`-`$13FF`; U7, C9). A block read of `$1400`-`$17FF`
reaches the board's callback like any read, so `$1402` (interrupt disable) and `$1403` (interrupt
status) are visible to a block transfer and the I/O buffer is loaded.

## What the source says (pcetech 2.0, tier 2, hardware-verified)

> When using any block transfer instruction to read addresses $0800 through $1400 in the I/O page,
> the value zero is always returned for every address, regardless of the CPU speed. (So you can't
> read the joystick port, timer, or IRQ registers) The I/O buffer is not changed either.
> (`reference/docs/pcetech.txt` lines 155-158)

The sentence disagrees with itself: the range ends at `$1400`, but the parenthesis names the IRQ
registers, which are `$1402`/`$1403`. The core took the stated range ending (`$13FF`, an off-by-one
of the stated `$1400`) and so contains neither the IRQ registers nor, under the literal reading,
`$1400` itself.

## Readings

| Reading | Range returning 0 | Basis |
| --- | --- | --- |
| core today | `$0800`-`$13FF` | the stated start, end one short of the stated `$1400` |
| literal | `$0800`-`$1400` | the stated range; `$1401`-`$1403` still reach devices |
| parenthesis | `$0800`-`$17FF` (the whole I/O-buffer region, the timer/port/IRQ registers) | "you can't read ... the IRQ registers" |

## Evidence from other sources

MAME and Mednafen read the device here (C9, emulator tier); neither follows pcetech. No hardware
capture settles the end of the range, and there is no judge here that exercises a block read of
`$1402`. Mark the choice **undecidable here**; the parenthesis is the only reading that makes the
sentence's own examples true.

## Proposed change (made)

1. Take the parenthesis: `HARDWARE_ZERO_END = 0x1FF7FF` (`$0800`-`$17FF`), keeping
   `block_reads_hardware_page_as_zero` as the single switch. VDC (`$0000`-`$03FF`) and VCE
   (`$0400`-`$07FF`) stay outside, as U7 already says.
2. Add a U/C entry for the end of the range, tier 2 with the contradiction stated.
3. Add a rung-3 directed test: a `TII` from `$1402`/`$1403` reads 0 and leaves the I/O buffer alone.
4. Re-certify: rungs 1, 1b and 4 must be unchanged (the corpus has no I/O page; the six MAME
   games should not block-read `$14xx`).
5. `pcengine-python` repins and reruns its gate; its test of block reads of `$0800`-`$13FF` extends
   to `$1402`.

Found by: `pcengine-python` `docs/m1-record.md`, "Core finding".

## Resolution

`HARDWARE_ZERO_END` is `0x1FF7FF` (`$0800`-`$17FF`); the switch is unchanged. U7 and C9 state the
range and the contradiction (C9 marks the end *undecidable here*). Rung 3 gained tests for
`$1402`/`$1403`/`$17FF` reading 0 without a device read, `$1800` reading the device, and the
switch off reading `$1402`. The I/O buffer itself is the board's, so the core's test checks only
that the device is not asked. Rungs 3 and 4 pass unchanged; `pcengine-python` still needs to
repin and extend its block-read test.
