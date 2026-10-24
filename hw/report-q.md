# Analyst Q: DSP hardware meanings

Evidence: `hw/fm1-2026-10-24/results.jsonl`, AC791N in the FM-1. Branch `hw/q`.
The assignment contains 108 forms, each with 12 recorded cases (1296 cases).

## Result

`tools/hwtest/semantics/q.py` models 107 assigned forms. All 1284 of their cases
match every register and all four low psr bits. No modeled form leaves its flags
unchecked. `copex.ppi` remains without a numerical model: its 12 cases do not
justify one. It is a real operation, not an observed no-op.

The complete checker also loads the six pre-existing basic models: 113/113
modeled entries match; 240/353 tested entries have no model in this worktree.
These counts include forms assigned to other analysts, whose models are absent
from this branch.

## Table changes: old claim to observed behavior

Only `summary`, `notes`, and `sources` of the 108 assigned entries were edited.
Every entry cites source `hardware` and `hw/fm1-2026-10-24`. These are observations
on the tested chip, not a claim about every pi32v2 implementation. Encoding,
syntax, examples, features and confirmation status are unchanged.

- **60 comparison forms:** `all`/`alls`, `any`/`anys`, `cmp`/`cmps`, all assigned
  conditions and both operand shapes. Previously unknown beyond syntax. Register
  forms compare four **bytes**; pair forms compare four **halfwords**. The `s`
  suffix selects signed comparisons. `cmp` returns an all-ones or zero lane for
  each predicate; `all` and `any` reduce predicates over all four lanes, then
  fill the entire 32- or 64-bit destination with ones or zero. Flags preserved.
- **`abs.rhrh`, `abs.v.rr`, `negs.rhrh`, `negs.v.rr`, `negs.rr`:** previously
  unknown beyond syntax. Selected-halfword and vector forms use signed 16-bit
  values; vectors contain two halfwords. Scalar `negs` negates signed 32 bits.
  A selected-halfword write preserves the other half. Flags preserved. No case
  tested the minimum signed input, so wrapping versus saturation there remains
  unresolved for all six abs/negs forms. `abs.rr` confirms its existing compiler
  meaning while retaining that edge-case gap.
- **Eight halfword/vector min/max forms:** previously unknown beyond syntax.
  `smin`, `smax`, `umin`, `umax` select signed/unsigned minima/maxima of selected
  halfwords or corresponding two 16-bit lanes. Halfword writes preserve the
  other half. The four scalar forms confirm the existing compiler-derived
  signed/unsigned 32-bit meanings. All twelve preserve flags.
- **`align8.rrr`, `align16.rrr`, `align24.rrr`:** previously unknown beyond
  syntax. Result is the low 32 bits of `((rs << 32) | rt) >> n`, with n = 8, 16,
  24 respectively. Thus the first source supplies the high word. Flags preserved.
- **`pack.rrhrh`:** previously unknown beyond syntax. First selected halfword
  goes into the result's high half, second into its low half. Flags preserved.
- **`packb.rp`, `packb.rpe`, `packb.rp.stou`:** previously unknown beyond syntax.
  Four source halfwords become four bytes, maintaining low-to-high lane order
  across the even/odd source pair. Plain `packb` keeps low bytes. `usat` clips
  unsigned halfwords to 0..255; `ssat` clips signed halfwords to -128..127;
  `stou` clips signed halfwords to 0..255. In particular unsigned input 0xffff
  clips to 255, while signed-to-unsigned input 0xffff clips to zero. Flags
  preserved.
- **`unpackb.s.pr`, `unpackb.u.pr`:** previously unknown beyond syntax. Four
  bytes extend with sign/zero extension into four halfwords: byte 0 goes to
  the even register's low halfword, byte 3 to the odd register's high halfword.
  Flags preserved; overlapping source/destination cases use the original source.
- **`mts0.prr`, `mts1.prr`:** previously unknown beyond syntax. Interleave bytes
  (`mts0`) or halfwords (`mts1`) from two registers into a pair. From least to
  most significant, lanes are `rt0, rs0, rt1, rs1, ...`. Flags preserved.
- **`sat8.s.rhrh`, `sat8.u.rhrh`:** previously unknown beyond syntax. Clip a
  signed/unsigned selected 16-bit source to a signed/unsigned byte range;
  signed output extends to 16 bits, and only the selected destination halfword
  changes. Flags describe that 16-bit result, not the whole destination.
- **`sat16.s.rr`, `sat16.u.rr`:** previously unknown beyond syntax. Clip
  signed/unsigned 32-bit input to the signed/unsigned 16-bit range. Signed output
  extends to 32 bits. Unsigned input with bit 31 set clips to 65535, not zero.
- **Revision-3 `sat8.s.rr`, `sat8.u.rr`:** previously claimed clipping to the
  signed/unsigned **8-bit** range. On this chip these behave like **sat16**.
  Examples: unsigned 0x3f800000 gives 0x0000ffff; signed 0xc0000000 gives
  0xffff8000. This is a behavioral finding; syntax and encodings were retained.
- **Revision-3 `vsat16.s.rp`, `vsat16.u.rp`:** previously described saturation
  into 16-bit lanes, meaning unestablished. They behave like saturating `packb`:
  four source halfwords narrow to four **bytes** with signed/unsigned saturation.
  Example: signed source even/odd 0x06c431f4/0x8011b5b1 gives 0x80807f7f.
  Flags preserved.
