<!-- SPDX-FileCopyrightText: 2026 Julius Vitkauskas -->
<!-- SPDX-License-Identifier: CC0-1.0 -->

# Analyst S, round 2: floating point and division

Worktree `s`, branch `hw/s`. All **29 assigned forms match 748/748 measured
cases, including all low four psr bits**: 348 in
`hw/fm1-2026-10-24/results.jsonl`, 400 in
`hw/fm1-2026-10-24/followup-s.jsonl`. The latter contains exactly the original
`hw/followup-s.json` cases, reordered by the split run, plus 16 calibration
nops. There are no unexplained register or flag changes. No hardware or ssh
commands were run from this worktree.

Round 1 (`e54bab1`) matched the original 348 cases but left midpoint rounding,
fusion, most special values and integer division edges provisional. Round 2
changes six executable models: `fmin`, `fmax`, `ftof.half`, `ftof.full`,
`madd.f`, `msub.f`. The other 23 models already predict all new measurements.
All 29 entries' summary/notes now cite the follow-up evidence and remove the
settled uncertainties. Only summary/notes/sources of assigned entries may
change; encodings, syntax, fields, examples and status are untouched.

## Rounding, infinities and subnormals

- `add.f`, `sub.f`, `mul.f`: nearest with ties to even. The follow-up exercises
  both midpoint parities; add/sub also exercise both signs. For example,
  `1 + 2^-24` rounds to 1, while `(1+2^-23) + 2^-24` rounds upward to the next
  even significand. Psr survives.
- `div.f`: exact-rational nearest-even models match both runs, including
  underflow ties: raw `0x00000001 / 2` -> 0,
  `0x00000003 / 2` -> `0x00000002`. Nonzero finite / signed zero gives the
  XOR-signed infinity without trapping; finite/infinity gives signed zero;
  finite overflow gives signed infinity. Normal finite quotients also match
  nearest-even. No separate FPU control/rounding mode was varied in this run.
- Arithmetic does **not** flush subnormal inputs or outputs in these runs.
  Add: minimum subnormal + itself -> raw 2. Subtract: minimum normal minus
  minimum subnormal -> maximum subnormal. Multiply/divide by 1 preserve both
  minimum and maximum subnormals. Underflow midpoint cases show gradual
  underflow with rounding, rather than unconditional flush-to-zero.
- `madd.f`/`msub.f` are **not fused**: first round the product to binary32,
  then perform a binary32 add/subtract, both nearest-even. Sources
  `0x3f800001` and `0x3f7ffffe` multiply exactly to `1 - 2^-46`.
  With accumulator -1, `madd` gives +0 (fused: `-2^-46`); with accumulator
  +1, `msub` gives +0 (fused: `+2^-46`). Maximum finite * 2 with a cancelling
  maximum-finite accumulator gives signed infinity, confirming intermediate
  product overflow. Minimum subnormal * 0.5 with a minimum-subnormal
  accumulator gives raw 1, confirming product underflow rounds before
  accumulation. Original cases also retain subnormal contributions/results.
- `itof`/`utof`: nearest with ties to even, now tested with 16777217 ->
  16777216 and 16777219 -> 16777220; signed conversion also tests the
  corresponding negative midpoints. Integer endpoints round as modelled.
- `ftof.even`/`ftoi.even`/`ftou.even`: nearest with ties to even, settled by
  2.5 -> 2 and 3.5 -> 4, plus negative ties where applicable. The `trunc`,
  `ceil`, `floor` suffixes mean toward zero, plus infinity, minus infinity.
  Integer-valued `ftof` retains zero's sign and passes signed infinities.
  Positive minimum subnormal -> 1 under ceil; negative minimum subnormal ->
  -1 under signed floor. These distinguish conversion from input flushing.
- `ftoi`, all four modes: clamp the rounded integer to
  [-2147483648, 2147483647]. Positive NaN/infinity -> `0x7fffffff`, negative
  NaN/infinity -> `0x80000000`. `ftou`, all four modes: clamp to
  [0, 4294967295]; negative values/NaN/infinity -> 0, positive overflow/NaN/
  infinity -> `0xffffffff`. Follow-up tests both exceptional signs and the
  last representable float below each positive range limit. All preserve psr.
- `ftof.half`: binary32 -> binary16, nearest with ties to even; only rd's low
  half changes. Finite normal midpoint parities now distinguish the mode.
  65504 -> half maximum finite, 65520 -> infinity; `2^-24` -> half subnormal
  1, `2^-25` -> zero. `ftof.full`: exact expansion of source low binary16,
  ignoring its high half, including half subnormals. Both preserve signed
  zero/infinity and psr. Half subnormals expand to normal binary32 values;
  this is separate from binary32 arithmetic's gradual underflow evidence.

## NaNs, signed zeros and comparisons

Arithmetic NaN inputs in either source, and in the multiply-accumulate
accumulator, give **positive `0x7f800001`**, discarding payload/sign. Invalid
combinations give that same value: opposite infinities added, like infinities
subtracted, zero * infinity, 0/0, infinity/infinity, and the tested invalid
multiply-accumulate combinations. This bit pattern conventionally represents
a signalling NaN; none of these cases trapped. It is a measured result, not
evidence of a general exception-status mechanism.

