<!-- SPDX-FileCopyrightText: 2026 Julius Vitkauskas -->
<!-- SPDX-License-Identifier: CC0-1.0 -->
# Analyst B: final run-2 branch and call semantics

## Result

All **97 assigned forms match every recorded case**: the original 94 match
**1,128/1,128** cases in `hw/fm1-2026-10-24-v2/results.jsonl`; the follow-up covers
93 assigned forms and matches **433/433** cases. Together that is **1,561/1,561**
assigned cases. The follow-up also includes two `beqz` cases and 16 nop calibrations:
its entire **451/451** records match, across **95/95** tested forms.

`tools/hwtest/semantics/b2.py` now models `call.l`, `goto.l` and `call.xl` as well as
the original 94 forms. The original generator's wide-offset solver omitted those
three from run 2; the lead fixed it as 4c11712 and appended 12 generated cases each
to `hw/followup5-b-run.json`. This omission was a coverage gap, not hardware failure.
The four existing `basic2.py` models are unchanged. No inconsistent behavior was
found, and no further follow-ups are requested.

## Corrections and settled follow-up findings

The new evidence is `hw/fm1-2026-10-24-v2/followup5-b.jsonl`, with scratch patterns
in `hw/fm1-2026-10-24-v2/followup5-b.patterns.json`. The lead ran all 435 requested
cases plus 16 calibrations in eight batches, without a reset; calibration passed.
The original 399 probes settle the following points; the extra 36 establish the
previously omitted forms.

- **Calls save instruction address + 2 -> calls save the next instruction address,
  instruction address + instruction length.** The original `call.r` and `call.s`
  are 2 bytes long, so their earlier observations remain valid. All 12 `call.l`
  cases save `stub + 4`; all 12 `call.xl` cases save `stub + 6`. Every case takes
  its target. For example, `call.l` at 0x01c284c0 saves 0x01c284c4, and `call.xl`
  at 0x01c20310 saves 0x01c20316. No general register, sp or scratch changes.
- **Long jump offset base unspecified -> instruction end + byte offset.** All 12
  `goto.l` cases take the target and preserve `rets` and all other captured state.
  The long calls also use that offset base. These cases use displacement +4;
  they establish the base and effects without exercising displacement-range limits.
- **Six float forms had provisional NaN conditions -> all 20 float forms have
  direct NaN evidence.** Each form passes five probes: +0 versus -0, both orders
  of adjacent 0x3f800000/0x3f800001, quiet NaN on the left, and signaling NaN on the
  right. Ordered `eq/ge/lt/gt/le` reject both NaNs; `une/uge/ult/ugt/ule` accept
  both. This settles `bfge.rr`, `bfge.rr.l`, `bfle.rr`, `bfle.rr.l`, `bflt.rr.l`
  and `bfugt.rr`, whose clauses were previously family-based predictions. The
  notes now cite observed results without the pending-NaN hedges.
- **Adjacent integer boundaries unobserved -> strict/non-strict comparisons
  confirmed.** All 50 integer forms pass 0 and 2 against 1 (100 cases), alongside
  the original equality cases. Forty relational probes cross explicit sign or
  immediate-extension boundaries: 0x7fffffff/0x80000000, register 0 versus signed
  immediate -1, 0x7fffffff versus modified immediate 0x80000000, or 0xffffffff
  versus unsigned immediate 0. Unsuffixed relational forms compare unsigned
  32-bit values; `ifs` forms compare signed 32-bit values. Signed immediates are
  extended before comparison; modified immediates use their decoded value.
- **Partial `bc.*` truth tables -> complete truth tables.** The 76 follow-up cases
  fill every previously missing flag row. All ten forms now have observations for
  all 16 N/Z/C/V combinations, with the predicates below unchanged.
- **`ifs2ns.c/.s` unknown in the original table -> r0 bit-0 clear/set tests,
  independent of flags.** The 64 follow-up cases cross both bit states under all
  16 flags values for both encodings, also varying r0 bit 31. They confirm the
  round-1 interpretation despite the unusual oracle spelling.
- **`dbnz.r` zero-result/wraparound unobserved -> confirmed.** Input 0 becomes
  0xffffffff and branches; 1 becomes 0 and falls through; 2 becomes 1 and branches.
  All three preserve input flags 15. It decrements modulo 2^32 before testing.
- **Masked and zero tests with conflicting flags -> confirmed.** Twelve masked
  probes produce both zero and nonzero AND results while flags suggest the
  opposite outcome. Four `beqz`/`bnez` probes confirm they test the register
  directly, independently of input Z. All preserve flags. The earlier correction
  to `beqz` remains: an unpinned offset base is now instruction end + byte offset.

Earlier table corrections remain in place: unsigned signedness is explicit in
unsuffixed relational summaries, and previously unspecified float conditions and
inferred ARM-style flag names now have explicit hardware-supported predicates.
`rts` continues at `rets` and preserves the captured state.

## Flags and state

N Z C V are psr bits 3 2 1 0. The complete `bc.*` predicates are:

- `eq`: Z; `ne`: !Z; `cs`: C; `cc`: !C.
- `hi`: C && !Z; `ls`: !C || Z.
- `ge`: N == V; `lt`: N != V.
- `gt`: !Z && (N == V); `le`: Z || (N != V).

Every assigned case in both files preserves all four input flags, including float
and masked comparisons, calls and `dbnz.r`. No assigned form changes sp or scratch.
Only `dbnz.r` changes a general register; only calls change `rets`. Every assigned
conditional form has both taken and fall-through hardware observations.

The tested operand boundaries and NaN conditions are settled. The probes do not
exhaust every NaN payload/sign/operand-position combination, establish IEEE
exception behavior, or exercise backward/maximum-range branch displacements.
Those are scope limits, not outstanding requested follow-ups.

## Validation

- `python3 -m pi32v2isa check`: **1,165 entries, 0 problems**.
- `python3 -m unittest discover -s tests`: **120 tests, OK (13 skipped)**.
- Original results: **352/352 modeled entries match**; 1 of 353 tested entries
  lacks a model (outside this assignment).
- Run-2 results: **104/104 modeled entries match**; 222 of 326 tested entries
  lack models (outside this assignment); all 94 assigned forms present match.
- Follow-up results: **95/95 modeled entries match, 451 cases, no missing models**.
- `python3 tools/hwtest/gen.py /tmp/hw5-b --cases hw/followup5-b.json`:
  **399 cases build in seven batches**, plus 14 generated calibrations.
- Structural table audit against the previous commit: **96 entries changed**, only
  `notes` and `sources`; encodings, syntax, fields, examples, status and all other
  keys are unchanged. The new three forms now cite `hardware`.
- Combined coverage audit confirms all 97 assigned forms, both exits of every
  conditional form and every flag row for each `bc.*` predicate.
- `git diff --check` passes. The lead's `check.py` change loading named follow-up
  pattern files is retained. No hardware, ssh or generated run script was executed
  by this analyst, and no new follow-up cases were added.
