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

- Forms objdump prints with `??` as the condition, and four floating-point conditions (`!=`, `u==`, `uno`,
  `ord`) the assembler does not round-trip: they are in the table with `asm_no_syntax`; whether the
  hardware treats them as instructions is unknown.
- 16-bit words were swept completely; 32-bit and 48-bit second and third words outside E000-FFFF do not
  exist (every first word there is 16-bit).

## Meaning (behaviour)

`confirmed` covers encoding and syntax only. Unknown or unverified:

- `<<<` and `>>>`: the compiler uses `>>>` for a signed `>>` (an arithmetic shift); `<<<` not yet seen.
- `callns`, `rtns`, `rtss`, `rthw`, `ifs2ns`, `gotoss`, `npc`: look like secure/non-secure state handling
  (ARMv8-M style); unknown.
- `sevl`, `sevg`, `wfe`, `lockset`, `lockclr`, `testset`, `trigger`, `cli R` / `sti R`; special registers
  `sr4`, `cnum`, `uspn`, `sspn`, `icfgn`, `icfgs`.
- Floating point: format (IEEE single assumed), rounding of the plain operations, fused or not, exceptions.
- DSP: saturation and averaging details, `(x2)`, `(rnd,...)`, lane order.
- What a branch offset is relative to; what `if (...) {` blocks cover; parallel-issue pairing rules.
- Flags: which instructions set `cc` and the flags `ifeq`..`ifle` test.

## ABI and object files

- The C ABI is in [ABI.md](ABI.md); its §9 lists what it could not determine (alignment the linker
  guarantees, some bitfield combinations, other interrupt conventions).
- ELF: relocation types beyond `MOV_ABS32` and `LONG_JUMP_23M2`, their numbers and fields, `e_flags`,
  section and symbol conventions.

## Known toolchain bugs and quirks (keep)

- JieLi's assembler turns `r = r | 0`, `r = r ^ 0` and `r = r & 0xFFFFFFFF` into a set, toggle or clear of
  bit 0 (`asm_wrong` on `or.modimm.rri`, `xor.modimm.rri`, `and.nmodimm.rri`).
- It accepts `d[r++=n]` offsets only from -512 to 508, while objdump decodes -1024..1020 (`ld.d.pin.l`).
- objdump prints an empty register list as `{}`, which the assembler refuses.
- With a zero mask and a near target, the mask branch `if ((r & 0) == 0) goto` is assembled as the
  single-bit form testing bit 0 (`asm_wrong` on the FF60/FF61 entries).
- The compiler crashes on `__builtin_frame_address(0)` at -O0, -O2 and -Os ([ABI.md](ABI.md) §9).

## Known to exist, not needed yet

- Instruction revisions and newer CPU models, and which instructions each needs (`instrev3` so far).
- The other CPU models `r1`, `r2`, `r4`, `r5` and how they differ from `r3`.
