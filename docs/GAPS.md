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

- Instruction revision 3: objdump shows some forms only with `-mattr=+instrev3`, and the sweeps above ran
  without it. A first-word sweep with it found `sat8` and `vsat16` (now in the table); a second-word sweep of
  every 32/48-bit first word with it is the remaining check.

- Forms objdump prints with `??` as the condition, and four floating-point conditions (`!=`, `u==`, `uno`,
  `ord`) the assembler does not round-trip: they are in the table with `asm_no_syntax`; whether the
  hardware treats them as instructions is unknown.
- 16-bit words were swept completely; 32-bit and 48-bit second and third words outside E000-FFFF do not
  exist (every first word there is 16-bit).

## Meaning (behaviour)

Priorities from real code [fm1-firmware-stats]: one FM-1 factory firmware uses 562 of the table's forms; 97%
of its image decodes, and the undecodable words inside code are data (text, small constants), apart from one
that decodes only with `+instrev3`. Forms it uses whose meaning is still open, most used first: `sti.r`,
`shl3.rri` (`<<<`, 514 uses), `lockclr`, `lockset`, `cli.r`, `callns.r`, `gotoss.xl`, `btbclr`, then 86 DSP forms
led by `smin`/`umin`/`smax`, halfword add/sub and saturating multiplies.

`confirmed` covers encoding and syntax only. The compiler showed what many instructions do (summaries and
notes cite `compiler`; [COMPILER.md](COMPILER.md)). Still open:

- Instructions the compiler never emits: `<<<` (`shl3`), `<c>` (`cycc`), the register-count `rep`, `ifs2ns`,
  `gotoss`, `ld.w.npc`, and the whole DSP/SIMD group (about 450 entries still say "meaning unknown").
- Edge cases: shift counts of 32 or more, divide by zero, `abs` of 0x80000000, NaN in `fmin`/`fmax`.
- Flags: which `psr` bits are sign, overflow and zero; which instructions write them.
- `callns`, `rtns`, `rtss`, `rthw`, `npc`, `sevl`, `sevg`, `wfe`, `trigger`, `cli R` / `sti R`; special
  registers `sr4`, `cnum`, `uspn`, `sspn`, `icfgn`, `icfgs`.
- Floating point: format (IEEE single assumed), rounding of the plain operations, exceptions.
- All of this needs tests on hardware (an FM-1 running small test programs) or other evidence.

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

- Which CPU models decode which forms: JieLi's objdump hides 91 floating-point forms (all `iff` blocks and
  `bf*` branches among them) unless given `-mcpu=r3` or `r4`, adds 6 with `-mcpu=r2`, and decodes 418 forms
  differently with `-mcpu=r1` ([OBJDUMP.md](OBJDUMP.md)). The table has no field for the CPU model yet; the
  lists are in `pi32v2isa/objdump.py`.
- Instruction revisions and newer CPU models, and which instructions each needs (`instrev3` so far).
- The other CPU models `r1`, `r2`, `r4`, `r5` and how they differ from `r3`.