The four integer-valued `ftof` modes instead canonicalize measured NaNs to
**sign-preserving quiet `0x7fc00000`**. Integer conversions use the
sign-selected saturation endpoints above. Half/full conversion discards
payload but distinguishes measured quiet/signalling classes: quiet NaNs give
signed half `0x7e00` / full `0x7fc00000`, while negative signalling sources
`0xff812345` / half `0xfc55` give **`0xfc01` / `0xff800001`**. The round-1
all-quiet-canonical prediction for these two forms was wrong. The model
generalizes class preservation to positive signalling NaNs, which have not
yet been measured; follow-up S2 tests that exact remaining gap.

`fmin`/`fmax` choose the numeric operand if exactly one source is NaN,
regardless of operand order or the two measured NaN classes/signs. With two
NaNs they copy the second source **unchanged**, including payload/sign/class.
Opposite signed zeros select **-0 for min, +0 for max**, in either order.
These replace the provisional second-source-on-every-tie/unordered model.
Infinities order normally and signed subnormals compare without flushing.

`fcmp`, `fmin`, `fmax` replace low psr with less **8**, equal **6**, greater
**2**, unordered **3**. Min/max flags describe source comparison even when a
numeric operand is selected from an unordered pair. Both signed zeros compare
equal. `fcmp` now exercises each outcome with incoming flags 0 and 15, proving
replacement rather than partial preservation, and writes no register. All
other assigned float forms preserve all four low bits. Upper psr bits read
zero in both files; upper input bits were not set by this experiment.

## Integer division and flags

All four integer divides return **zero for a zero divisor**, for every
sampled dividend: zero, one, all-ones, sign bit and 32-bit boundaries. Each
form has six zero-divisor cases. None hung or trapped. Signed
**INT32_MIN / -1 -> `0x80000000`**, **INT64_MIN / -1 ->
`0x8000000000000000`**, wrapping the quotient to the destination width.
Ordinary signed quotients truncate toward zero.

The `rrr` forms return only a 32-bit quotient; bits 0..1 of psr survive,
bit 2 is quotient == 0, bit 3 is quotient bit 31. The unsigned bit-3 rule is
now measured with quotients `0x80000000` and `0xffffffff`. For divide by
zero the output flags are `(flags_in & 3) | 4`; signed overflow preserves
bits 0..1, sets bit 3, clears bit 2.

The `ppr` forms return the **full 64-bit quotient**, low word in the even
register and high word in the odd, and preserve all four psr bits even for
division by zero and signed overflow. **None of the assigned division forms
returns a remainder**; no non-destination register changed. In particular,
the odd pair destination is the high quotient word, not a remainder. The
compiler's separate multiply/subtract remainder sequence remains a separate
operation, not an additional output of these forms.

## Remaining hardware request

`hw/followup-s2.json` contains **208 cases on 23 float forms**, not yet run.
No additional integer division cases are needed for the questions in this
round. S2 targets residual NaN coverage gaps:

- Cases 1..16: half/full conversion, both signs and quiet/signalling classes
  at minimal/maximal payloads. Positive signalling NaNs are the main missing
  evidence for the revised canonical-class model.
- 17..64: all twelve integer/float rounding forms, positive signalling and
  negative quiet NaNs with different payloads. Existing follow-ups pair
  positive quiet with negative signalling, so sign/class effects are partly
  confounded for exceptional conversion endpoints.
- 65..120: all six arithmetic forms, the same missing NaN sign/classes in
  each operand and the accumulator where applicable.
- 121..176: min/max with both signs/classes in either position and all
  two-NaN combinations, plus differing payloads within the same class/sign.
  This tests raw second-source preservation beyond existing mixed-class pairs.
- 177..196: comparisons across those NaN classes/signs.
- 197..208: invalid/overflowed products followed by infinite accumulators,
  and negative/tie underflow accumulation for the separate-rounding model.

## Validation

- Both semantic checks pass: original file **35/35 available modelled forms**
  (318 other forms unmodelled here); follow-up **30/30**, including nop.
  Assigned-only counts: **29/29, 348/348** and **29/29, 400/400**.
- Follow-up input multiset equals all 400 requested cases exactly; the 16
  extra records are calibration nops across eight batches. The run README
  records the split/build/batch method supplied by the lead.
- `python3 tools/hwtest/gen.py /tmp/hw-s2 --cases hw/followup-s2.json`:
  passed, 208 cases, 23 forms, two batches (182/30 including nops), last
  slot `0x01c20000`. Built only; no unit access.
- `python3 -m pi32v2isa check`: passed, 1165 entries, 0 problems.
- `python3 -m unittest discover -s tests`: passed, 118 tests, 13 skipped.
- Parsed-table comparison against round-1 HEAD: exactly the 29 assigned
  entries changed, restricted to summary/notes. Existing hardware sources
  remain; every entry cites both result files. All other table content is
  identical. `git diff --check` passed.