- **Revision-3 `unpack4.s.pr`, `unpack4.u.pr`:** byte-to-halfword expansion was
  suggested but lane layout unestablished. They behave like corresponding
  `unpackb` forms, including lane order, extension and preserved flags.
- **Seven `xchg` forms:** previously unknown beyond syntax. The printed `><`
  operation is a signed-count bidirectional shift. It uses the signed low five
  bits for halfwords/two-halfword vectors, six for scalar 32-bit data, seven for
  64-bit in-place pair data. Positive counts shift left; negative counts shift
  right. Plain forms truncate left shifts and shift right logically; `sat`
  forms saturate left shifts to signed lane limits and shift right arithmetically.
  Vector lanes share one count. Halfword/vector forms preserve flags; scalar
  and pair flags are described below. The ordinary `xchg.rrr` form belongs to
  another analyst and was inspected only as supporting evidence, not edited or
  added to this module.
- **`sad4.acc.prr`:** previously claimed the **sum** of absolute byte differences
  accumulates into a pair. Instead four independent absolute unsigned byte
  differences each add to the corresponding 16-bit accumulator lane. No
  horizontal sum; overflow and inter-lane carry remain untested. Example: source 0x0000ffff versus 0x00007fff adds 0x80 to lane
  1, changing pair even/odd 0x8b22b400/0x0000ffff to
  0x8ba2b400/0x0000ffff. Flags preserved. Saturation at 65535 is suggested by
  `usat`, but no recorded case overflowed a lane; the model's clamp remains
  a hypothesis pending follow-up.
- **`copex.ppi`:** previously unknown beyond syntax; still numerically unresolved.
  Only the destination pair and no low flags change in all 12 cases. Inputs
  even/odd 0x7fffffff/0x8d68c25e, control 0, give
  0x20000006/0xffffffb5. Inputs 0x13bcc27e/0x00000080, control 1, give
  0x00000043/0x0000001d. Control 77 takes
  0x23ae7f5d/0xce564b90 to 0/0xce564b90. Arbitrary unrelated inputs and controls
  do not separate a general numeric operation from control-specific behavior.
  No lookup table or forced model was added.

## Flags

- Comparisons, abs/negs, all min/max, align, pack/unpack, mts, sad4, vector and
  halfword `xchg`, and `copex` preserve the input low four psr bits in every case.
- Scalar and halfword saturators, including revision-3 register `sat8`, preserve
  bits 0 and 1, replace bit 3 with result sign, and replace bit 2 with result-zero.
  For halfword saturation, sign is bit 15 after extension within the selected
  destination halfword. Bit 0 is preserved even when saturation occurs.
- Scalar `xchg.rrr.sat` preserves bit 0, sets bit 3 sign and bit 2 zero from
  the final clamped 32-bit result, and sets bit 1 to the last shifted-out source
  bit. Count zero preserves bit 1.
- Pair `xchg.pr` and `xchg.pr.sat` change only bit 1 to the last shifted-out
  source bit, preserving the other low bits even if the result becomes zero.
  Count zero preserves carry. Carry uses the original input even on saturation.
- None of these observations establishes the general meaning of psr bit 0.

## Follow-up

`hw/followup-q.json` contains **351 cases across 98 forms**, below the 400-case
budget. All fields are raw encoding values. Built successfully with:

```
python3 tools/hwtest/gen.py /tmp/hw-q --cases hw/followup-q.json
```

This produced two batches, 182 and 173 cases including calibration; the final
batch uses slot 0x01c20000. No hardware or ssh command was executed.

Required to settle unresolved behavior:

- 80 `copex` cases: five fixed basis inputs crossed with 16 controls including
  individual control bits and combinations. This separates input effects from
  immediate effects; the first run varied both simultaneously.
- 24 abs/negs cases: minimum signed 16-/32-bit values, neighbors, -1 and zero;
  distinguish wrapping from saturation and check unchanged flags.
- Eight sad4 cases: force overflow in each accumulator lane separately; test
  saturation versus wrapping and any carry into neighboring lanes.

Additional controlled checks strengthen inference beyond sparse random samples:

- 120 comparison cases exercise mixed equality and signed/unsigned lane ordering,
  plus equal operands, across every comparison/reduction form.
- 12 min/max cases check signed extrema against unsigned ordering.
- 36 saturator cases and 15 pack cases cover exact clipping thresholds, negative
  values, unsigned high-bit inputs, lane order and zero-result flags.
- 56 `xchg` cases cover zero, positive/negative boundaries, maximum right shifts,
  count-field wrapping, ignored upper bits and carry behavior. Not every boundary
  count occurred in the first run.

Abs/negs currently model wrapping at the unobserved minimum; sad4 currently
models saturation on unobserved overflow. These are explicit provisional choices,
not hardware-confirmed outcomes. All stated complete matches concern the original
12 cases per form. Results of the follow-up must settle those choices before
claiming complete edge semantics.

## Validation

- `python3 -m pi32v2isa check`: 1165 entries, 0 problems.
- `python3 -m unittest discover -s tests`: 118 tests, OK (13 skipped).
- `python3 tools/hwtest/check.py hw/fm1-2026-10-24/results.jsonl`:
  113/113 modeled entries match on every case, including 107/107 assigned models.
- Follow-up image generation succeeded for all 351 cases.
