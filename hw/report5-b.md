<!-- SPDX-FileCopyrightText: 2026 Julius Vitkauskas -->
<!-- SPDX-License-Identifier: CC0-1.0 -->
# Analyst B: run-2 branch and call semantics

## Result

All **94 assigned forms match every one of their 1,128 recorded cases** in
`hw/fm1-2026-10-24-v2/results.jsonl`. `tools/hwtest/semantics/b2.py` models all 94,
including flags, registers, sp, rets, exit and scratch effects through the format-2
checker. The four existing `basic2.py` models are unchanged. The table has evidence
updates for the 94 forms plus notes/source updates for `beqz` and `rts`.

No inconsistent behavior was found. Models express the best reading of the recorded
cases; the specific gaps below remain pending hardware follow-up.

## Conditions and flags

- Integer `if` relational branches (`bge`, `blt`, `bgt`, `ble`, every assigned operand
  shape) compare **unsigned 32-bit** values. `ifs` (`bges`, `blts`, `bgts`, `bles`)
  compares **signed 32-bit** values. Neither comparison modifies psr.
- Equality/inequality compares all 32 bits. Signed immediate fields are sign-extended
  to 32 bits, unsigned fields zero-extended, and modified immediates decoded before
  comparison. Masked branches test `(register & register/mask) == 0` or `!= 0`.
- Float branches interpret register bits as binary32. Ordered `eq/ge/lt/gt/le` are
  false for unordered operands; `une/uge/ult/ugt/ule` include unordered. Existing
  NaN cases support that reading in 14 of the 20 forms. The other six have no NaN
  observations: `bfge.rr`, `bfge.rr.l`, `bfle.rr`, `bfle.rr.l`, `bflt.rr.l`,
  `bfugt.rr`. Their NaN behavior is a model prediction based on the condition family
  and compiler evidence, explicitly identified as pending in the table.
- `bc.eq`: Z; `bc.ne`: !Z; `bc.cs`: C; `bc.cc`: !C;
  `bc.hi`: C && !Z; `bc.ls`: !C || Z;
  `bc.ge`: N == V; `bc.lt`: N != V;
  `bc.gt`: !Z && (N == V); `bc.le`: Z || (N != V).
  Here **N Z C V are psr bits 3 2 1 0**. These are predicates of the supplied flags,
  without an implicit register comparison. The observations cover 84 of the 160
  possible form/flag combinations; follow-up fills the other 76.
- `beqz`/`bnez` test the register, not Z. `dbnz.r` decrements modulo 2^32, then tests
  the new register value; it preserves flags even though ordinary subtraction would
  update them. All twelve recorded `dbnz.r` counters take the branch, so the zero
  result and wraparound need explicit probes.

All 1,128 assigned cases preserve all four input flags, including float comparisons,
masked comparisons, calls, and `dbnz.r`. No assigned form changes sp or scratch.
Only `dbnz.r` changes a general register; only calls change rets. The existing
`beqz` and `rts` cases also preserve their flags and other state.

## Corrections and newly settled details

1. `ifs2ns.c`, `ifs2ns.s`: **unknown meaning -> r0 bit-0 clear/set tests**.
   The `(c)` encoding branches exactly when `(r0 & 1) == 0`; `(s)` exactly when
   `(r0 & 1) != 0`, each 12/12. Identical flags can produce opposite exits:
   `(c)` with flags 8 falls through for r0 = 0x40490fdb and branches for
   r0 = 0x1d7accf4; `(s)` with flags 0 falls through for r0 = 0x20 and branches
   for r0 = 0x55555555. These are operationally the fixed-r0, bit-0 cases in the
   bit-test encoding family, despite the oracle's unusual spelling. The wider
   meaning suggested by the name is not established. Follow-up crosses bit 0 with
   every flags value and varies the r0 sign, so the model is not silently justified
   by a flag correlation.
2. `call.r`, `call.s`: **unspecified return-address value -> instruction address + 2**,
   the first byte after the 2-byte call. Every call takes its target and writes
   `rets = st.end`, retaining all flags, registers, sp and scratch. For example,
   `call.r` at 0x01c28330 records rets = 0x01c28332, distinct from its target.
3. `beqz`: **offset base described as unpinned -> instruction end + byte offset**.
   This agrees with `docs/COMPILER.md`. All assigned relative branches/calls use
   this base; recorded branch displacements are +4 to the generated taken label.
   No claim is made that this run exercised long-range or backward displacement
   boundaries. Its existing executable model is unchanged.
