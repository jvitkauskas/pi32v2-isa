# Gaps

What is known to exist but is not documented yet, roughly in the order it matters. When a gap is closed, move
the facts into the table or [ISA.md](ISA.md) and delete the line here.

## Encodings: done

Every word objdump decodes as an instruction's first word is in the table (`oracle coverage`: all five
regions complete), and all entries are confirmed against JieLi's objdump and assembler. Every
(first word, second word) pair was swept for E000-EFFF and F000-FFFF (with samples of third words for the
48-bit forms) and compared with the table's decoding; the sweep of F000-FFFF found ten long
compare-with-immediate branches whose first-word bit 5 had been taken as ignored, now split into a signed
form and a `.modimm` form ([audit](audits/2026-10-round2-coverage.md)).

Still open on the encoding side:

- Instruction revision 3 (done 2026-10-24): objdump shows some forms only with `-mattr=+instrev3`, and the
  earlier sweeps ran without it. Every 16-bit word, and every second word of every 32/48-bit first word, was
  swept with and without `+instrev3`; the forms that appear only with it (`sat8`, `vsat16`, `unpack4`, and the
  `(usat)`/`(ssat)`/`(msat)` modes of `sum(... *|*|*|* ...)`, with their parallel twins) are in the table with
  `decode_requires = ["instrev3"]`. Other CPU models (`-mcpu=r1`, `r2`, `r5`, the rev3 models) were not swept.

- Forms objdump prints with `??` as the condition, and four floating-point conditions (`!=`, `u==`, `uno`,
  `ord`) the assembler does not round-trip: they are in the table with `asm_no_syntax`. On the FM-1 the
  register-only ones (the `??` vector compares) reset the chip ([hw](../hw/fm1-2026-10-24/README.md)); the
  branch and `if` forms were not run.
- 16-bit words were swept completely; 32-bit and 48-bit second and third words outside E000-FFFF do not
  exist (every first word there is 16-bit).

## Meaning (behaviour)

Priorities from real code [fm1-firmware-stats]: one FM-1 factory firmware uses 562 of the table's forms; 97%
of its image decodes, and the undecodable words inside code are data (text, small constants), apart from one
that decodes only with `+instrev3`. Forms it uses whose meaning is still open, most used first: `sti.r`,
`lockclr`, `lockset`, `cli.r`, `callns.r`, `gotoss.xl`, `btbclr` (`shl3` and the 86 DSP forms it uses are now
settled on hardware). M-VAVE's 016 package (2026-10-21)
gives the same picture: 598 forms used, all decoding as objdump does at `-mcpu=r3`; it uses the FPU far more
(5090 FPU instructions, `madd.f.rrr` 111 times, which JieLi's compiler never emits), and with `+instrev3` it
contains parallel twins of revision-3 forms that were then missing (`unpack4 ... #`, `sum(... *|*|*|* ...) #`; now in
the table). Both images now read the same with this repo's objdump as with JieLi's, with and without
`+instrev3`, apart from one block-nesting formatting quirk in 015.

`confirmed` covers encoding and syntax only. Behaviour comes from the compiler ([COMPILER.md](COMPILER.md),
source `compiler`) and from the FM-1 itself (source `hardware`, [hw/fm1-2026-10-24](../hw/fm1-2026-10-24/README.md)):
every register-only form (353, including the FPU, division and the revision-3 forms) ran on the chip, and
executable models of all but `copex.ppi` (`tools/hwtest/semantics/`) match every case, flags included. The
`psr` flags (N, Z, C, V in bits 3..0, and which forms write which) are in [COMPILER.md](COMPILER.md). Still open:

- Forms the runner cannot run blind, so untested on hardware: memory, stack and `sp` forms, branches
  (including the flag branches `ifeq`..`ifle`, `bc.*`), `rep` and `if` blocks, parallel twins (`#`), special
  registers and the control forms `callns`, `rtns`, `rtss`, `rthw`, `npc`, `sevl`, `sevg`, `wfe`, `trigger`,
  `cli R` / `sti R`, `lockset` / `lockclr`; special registers `sr4`, `cnum`, `uspn`, `sspn`, `icfgn`, `icfgs`.
  They need a runner that sets up memory and control state.
- `copex.ppi`: depends on something besides its operands (identical inputs gave different results in mode
  15); internal state or history is suspected ([report](../hw/report-q.md)).
- Instruction revision 3 on this chip: it is not implemented as such. `popcnt.rr` does nothing, and the other
  revision-3 forms (`popcnt.r_pair`, `sat8.rr`, `vsat16`, `unpack4`, `sum` with `usat`/`ssat`/`msat`) behave
  exactly as an older form whose encoding differs by one selector bit. What they do on a revision-3 core is
  unknown.
- Unnamed (`??`) conditions of the vector compares reset the chip; the `??` branch and `if` forms were not run.
- A few edges no case reached: the 32-bit clamp of `madd.mul2.prhrhi.{ssat,usat}`.

## ABI and object files

- The C ABI is in [ABI.md](ABI.md); its §9 lists what it could not determine (alignment the linker
  guarantees, some bitfield combinations, other interrupt conventions).
- ELF: documented in [ELF.md](ELF.md) as JieLi's assembler writes it and its linker accepts it; debug
  sections (`-g`, `.cfi_*`, `.loc`) are not covered.

## Known toolchain bugs and quirks (keep)

- JieLi's assembler turns `r = r | 0`, `r = r ^ 0` and `r = r & 0xFFFFFFFF` into a set, toggle or clear of
  bit 0 (`asm_wrong` on `or.modimm.rri`, `xor.modimm.rri`, `and.nmodimm.rri`).
- It accepts `d[r++=n]` offsets only from -512 to 508, while objdump decodes -1024..1020 (`ld.d.pin.l`).
- objdump prints an empty register list as `{}`, which the assembler refuses.
- With a zero mask and a near target, the mask branch `if ((r & 0) == 0) goto` is assembled as the
  single-bit form testing bit 0 (`asm_wrong` on the FF60/FF61 entries).
- The compiler crashes on `__builtin_frame_address(0)` at -O0, -O2 and -Os ([ABI.md](ABI.md) §9).

## Known to exist, not needed yet

- Other CPU models: the table records which models' objdump shows each form (`absent_on`, `decode_requires`,
  [TABLE-FORMAT.md](TABLE-FORMAT.md#cpu-models)), but only `r3` was swept; what `r1` and `r5` decode in place of
  the 426 forms they lack, and anything the rev3 models add, is not in the table.
- Instruction revisions and newer CPU models, and which instructions each needs (`instrev3` so far).
- The other CPU models `r1`, `r2`, `r4`, `r5` and how they differ from `r3`.
