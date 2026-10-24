# Gaps

What is known to exist but is not documented yet, roughly in the order it matters. When a gap is closed, move
the facts into the table or [ISA.md](ISA.md) and delete the line here.

## Encodings: nearly done

All 1017 entries are confirmed against JieLi's objdump and assembler. `oracle coverage` (first words, each
followed by zero words): 0000-1FFF 7200/7200, 2000-BFFF 37632/37888, C000-DFFF 2650/2650, E000-EFFF
2500/2500, F000-FFFF 2577/2671. Left:

- 256 words of `R += N` (2000-BFFF, `001.....11000...`): the assembler writes `r1 = r1 + n` for them.
- About 20 parallel twins (`F000`..`F7FF`) of region-C entries that were confirmed last, and two mask
  branches at `FF60`/`FF61`.
- Words objdump prints with `??` for the condition (`if (R ?? N) goto`, `if (R ?? R) {`, some vector
  compares): no assembler syntax produces them, so whether the hardware treats them as instructions is open.
- Four floating-point branch conditions (`!=`, `u==`, `uno`, `ord` at `FF44`..`FF47`) that objdump prints and
  the assembler does not round-trip.
- Second words: coverage counts first words. Region C's sweep of every second word matched objdump on all
  but 0.45% of pairs (the `??` forms); regions B and D were checked by `confirm` probes, not full sweeps.

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
- The compiler crashes on `__builtin_frame_address(0)` at -O0, -O2 and -Os ([ABI.md](ABI.md) §9).

## Known to exist, not needed yet

- Instruction revisions and newer CPU models, and which instructions each needs (`instrev3` so far).
- The other CPU models `r1`, `r2`, `r4`, `r5` and how they differ from `r3`.