4. `bc.*`: **names/ARM-style inference -> explicit tested N/Z/C/V predicates** above.
   The old ARM-style reading is consistent with every observation; it was incomplete
   as evidence and did not provide exact predicates in the summaries.
5. Unsuffixed relational compare branches: **summaries omitting signedness -> explicit
   unsigned comparison**. Signed `ifs` forms agree with their previous signed claim.
   Every integer form has 4..6 equality observations, but none has operands differing
   by exactly one. Equality evidence alone does not prove a strict/non-strict boundary.
6. `bf*`: **generic floating comparison / unspecified NaN behavior -> explicit ordered
   or unordered-inclusive binary32 condition**, supported by NaN observations in the
   14 forms identified above. The six untested NaN clauses remain explicitly
   provisional. Existing claims inferred from compiler output are now distinguished
   from direct hardware evidence. No IEEE exception or NaN-payload behavior is inferred.
7. All 96 edited entries cite `hardware` and `hw/fm1-2026-10-24-v2`, and state that
   N/Z/C/V are preserved. `goto.r`, `goto.s`, `bnez`, `rts`, ordinary/masked compares,
   and `dbnz.r` retain their previously stated value/control-flow meanings.

Only `summary`, `notes` and `sources` changed in `isa/pi32v2.toml`; a structural
comparison verified every other key against the original table. Encodings, syntax,
fields, examples and status are untouched, including the `ifs2ns` spelling/IDs.

## Requested follow-up

`hw/followup5-b.json` contains **399 cases**, built successfully with:

```
python3 tools/hwtest/gen.py /tmp/hw5-b --cases hw/followup5-b.json
```

The seven batches contain 399 requested cases for 91 forms, plus 14 generated nop
calibrations. No hardware, ssh, or generated run script was executed.

- **76** cases supply every missing `bc.*` flags value, completing all ten truth
  tables when combined with run 2.
- **64** cases test both r0-bit-0 states for both `ifs2ns` encodings under all 16
  flags values. Alternate flags rows also change r0 bit 31.
- **100** cases put 0 and 2 against 1 for every one of the 50 integer equality and
  relational forms. Existing cases provide equality; these add both immediate
  neighbors with deliberately conflicting flags.
- **40** cases put the relational forms across explicit signed/unsigned boundaries:
  register pairs 0x7fffffff/0x80000000; signed immediate -1 against register 0;
  modified immediate 0x80000000 against 0x7fffffff; unsigned immediate 0 against
  0xffffffff. These distinguish sign interpretation and immediate extension.
- **100** cases test each float form with +0/-0, the two orders of adjacent values
  0x3f800000/0x3f800001, quiet NaN on the left, and signaling NaN on the right.
  These cover the unobserved NaN predicates and important equality/order boundaries.
  They do not exhaust every NaN class, sign and operand-position cross-product.
- **12** masked cases deliberately produce zero/nonzero AND results with input
  flags suggesting the opposite outcome. Single-bit masks use bit 0; register and
  modified-immediate masks have value 1.
- **3** `dbnz.r` cases use 0, 1, 2 to check wraparound, falling through after decrement
  to zero, and the neighboring taken case while preserving flags = 15.
- **4** cases test zero/nonzero `beqz` and `bnez` against conflicting input Z flags.

No memory accesses, deliberate misalignment, or RESETS forms are requested. These
are requested inputs, not new hardware evidence; results must be checked before
claiming their boundaries fully settled.

## Validation

- `python3 -m pi32v2isa check`: **1,165 entries, 0 problems**.
- `python3 -m unittest discover -s tests`: **120 tests, OK (13 skipped)**.
- Original results: **352/352 modeled entries match**; 1 of 353 tested entries lacks
  a model (outside this assignment).
- Run-2 results: **104/104 modeled entries match**, including all 94 assigned forms;
  222 of 326 tested entries lack models (outside this assignment).
- Follow-up generation succeeds: **399 cases, 7 batches**.
- `git diff --check` succeeds.
- Follow-up audit: recorded exits plus predicted follow-up exits cover both outcomes
  of every assigned conditional form; combined original/follow-up bc flags cover
  all 16 input values for every form. Predictions are not hardware observations.
