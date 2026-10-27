# AC79 SDK inline assembly compatibility (2026-10-26)

The assembler changes add spellings of existing confirmed entries, with no new instruction encoding.
The evidence is from black-box assembly/compilation with JieLi 20260730.1, `-target pi32v2 -mcpu=r3`.
No hardware was used. The table remains at 1165 entries.

## Forms

Every ID listed below already has status `confirmed`; every change is an assembler alias, not a new
entry. None requires an additional CPU feature. The generator still emits 4230 LLVM instructions.

Implicit `++`/`--` memory steps use the access size. Both operands of a memory multiply may independently
omit the step. The alias's fixed raw value is obtained from the table field's scale/range; there is no
encoding duplicated in the generator. Together with negation (`rsub.modimm.rri` and its parallel twin)
and `fabs` (`and.nmodimm.rri` and its parallel twin) and floating negation
(`xor.modimm.rri` and its parallel twin), the fixed-field aliases cover these 47 IDs:

- `and.nmodimm.rri`
- `and.nmodimm.rri.p`
- `ld.bs.pin.l`
- `ld.bu.pin`
- `ld.bu.pin.l`
- `ld.d.pin.l`
- `ld.hs.pin.l`
- `ld.hu.pin`
- `ld.hu.pin.l`
- `ld.w.pin`
- `ld.w.pin.l`
- `madd.mem1.h.i.s`
- `madd.mem1.h.i.u`
- `madd.mem1.w.i.s`
- `madd.mem1.w.i.u`
- `madd.mem2.hw.i.s`
- `madd.mem2.hw.i.u`
- `madd.mem2.ww.i.s`
- `madd.mem2.ww.i.u`
- `msub.mem1.h.i.s`
- `msub.mem1.h.i.u`
- `msub.mem1.w.i.s`
- `msub.mem1.w.i.u`
- `msub.mem2.hw.i.s`
- `msub.mem2.hw.i.u`
- `msub.mem2.ww.i.s`
- `msub.mem2.ww.i.u`
- `mul.mem1.h.i.s`
- `mul.mem1.h.i.u`
- `mul.mem1.w.i.s`
- `mul.mem1.w.i.u`
- `mul.mem2.hw.i.s`
- `mul.mem2.hw.i.u`
- `mul.mem2.ww.i.s`
- `mul.mem2.ww.i.u`
- `rsub.modimm.rri`
- `rsub.modimm.rri.p`
- `st.b.pin`
- `st.b.pin.l`
- `st.d.pin.l`
- `st.h.hi.pin.l`
- `st.h.pin`
- `st.h.pin.l`
- `st.w.pin`
- `st.w.pin.l`
- `xor.modimm.rri`
- `xor.modimm.rri.p`

`cmpu` is an alternative spelling of `cmp` for these 24 named vector forms (including parallel twins):

- `cmp.eq.ppp.v`
- `cmp.eq.ppp.v.p`
- `cmp.eq.rrr.v`
- `cmp.eq.rrr.v.p`
- `cmp.ge.ppp.v`
- `cmp.ge.ppp.v.p`
- `cmp.ge.rrr.v`
- `cmp.ge.rrr.v.p`
- `cmp.gt.ppp.v`
- `cmp.gt.ppp.v.p`
- `cmp.gt.rrr.v`
- `cmp.gt.rrr.v.p`
- `cmp.le.ppp.v`
- `cmp.le.ppp.v.p`
- `cmp.le.rrr.v`
- `cmp.le.rrr.v.p`
- `cmp.lt.ppp.v`
- `cmp.lt.ppp.v.p`
- `cmp.lt.rrr.v`
- `cmp.lt.rrr.v.p`
- `cmp.ne.ppp.v`
- `cmp.ne.ppp.v.p`
- `cmp.ne.rrr.v`
- `cmp.ne.rrr.v.p`

The re-sweep exposed further aliases: signed equality `ifs`, modifier order `(uavg,rnd)`, pair-to-word
`>>>` without `(s)`, and word compound `><=`. They cover these 68 existing confirmed IDs, with no
additional feature requirement:

