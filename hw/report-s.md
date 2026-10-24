<!-- SPDX-FileCopyrightText: 2026 Julius Vitkauskas -->
<!-- SPDX-License-Identifier: CC0-1.0 -->

# Analyst S: floating point and division

Worktree `s`, branch `hw/s`; evidence: `hw/fm1-2026-10-24/results.jsonl`.
All **29 assigned forms match every case (348/348), including the low four psr
bits**, with `tools/hwtest/semantics/s.py`. The full checker also includes six
pre-existing basic models: 35/35 modelled forms match. No assigned form has an
unexplained register change or an inconsistent result. `fcmp.rr` deliberately
writes no register; this is a comparison, not an unimplemented instruction.

The model uses exact rational values and explicit binary32/binary16 rounding,
so host NaN conventions, integer division, or double rounding do not determine
its results. It models all flags on these 29 forms. Predictions for unmeasured
cases are identified below and in the model; agreement on 12 cases does not
settle those predictions.

## Table changes (old claim -> hardware finding)

Only `summary`, `notes`, and `sources` of the 29 assigned entries changed. Each
now cites `hardware` and `hw/fm1-2026-10-24`. Encodings, examples, syntax,
fields, and status are untouched.

- `div.u.ppr`, `div.s.ppr`: meaning unknown -> a 64-bit dividend divided by a
  32-bit divisor returns the full 64-bit quotient in the destination pair, not
  a quotient/remainder pair. The low word is even, high word odd. Signed
  division truncates toward zero. Both forms preserve psr.
- `div.u.rrr`, `div.s.rrr`: quotient only, flags unspecified, division by zero
  unknown -> ordinary quotients agree with unsigned division / signed
  truncation toward zero; bits 0..1 survive and bit 2 records zero. Signed division sets bit 3 to
  the quotient's sign bit; unsigned division clears it on all sampled
  quotients, none of which has bit 31 set. Unsigned `0/0` returned 0 without trapping. **There
  is no signed zero-divisor or `INT_MIN / -1` case in the assigned data, and
  no nonzero integer dividend / zero case at all.** Their results remain
  unsettled, rather than being inferred from the absence of traps elsewhere.
- `fcmp.rr`: result goes to an unspecified flag -> replaces the low psr bits
  with less `0x8`, equal `0x6`, greater `0x2`, unordered `0x3`; all sixteen
  registers survive. NaN on either side produces unordered.
- `fmin.rrr`, `fmax.rrr`: float minimum/maximum, flags unspecified -> selection
  agrees, including subnormals; they also write the same comparison flags as
  `fcmp s,t`. The original NaN uncertainty remains: neither form has a NaN
  source in its 12 cases. Equal operands have identical bits, so signed-zero
  tie selection is also unknown.
- `add.f.rrr`, `sub.f.rrr`, `mul.f.rrr`, `div.f.rrr`: single-precision arithmetic,
  rounding/special values/flags unspecified -> binary32 nearest-even models
  match, and psr is preserved. Addition retains subnormal inputs/results;
  multiplication and division retain subnormals and gradually underflow to
  zero. Subtraction of equal finite operands, including `-0`, gives `+0`.
  NaN inputs to subtraction and multiplication return `0x7f800001` (not the
  usual quiet-NaN bit pattern). Addition/division have no NaN source case.
  Multiplication includes infinity * infinity -> infinity. Division includes
  finite / infinity -> signed zero and finite overflow -> signed infinity.
  Arithmetic halfway cases and invalid infinity/zero combinations need more
  evidence.
- `madd.f.rrr`, `msub.f.rrr`: meaning unknown -> accumulator plus/minus the
  product; psr survives. NaN source or accumulator produces `0x7f800001`.
  Every sampled result fits **both fused and separately rounded** arithmetic;
  the model uses fused evaluation provisionally. The `madd` input accumulator
  `0x0000ffff`, sources `0x484e0bf7` and `0x00000002`, produces `0x0007705f`,
  showing a subnormal contribution is retained.
