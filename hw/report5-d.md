<!-- SPDX-FileCopyrightText: 2026 Julius Vitkauskas -->
<!-- SPDX-License-Identifier: CC0-1.0 -->
# Round 5 — analyst D, final

All **58 assigned forms match every one of their 701 hardware cases**, including flags, registers, scratch,
sp, rets and exit. The completed follow-up also matches **336/336 arithmetic cases across all 54
arithmetic forms**, plus **12/12 calibration nops** (55/55 modelled entries). Models are in
`tools/hwtest/semantics/d2.py`. Evidence is `results.jsonl`, `patterns.json`, `followup5-d.jsonl`,
`followup5-d.patterns.json` and `README.md` in `hw/fm1-2026-10-24-v2/`. No hardware or SSH commands
were run by this analyst.

## Corrections and newly settled meanings

Round 1 changed only `summary`, `notes` and `sources` in 58 assigned entries and the six reset entries.
This final round updates only `notes` in the 54 arithmetic entries. Encodings, syntax, examples,
requirements and status are unchanged.

- **24 `mul/madd/msub.mem1.{h,w}.{i,r}.{u,s}` forms:** previously “meaning not known beyond the syntax” →
  load at the original address, multiply the halfword or word by the full 32-bit register operand, and write
  the 64-bit product or accumulated result into the even/odd pair, low word first. `(s)` sign-extends each
  operand from its own width; `(u)` zero-extends it. Immediate displacements are signed, with the table's
  access-size scaling; register increments are byte displacements. Loads precede pointer updates.
- **24 `mul/madd/msub.mem2.{hw,ww}.{i,rh}.{u,s}` forms:** previously unknown → multiply the two original
  memory operands, 16 × 32 or 32 × 32 bits respectively, and write/accumulate the 64-bit result. Immediate
  increments use the table's signed, access-size scaling. For `.rh`, the increment register's **signed high
  halfword** updates the first pointer and its **signed low halfword** updates the second, both in bytes
  without access-size scaling. This includes observed first-pointer updates by -1 on word loads.
- **Six `mul/madd/msub.mem2.hh.rh.{u,s}` forms:** previously unknown, printed as two halfword loads →
  **execute as 16 × 32**, just like `.hw.rh`; the second load is a full word. All 72 original cases and
  36 follow-up cases match that model; all 72 original cases fail a 16 × 16 model. For example, `batch-mem-037` has
  `r1_r0 = h[r13 ++= r6.h]*h[r11 ++= r6.l] (u)`: the operands are `0x498c` and `0xbed31615`, and hardware
  returns `0x000036d28cbc107c`. Using only the second halfword would give `0x0658107c`.
- **Six `mul/madd/msub.mem2.hh.i.{u,s}` forms:** previously unknown → reset the FM-1 in every tested case,
  **including zero increments and aligned addresses**, as recorded in the run README. `.hw.i`, `.ww.i`
  and `.rh` two-memory-operand forms run. These six stay outside the model and follow-up cases;
  `gen.py` already excludes them through `RESETS`. No arithmetic or flag result can be inferred from a reset.
- **`flush`, `flushinv`, `iflush`, `pfetch`:** previously the cache effect was untested → recorded registers,
  flags, sp, rets and scratch remain unchanged and execution falls through. Their named cache effects still
  are not measured: this evidence does not establish cache-line size, invalidation/writeback details,
  ordering or timing. The models describe the recorded state, not a claim that the instructions are no-ops.

Arithmetic is modulo 2^64, with no saturation. Original inputs supply both the product and accumulator even
when operands overlap the destination. The pair write wins over a pointer update to the same register.
Two-memory cases sharing a base retain the **first pointer's increment**, rather than adding both
increments. Both multiplicands are loaded from the original address. The follow-up confirms these rules
for every arithmetic form with shared bases where applicable, either pointer overlapping the destination,
register multiplicand or increment overlaps with the destination where probed, and a pointer also serving
as a multiplicand. The `.rh` increment/result overlap also uses the original increment value.

## Flags and other state

The 18 multiply forms and four cache forms preserve **N/Z/C/V**. The 18 multiply-add forms replace only
**C** with the unsigned carry out of adding the product's 64-bit bit pattern to the old pair. The 18
multiply-subtract forms replace only **C** with **no borrow**, comparing the old pair against the product's
64-bit bit pattern. This applies to signed products too: a negative product is represented modulo 2^64
before carry/no-borrow is computed. All 36 accumulator forms preserve **N/Z/V**.

Every assigned case leaves sp, rets and observed scratch unchanged and falls through.

## Follow-up

`hw/followup5-d.json` contains **336 cases for the 54 arithmetic forms**:

- Seven per one-memory form (168): zero, -1, sign-bit and small register multiplicands; zero/all-ones
  accumulator boundaries; positive, negative and zero increments; a first halfword at scratch + 0x102;
  destination/pointer and destination/input overlaps; and the address register also serving as multiplicand.
- Five per immediate two-memory form (60): zero/all-ones accumulator boundaries, distinct signed increments,
  a halfword at +0x102 where applicable, one shared base with different increments, and each pointer
  overlapping one of the destination registers.
- Six per `.rh` two-memory form (108): the preceding memory/overlap probes, independent high/low signed
  increments (`0x0010fff8` and `0xfff00008`), and the increment register overlapping the destination pair.

The lead ran these as **six batches without a reset**, with calibration passing throughout. Results in
`hw/fm1-2026-10-24-v2/followup5-d.jsonl` contain 348 records including 12 nops, with scratch patterns in
`followup5-d.patterns.json`. All 54 arithmetic forms match all 336 follow-up cases without model changes.
The zero, -1 and sign-bit multiplicands and zero/all-ones accumulators confirm product extension,
modulo-64 wrap and carry/no-borrow behavior. First loads at scratch + 0x102 confirm halfword alignment;
independent positive/negative signed high/low-halfword increments confirm byte scaling, including when
the increment register overlaps the result pair. Shared bases and destination overlaps confirm the
original-input and write-precedence rules above. The repeated `.hh.rh` cases confirm the word-sized
second operand. The affected table notes now cite this follow-up and drop the settled overlap hedge.
No deliberate misalignment or reset form is included. Word loads start on word boundaries; halfword probes
are halfword-aligned. All loads and surviving pointer updates stay inside the scratch. The existing harness
cannot measure cache contents/timing, so no redundant cache probes are included. No further follow-ups
are proposed. Exact cache effects and the reset forms remain outside the returned-state evidence;
no follow-up result changes those limitations.

## Validation

- `python3 -m pi32v2isa check`: **1165 entries, 0 problems**.
- `python3 -m unittest discover -s tests`: **120 tests, OK (13 skipped)**.
- Run 1 `check.py`: **352/352 modelled entries** match; one tested entry remains unmodelled, unchanged.
- Run 2 `check.py`: **68/68 modelled entries** match, including **58/58 assigned forms (701/701 cases)**.
  The other 258 tested forms have no model in this analyst's checkout.
- Follow-up `check.py`: **55/55 modelled entries**, **348/348 cases** (336 arithmetic, 12 nops).
- `python3 tools/hwtest/gen.py /tmp/hw5-d --cases hw/followup5-d.json`: builds all **336 cases in six batches**.
  Offline model preflight validates scratch reads and surviving pointer bounds for every generated case.
- A parsed TOML comparison against round 1 verifies that only `notes` changed in the 54 arithmetic entries.
- The lead's `check.py` change loading adjacent `*.patterns.json` files is retained with the evidence.
