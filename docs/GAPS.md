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
  register-only ones (the `??` vector compares) reset the chip ([hw](../hw/fm1-2026-10-24/README.md));
  the branches also reset in run 4, while the unnamed `if` forms ran like AND-zero blocks in its operand grid.
- 16-bit words were swept completely; 32-bit and 48-bit second and third words outside E000-FFFF do not
  exist (every first word there is 16-bit).

## Meaning (behaviour)

Priorities from real code [fm1-firmware-stats]: one FM-1 factory firmware uses 562 of the table's forms; 97%
of its image decodes, and the undecodable words inside code are data (text, small constants), apart from one
that decodes only with `+instrev3`. Frequently used forms whose control or mode effects remain open include
`lockclr`, `lockset`, `callns.r`, `gotoss.xl` and `btbclr`; `cli.r`/`sti.r` now have hardware evidence for
their icfg-bit-9 effects (`shl3` and the 86 DSP forms it uses are also settled on hardware). M-VAVE's 016 package (2026-10-21)
gives the same picture: 598 forms used, all decoding as objdump does at `-mcpu=r3`; it uses the FPU far more
(5090 FPU instructions, `madd.f.rrr` 111 times, which JieLi's compiler never emits), and with `+instrev3` it
contains parallel twins of revision-3 forms that were then missing (`unpack4 ... #`, `sum(... *|*|*|* ...) #`; now in
the table). Both images now read the same with this repo's objdump as with JieLi's, with and without
`+instrev3`, apart from one block-nesting formatting quirk in 015.

`confirmed` covers encoding and syntax only. Behaviour comes from the compiler ([COMPILER.md](COMPILER.md),
source `compiler`) and from the FM-1 itself (source `hardware`): 774 of the 803 forms (parallel twins not
counted, 282 of which ran too) ran on the chip, every register-only form in [run 1](../hw/fm1-2026-10-24/README.md) and the memory,
stack, branch, call, jump, `rts` and special-register-read forms in [run 2](../hw/fm1-2026-10-24-v2/README.md), and the
`if` blocks, `rep` loops, table branches and parallel twins in [run 3](../hw/fm1-2026-10-24-v3/README.md), and
40 additional control, return, special-register and unnamed-block forms in [run 4](../hw/fm1-2026-10-24-v4/README.md).
Every non-parallel form has now been attempted. Run 5 adds successful `syscall`, `hbkpt` and `btbclr` captures with RAM handlers;
the other 29 have failure observations without results. Its six `iff.ne.rr.1`..`.6` forms match AND-nonzero
blocks on this chip (480 earlier cases and 48 distinguishing follow-ups).
Application interrupt-count relations are checked by `tools/hwtest/appverify.py`; exact timer counts
remain timing-dependent. Executable models of the settled numerical forms (`tools/hwtest/semantics/`)
match every modeled captured case, flags, memory,
`sp`, `rets` and the path taken included. The `psr` flags (N, Z, C, V in bits 3..0, and which forms write which)
are in [COMPILER.md](COMPILER.md), the special registers as read on the FM-1 in [ISA.md](ISA.md). Still open:

- Control effects still open: `callns.r` selects rets/reti/retx/rete by the encoded field low two bits
  in controlled [run-5](../hw/fm1-2026-10-24-v5/README.md) probes of all sixteen fields, with flags 0 and 15;
  its mode effects, mode changes of the return variants and
  `gotoss.xl`, icfg bits other than bits 8/9, event delivery/consumption, lock exclusion and barrier ordering.
  The rete-only pops and a multi-register `pop.srmask` sequence initially hung, then completed on a
  motherboard USB port; the earlier failures are not established as instruction traps. `hbkpt` hung
  again on that port, then reset in a final retry using the other RAM slot. [Run 4](../hw/fm1-2026-10-24-v4/README.md) separates captures from failures.
- RAM handlers in run 5 identify table entry 2 for `syscall` (reti/rti), entry 0 for `bkpt`/`hbkpt`
  (rete/rte works in both slots), and entry 1 for the delayed `btbclr` exception. Debug reti/rti handlers
  returned captures but following uploads hung; reaching the main instruction in those failed batches,
  including the earlier `swi 0` batch, is unproved. Fresh hooked `swi 0` completed without handler entry;
  `idle` reset. These download-mode observations did not configure delivery; the application runs below
  establish software requests/acknowledgement and a working idle wakeup. Other privilege/power modes and
  the branch-buffer effect of `btbclr` remain open.
- Application [steps 3–4](../hw/fm1-2026-10-24-app2/README.md) establish TIMER5 delivery gates at icfg
  bits 8 and 9, pending retention across both masks, and delivery at priorities 0/3/7. All eight `swi`
  numbers reached vectors 120..127. `idle` woke through TIMER5 without resetting. `btbclr` reached the
  exception handler with EMU_MSG bit 1 (illegal instruction); its advertised buffer effect remains open.
  Application [run app3](../hw/fm1-2026-10-24-app3/README.md) adds software pending retention through both
  global gates and priority nesting: a higher-priority software source preempts only when both gates are
  opened in the outer handler; equal/lower priority defers. The tested pairs and independent entry/exit
  traces are in the run report; other source/context combinations remain open.
  Synchronized timing shows WFE is nonblocking in the tested masked/unmasked application contexts,
  including 128 executions after SEVL or SEVG, while enabled IDLE waits for TIMER5. Masked IDLE reaches
  watchdog recovery with no result. A verified second core executes event and WFE commands after one
  startup, but no blocking WFE receiver was found, so event delivery/routing/consumption remains open.
  Per-batch second-core restarts were unreliable (13 ready-poll timeouts); the successful sequence avoids
  them. Other event-enable, power and interrupt configurations remain untested.
- Not tried: `rep` with a count of 0, a block or pair whose B is not a 16-bit load or store, nested blocks.
- `copex.ppi`: run 5 reproduces different mode-15 outputs after restoring all GPR inputs and flags,
  including the old destination, and inserting waits. Unobserved state/history remains unresolved
  ([run 5](../hw/fm1-2026-10-24-v5/README.md), earlier [report](../hw/report-q.md)). Application
  [run app3](../hw/fm1-2026-10-24-app3/README.md) repeats its entire eight-result sequence across two
  software-reset launches, but still varies among equal target inputs within each launch. No numerical
  model or hidden-state/reset rule follows from this reproducibility.
- Instruction revision 3 on this chip: it is not implemented as such. `popcnt.rr` does nothing, and the other
  revision-3 forms (`popcnt.r_pair`, `sat8.rr`, `vsat16`, `unpack4`, `sum` with `usat`/`ssat`/`msat`) behave
  exactly as an older form whose encoding differs by one selector bit. What they do on a revision-3 core is
  unknown.
- Forms that reset the chip: the unnamed (`??`) vector compares, the six `mem2.hh.i` multiplies,
  misaligned word loads, the tested canonical unnamed integer/floating branches, and the four non-round-tripping floating
  branch conditions (`!=`, `u==`, `uno`, `ord`). Run 4 also observed resets in both `btbclr` cases,
  `syscall`, `idle`, one of two `sevg` cases and the r7/r15 `callns` cases with flags 15. These are
  observations in the ROM runner, not proof of intrinsic traps. The `mem2.hh.rh` forms run as 16 x 32
  multiplies. The seven unnamed block forms ran like AND-zero blocks in the tested operand grid.
- The `.c` pushes store exactly what the plain pushes do; what `c` changes is unknown. `reti` and `usp` read
  values that stay fixed within a batch and differ between batches (ROM state, untested).
- A few edges no case reached: the 32-bit clamp of `madd.mul2.prhrhi.{ssat,usat}`; `ld.w.npc.r` with the
  instruction at 2 mod 4.

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