- `ftoi.even.rr`, `ftoi.ceil.rr`, `ftoi.floor.rr`: meaning unknown -> signed
  conversion with the indicated nearest/upward/downward finite results;
  observed out-of-range and NaN inputs saturate to the endpoint selected by
  their sign. In `even`, `0xffffffff` -> `0x80000000` and `0x7fffffff` ->
  `0x7fffffff`; in `ceil`, positive infinity -> `0x7fffffff`; in `floor`,
  positive quiet NaN -> `0x7fffffff`. Psr survives. Half-integer ties and the
  exceptional values not sampled for each individual form remain open.
- `ftoi.trunc.rr`: C signed cast -> confirmed for sampled finite values;
  positive overflow and infinity saturate to `0x7fffffff`; psr survives.
  Negative overflow/NaNs were not sampled for this form.
- `ftou.even.rr`, `ftou.ceil.rr`, `ftou.floor.rr`: meaning unknown -> unsigned
  conversion with nearest/upward/downward finite results, negative inputs
  clamped to 0, positive overflow to `0xffffffff`; psr survives. No halfway
  input establishes the `even` tie rule.
- `ftou.trunc.rr`: C unsigned cast -> finite truncation agrees; negative values
  and negative NaN `0xffffffff` give 0, positive overflow gives `0xffffffff`;
  psr survives.
- `ftof.even.rr`: meaning unknown -> nearest integer-valued binary32, retaining
  negative zero when rounding a small negative number; psr survives. No
  halfway case establishes ties-to-even yet.
- `ftof.trunc.rr`, `ftof.ceil.rr`, `ftof.floor.rr`: compiler's float-rounding
  interpretation -> sampled results agree and psr survives. Truncation and
  ceiling retain negative zero. Floor maps NaNs `0xffffffff` / `0x7fc00000`
  to `0xffc00000` / `0x7fc00000`, discarding payload but retaining sign.
- `itof.rr`, `utof.rr`: signed/unsigned float conversion -> results agree with
  nearest-even binary32 and preserve psr. Signed input `0xfd7abe52`
  (-42287534), a midpoint, gives `0xcc21506c` (-42287536), the even significand.
  Other signed/unsigned midpoint parities need deliberately chosen inputs.
- `ftof.half.rr`: meaning unknown -> binary32-to-binary16 interpretation fits:
  only the low destination half changes; the upper half and psr survive.
  Tiny inputs give signed half zero, huge inputs signed half infinity; NaNs
  `0x7fc00000` / `0xffffffff` give `0x7e00` / `0xfe00`. No sample yields an
  ordinary finite nonzero half, so the exact finite rounding rule needs the
  follow-up values.
- `ftof.full.rr`: meaning unknown -> binary16 in the source low half becomes
  binary32; the source high half is ignored, psr survives. Half subnormals
  expand, e.g. low half `0x007f` -> `0x36fe0000`; low half `0xffff` becomes
  canonical negative NaN `0xffc00000`.

## Flags and surprising results

The three float comparisons (`fcmp`, `fmin`, `fmax`) overwrite all four low
bits. Observed outcomes are less `1000`, equal `0110`, greater `0010`, and
unordered `0011` (unordered is observed only on `fcmp`). This is consistent
with bit 3 as negative, bit 2 as zero, bit 1 as carry, bit 0 as overflow; the
models use the measured bit patterns without relying on names. Comparison
flags describe the source ordering, not the sign or zero-ness of the selected
minimum/maximum.

The two 32-bit integer divisions preserve bits 0 and 1 and replace bit 2
with quotient-zero. Signed division sets bit 3 to quotient-sign; unsigned
division clears bit 3 on the sampled quotients, all below 2^31. The unsigned
quotient-sign interpretation is a prediction tested by the follow-ups. Both 64-bit divisions preserve all
four bits. All other assigned float forms preserve all four bits, including
NaN, overflow and underflow samples. Upper psr bits are zero in the entire
run; the runner does not establish what happens for nonzero upper input bits.

The arithmetic NaN result `0x7f800001`, canonical sign-preserving conversion
NaNs, the flag-writing `fmin/fmax`, and flag-preserving 64-bit division are
notable. The arithmetic NaN bit pattern would conventionally be a signalling
NaN; no trap occurred in these sampled cases. No general exception mechanism
or exception-status semantics is established by this run.

## Follow-up cases