- `add4.rrr.rnd.uavg`
- `add4.rrr.rnd.uavg.p`
- `addadd.rrhrhrhrh.rnd.uavg`
- `addadd.rrhrhrhrh.rnd.uavg.p`
- `addsub.rrhrhrhrh.rnd.uavg`
- `addsub.rrhrhrhrh.rnd.uavg.p`
- `beq.ri`
- `beq.ri.l`
- `beq.ri.l.modimm`
- `beq.rr`
- `beq.rr.l`
- `beqz`
- `bges.ri`
- `bges.ri.l`
- `bges.ri.l.modimm`
- `bges.rr`
- `bges.rr.l`
- `bgts.ri`
- `bgts.ri.l`
- `bgts.ri.l.modimm`
- `bgts.rr`
- `bgts.rr.l`
- `bles.ri`
- `bles.ri.l`
- `bles.ri.l.modimm`
- `bles.rr`
- `bles.rr.l`
- `blts.ri`
- `blts.ri.l`
- `blts.ri.l.modimm`
- `blts.rr`
- `blts.rr.l`
- `bne.ri`
- `bne.ri.l`
- `bne.ri.l.modimm`
- `bne.rr`
- `bne.rr.l`
- `bnez`
- `if.eq.ri.modimm`
- `if.eq.ri.s12`
- `if.eq.rr`
- `if.ne.ri.modimm`
- `if.ne.ri.s12`
- `if.ne.rr`
- `ifs.ge.ri.modimm`
- `ifs.ge.ri.s12`
- `ifs.ge.rr`
- `ifs.gt.ri.modimm`
- `ifs.gt.ri.s12`
- `ifs.gt.rr`
- `ifs.le.ri.modimm`
- `ifs.le.ri.s12`
- `ifs.le.rr`
- `ifs.lt.ri.modimm`
- `ifs.lt.ri.s12`
- `ifs.lt.rr`
- `lsr.s.rpi`
- `lsr.s.rpi.p`
- `lsr.s.rpr`
- `lsr.s.rpr.p`
- `subadd.rrhrhrhrh.rnd.uavg`
- `subadd.rrhrhrhrh.rnd.uavg.p`
- `subsub.rrhrhrhrh.rnd.uavg`
- `subsub.rrhrhrhrh.rnd.uavg.p`
- `xchg.rrr`
- `xchg.rrr.p`
- `xchg.rrr.sat`
- `xchg.rrr.sat.p`

Register-pair `.l`/`.h` normalization names the pair's low/high word. It makes, for example, a
64-bit asm output followed by `.h = r2` an ordinary `mov.rr`, and `.l = uextra(...)` an ordinary
`uextra.rrii`. Single-register `.l`/`.h` continues to mean a 16-bit halfword. Other apparent missing
forms in the initial sweep were resolved by assigning 64-bit `r` operands to pairs:

- `copex.ppi` (controls 11, 16, 22, 23 and others already supported by its field).
- `shiftr.rpi.mode` and `shiftr.rpr.mode` (including `(round)` and `(up)`).
- `xchg.rrr.sat` after pair-word normalization; pair shifts/saturation remain existing entries.
- `mul.s.prr`, `madd.s.prr`, memory multiplies and vector compares (all existing entries).

Decimal single-precision bit literals (`1.f`, `10.f`, also independently tested `1.5f`, `-1.f`) normalize
to integer bits and use existing constant-load selection (`li.modimm`/`li.u32` in the probes).
A `#` pair may occupy one source line, e.g. `r9 -= 1 # r4 = [r1++=4]`; it uses
`sub.modimm.rri.p` plus `ld.w.pin` and retains the existing block instruction counting.

`tests/asm/dropin-aliases.s` and the LLVM MC test contain 47 independently written probes, 52 instructions,
with expected encodings from the oracle. The Python live regression additionally checks every new alias
variant at both register extremes: 504 cases. The six `mem2.hh.i` entries reject implicit steps in the oracle and therefore gain no such alias. No claim about new DSP behavior is made.

