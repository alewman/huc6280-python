# Changelog

Releases are git tags; install one with
`pip install "huc6280-python @ git+https://github.com/alewman/huc6280-python@v0.3.0"`.
The package is not on PyPI (it depends on 6502-python by git commit).

## 0.3.0 (2026-11-12)

- **Behaviour change:** decimal `ADC` and `SBC` with an invalid BCD digit follow Mednafen's
  formulas by default (its changelog says they were corrected "per tests on a HuC6280");
  `decimal_formula = "mesen"` restores the previous results. Valid digits, binary mode, V, cycles
  and the T flag are unchanged ([issue 0004](docs/issues/0004-decimal-adc-sbc-mednafen-formulas.md)).
- Rung 5's bus comparison runs the core with the corpus's own decimal formula.
- **Provenance:** the decimal routines of the first version of this change (commits d575521 to
  9c47c98, never tagged) were transcriptions of Mednafen's (GPL-2.0) and Mesen2's (GPL-3.0) code.
  They are rewritten from a description in words, the test keeps only digests of the result
  tables, and the quoted code is gone from the issue; the results are bit-identical.
- `tools/mednafen-trace.patch` is marked GPL-2.0-or-later (it is a patch to Mednafen).

## 0.2.0 (2026-11-07)

- `irq_poll_cycle` (U25): where an instruction polls its interrupts, as a named switch; the
  default is unchanged ([issue 0003](docs/issues/0003-interrupt-sampling-point-and-the-covell-spread.md)).
- `HuC6280.opcode`: a public, read-only accessor for embedders.
- Rung 4b: Mednafen 1.32.1 as a second emulator referee (six games, 20.4 million instructions).

## 0.1.0 (2026-10-24)

- The core: rungs 0, 1, 1b, 2, 3, 4 and 5 ([docs/validation.md](docs/validation.md)).
- Block transfers read zero over `$0800-$17FF` ([issue 0001](docs/issues/0001-block-read-range-reaches-irq-registers.md)).
- An interrupt whose source has gone before its entry is dropped, `vanished_interrupt = "mesen2"`
  ([issue 0002](docs/issues/0002-interrupt-taken-after-its-source-is-gone.md)).