`hw/followup-s.json` has exactly **400 cases**, all 29 forms. Case numbers below
are one-based array positions, before the generator inserts calibration nops.
All operands use raw register/pair field values; sentinel registers make
unexpected writes visible. These are cases to run, not new measurements.

- 1..104 (104): all eight `ftoi/ftou` forms, each with 13 sources: signed
  half-integers, signed subnormals, both NaN signs, infinities, the last
  representable value below the positive limit, and out-of-range endpoints.
- 105..160 (56): all four integer-valued `ftof` forms; positive/negative zero,
  half-integer ties of both parities, NaNs, infinities, signed subnormals.
- 161..184 (24): both binary16 conversions; finite normals/subnormals,
  midpoints, max-finite/overflow boundary, signed zero, infinities and NaNs.
  Nonzero source/destination high halves test which halves matter.
- 185..200 (16): `itof/utof`; midpoint parity, signed negative midpoints for
  `itof`, zero and integer endpoints.
- 201..248 (48): add/sub/mul/div; rounding ties where possible, subnormals,
  gradual underflow, signed zero, NaN operand order and invalid combinations
  (`infinity-infinity`, `0*infinity`, `0/0`, `infinity/infinity`).
- 249..268 (20): multiply-add/subtract fusion witnesses, intermediate product
  overflow with a cancelling accumulator, NaN in each input/accumulator,
  invalid products, signed zero and subnormal accumulation.
- 269..300 (32): min/max with each NaN operand order, two NaNs, both signed-zero
  orders, infinities, signed subnormals and ordinary comparisons.
- 301..320 (20): `fcmp` with flags initially 0 and 15 for each outcome, then
  signed zeros/subnormals, infinities and NaN operand orders. This directly
  tests replacement rather than preservation of each flag bit.
- 321..400 (80): all four integer divides; 0, 1, all-ones, sign-bit and
  32-bit edge dividends divided by zero, quotient signs and truncation,
  signed `INT_MIN / -1` (32- and 64-bit), wide quotients, zero quotients,
  and negative/large divisors. These settle the missing zero-divisor and
  signed-overflow results without assuming a trap or an all-ones quotient.

For the first fusion witness, sources `0x3f800001` and `0x3f7ffffe` multiply
exactly to `1 - 2^-46`. `madd` with accumulator `-1` gives `-2^-46` if fused,
`+0` if separately rounded; `msub` with accumulator `+1` gives `+2^-46` if
fused, `+0` if separately rounded.

Unmeasured model predictions are nearest-even ties, fused multiply-accumulate,
second-source min/max selection for ties/unordered, arithmetic-invalid NaN
`0x7f800001`, sign-selected conversion saturation for all exceptional forms,
zero quotient on integer zero divisors, unsigned quotient-sign in psr bit 3,
and wrapped signed quotient overflow.
These are hypotheses for the follow-ups, not table claims of measured facts.

## Validation

- `python3 tools/hwtest/gen.py /tmp/hw-s --cases hw/followup-s.json`: passed;
  29 forms, 400 cases, three batches (182/182/42 including calibration nops).
  Last batch slot `0x01c28000`. Images were built only; no hardware or ssh
  commands were run.
- Exact-rounding helper cross-check: every finite binary16 pattern round-trips
  and expands to the same binary32 as Python's binary16 decoder. A seeded
  sample of 10,000 binary32 input pairs agrees with host binary32-rounded
  finite add/subtract/multiply; normal/subnormal carry and halfway-to-zero
  boundaries were also checked. This validates model machinery, not hardware.
- `python3 -m pi32v2isa check`: passed, 1165 entries, 0 problems.
- `python3 -m unittest discover -s tests`: passed, 118 tests, 13 skipped.
- `python3 tools/hwtest/check.py hw/fm1-2026-10-24/results.jsonl`: passed,
  35/35 modelled forms; 318/353 tested forms have no model in this worktree.
  A separate assigned-id check confirms 29/29 forms and 348/348 cases, with
  flags checked on every assigned form.
- Final parsed-table comparison against HEAD confirms that exactly the 29
  assigned entries changed, restricted to summary/notes/sources.
  `git diff --check` passed.