## Constraints

See [ABI section 10](../ABI.md#10-inline-assembly-register-constraints) for the C probe and pressure
limits. Implemented register classes are `w` = r0..r7, `W` = r8..r15, `d` = four low-bank pairs,
`D` = four high-bank pairs; `r` chooses a word or aligned pair according to the operand width.
The lowering changes are confined to the inline-asm hooks, declarations, and pair-copy legalization at the
asm boundary. Untyped pair copies bridge legal i32 words to the pair register without making i64 arithmetic
a legal scalar type. The explicit register type supplied by an asm constraint also overrides LLVM’s
default count of two word registers for i64. Calls and byval lowering are untouched. Two register subclasses and
Clang constraint acceptance complete the implementation. The CodeGen tests cover bank pressure, inputs,
outputs, ties, short, float, and double operands. The oracle type matrix covers all five constraints,
five scalar types, and input/output/read-write uses (75 probes, including the four w/W double crashes).

## SDK scope and known failures

The selected set is the 66 `FAIL` records in `/tmp/bcsweep/results.txt` containing an unrecognised
instruction or constraint error. Extracted bitcode and investigation listings remain outside both repos.
JieLi's compiler itself accepts 64 and rejects 2; [GAPS](../GAPS.md#sdk-inline-assembly-rejected-by-the-oracle)
records the two members and independent reproductions. No encoding was invented for rejected lines.

## Validation

- `python3 -m pi32v2isa check`: 1165 entries, 0 problems.
- `python3 -m unittest discover -s tests`: 140 tests, 0 failures, 1 skipped (207.823 seconds). The skipped test is the opt-in full confirmation of every table entry
  (`PI32V2_LIVE_ALL`), not a failed or unavailable oracle test.
- Fresh `oracle confirm --write`: `rsub.modimm.rri` 1458 cases; `and.nmodimm.rri` 1458;
  `cmp.lt.ppp.v` 512; `copex.ppi` 504. All agree in both directions, allowing the checker's
  equivalent encodings selected by the oracle. Additional confirmations: `xor.modimm.rri` 1458; `lsr.s.rpi` 648;
  `add4.rrr.rnd.uavg` 4096; `xchg.rrr.sat` 4096; `if.eq.ri.modimm` 2592. Their encoding fields and
  recorded examples did not change.
- Alias live tests: 504 cases agree with the oracle. `tests/asm/dropin-aliases.s`: complete ELF object identical.

- `tools/llvm/check_mc.py`: disassembly 6093/6093; assembly 5478/5478.
- `llvm-lit` on CodeGen/PI32V2, MC/PI32V2 and MC/Disassembler/PI32V2: 14/14 pass.
  The new CodeGen cases also run the machine-instruction verifier and object emission.
- Re-sweep: 64/66 compile with `llc -O2 -filetype=obj`; 2 still fail for the oracle-rejected
  forms above. All 64 members the oracle compiles now compile with this build. `fast_corner.o` still
  reports the existing ignored `+cordic` feature warning; it compiles successfully.
- Per-line byte comparison using our allocated operands: 90/90 inline-asm lines agree with the oracle.
  Members: `libcompressor.a:compressor.o` (7), `lib_howling.a:noisegate.o` (30),
  `cpu.a:eq_design.c.o` (3), `cpu.a:math_fast_funtion.c.o` (50). No SDK listing is committed.

- The requested Release/assertions build completed with six Ninja jobs, including Clang and LLD.
  `llvm-lit` is a generated script rather than a Ninja target in this LLVM checkout; `llvm-config` and
  `llvm-readobj` were also built for validation.
- Clang frontend: 3/3 PI32V2 test RUN commands pass with FileCheck (`pi32v2-inline-asm.c`,
  `pi32v2-builtins.c`, `pi32v2-interrupt.c`). The new constraint C test also compiles to an object with
  `clang -target pi32v2 -mcpu=r3 -O2 -c`.
- Clang lit's generated configuration rejects the requested bare default triple `pi32v2` before test
  discovery (`Could not turn 'pi32v2' into Itanium ABI triple`). The three literal test RUN commands were
  executed directly with this build's Clang and FileCheck. The LLVM lit suites above run normally.

ISA live checks used `PI32V2_TOOLCHAIN` pointing at the parent checkout's 20260730.1 oracle. All LLVM
validation used `/root/work/wt-asm/build/bin`. Neither parent checkout nor `/root/src/build` was modified.
Nothing was pushed; no hardware or remote machines were used.

## Round 3: the four applications that stopped in the assembler (2026-10-27)

`demo_edr`, `demo_DevKitBoard`, `demo_audio` and `wifi_story_machine` compile `apps/common/jl_math/flfft_core_pi32v2.c`,
whose inline assembly has `if(%1 < 0){ ... }` and a `rep` block with an `iff` block inside it. The link reported
`unrecognised instruction or operand: if(r2<0)` (and `if(r2>254)`), then `Nested variants found in inline asm string`.

**The assembler was not at fault.** `if(r1<0){` / `if(r1>254){` / `ifs(...)` written with or without spaces, and `rep`
with a nested `iff`, are accepted and encode as JieLi's assembler does (`tests/asm/inline-blocks.s`, identical
object). The diagnostic prints the instruction with its blanks removed, and the block opener `{` was already gone:
clang turned each `{` of the asm string into `$(`, LLVM's marker for the start of an assembler-dialect variant
(`{a|b}`), which the asm printer consumes. The first block lost its brace (`if(r2 < 0)` alone is not an instruction)
and the second `$(` inside the `rep` block was a nested variant.

**What JieLi's compiler does** (clang 4.0.1, black box, `-S -emit-llvm`): `{`, `|` and `}` in an asm string are
copied into the IR string unchanged (`"rep $0 { $0 = [$1++=4] ... iff($0 > $1) { $0 = $1 } }"`), `$` becomes `$$`,
so a written `$(` is the literal text `$$(`, which its backend prints as `$(`. The SDK's own bitcode shows the same:
no inline-asm string in it contains `$(`, and the blocks have plain braces. Its backend copies the braces to the
assembly, nested ones included (`-S` of the string above shows `rep r1 {` and `iff(r1 > r0) { ... } }`). It also
rejects `%{`, `%|` and `%}` as invalid escapes (clang here accepts `%{` and `%}` as the characters; kept).

**The change** (LLVM fork, clang): `PI32V2TargetInfo` sets `NoAsmVariants`, the existing hook for targets whose
assembly has no dialects (AArch64, ARM, Hexagon, ...): `{`, `|`, `}` stay as written. The LLVM side needed nothing:
its asm printer treats a bare `{` as text, and `llc` assembles the SDK's bitcode with the braces.
`clang/test/CodeGen/pi32v2-inline-asm.c` checks the IR string; `llvm/test/MC/PI32V2/inline-blocks.s` and
`tests/asm/inline-blocks.s` keep the block spellings.

No assembler alias was needed, so the table (1165 entries) and the generated parser are unchanged. Validation, LLVM
`80c2ec816` (Release, assertions): `python3 -m pi32v2isa check` 1165 entries, 0 problems; `unittest discover` 152
tests OK (1 skipped, the opt-in full confirmation); `tools/llvm/check_mc.py` disassembly 6093/6093, assembly
5478/5478; `llvm-lit` CodeGen/PI32V2 13/13, MC/PI32V2 5/5, MC/Disassembler/PI32V2 1/1; the RUN lines of
`clang/test/CodeGen/pi32v2-*.c` (5 files, 6 runs) pass. `demo_edr`, `demo_audio`, `demo_DevKitBoard` and
`wifi_story_machine` link with the drop-in made from that build (sizes in [DROPIN.md](../DROPIN.md#builds-2026-10-26)).
