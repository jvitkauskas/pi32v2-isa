# Analyst Q, round 2: DSP hardware meanings

Evidence: `hw/fm1-2026-10-24/results.jsonl` and
`hw/fm1-2026-10-24/followup-q.jsonl`, AC791N in the FM-1. Branch `hw/q`.
The assignment contains 108 forms. Round 1 is commit `c481e13`.

## Result and changes since round 1

`tools/hwtest/semantics/q.py` still models **107/108 assigned forms**. All **1284
original cases and 271 follow-up cases** of these forms match every register and
all four low psr bits (1555 assigned modeled cases in total). The follow-up covers
97 modeled assigned forms, plus unresolved `copex` and four calibration cases.
The complete checker reports 113/113 modeled entries matching on the original
file, and 98/98 on the follow-up; these totals include the pre-existing basic
models. Other analysts' models are absent from this branch.

The only numerical model change is to the six abs/negs forms: minimum signed
inputs **saturate**, rather than wrap as the provisional round-1 models assumed.
For 32 bits, `0x80000000` becomes `0x7fffffff`; for each selected/vector halfword,
`0x8000` becomes `0x7fff`. Other halfwords and all low flags are preserved.
Before this correction the follow-up checker failed ten cases across these six
forms; all other modeled follow-up cases already passed.

The eight overflowing `sad4` cases confirm the provisional per-lane saturation
model: each unsigned 16-bit accumulator clips independently at 65535, with no
carry into the next lane. For example, adding four differences of 255 to even/odd
accumulator `0x1234fffe/0x12341234` produces `0x1333ffff/0x13331333`.
Overflow was forced in each lane and with both orders of the byte sources.

Thirty-six scalar/halfword saturator cases confirm exact clipping boundaries,
zero/sign flags and unsigned high-bit handling. In particular revision-3 signed
`sat8.rr` preserves -1, clips +32768 to +32767 and -32769 to -32768; unsigned
`sat8.rr` preserves 256 and 65535, and clips 65536 and `0xffffffff` to 65535.
Thus the sat16 behavior is confirmed at controlled thresholds. Fifteen pack
cases and 56 shift cases also agree, including count zero, signed-count extremes,
ignored upper count bits, carry and saturation. The 120 comparison and 12 min/max
cases confirm the original lane and signedness models.

`copex.ppi` remains without a numerical model after **92 total cases**. The new
control/input structure establishes observations described below, but does not
justify a general formula. `hw/followup-q2.json` requests 284 additional cases;
none has been run by this analyst.

## Revision-3 alias hypothesis

All six assigned revision-3 forms behave like older operations, and their table
encodings differ by one selector bit when dash bits are zero. Number bits within
each 16-bit word from 0 at the least significant end; word 0 is first in memory.

- `sat8.u.rr` versus `sat16.u.rr`, and `sat8.s.rr` versus `sat16.s.rr`:
  word 0 `11100000011111--` versus `11100000011110--`. The sole difference is
  **word 0 bit 2**, i.e. `0xe07c` versus `0xe078` with dash bits zero. Word 1,
  including the unsigned/signed bit, is identical. Controlled follow-up
  threshold cases agree with sat16, including flags.
- `vsat16.u.rp` versus `packb.rpe` with `n=0` (usat), and `vsat16.s.rp`
  versus `packb.rpe` with `n=1` (ssat): word 0 `1110010000000111` versus
  `1110010000000110`, differing only at **word 0 bit 0** (`0xe407/0xe406`).
  Rename source field p to s: the operand positions are equal. With dash bits
  zero, word 1 is identical. There is a constraint difference: packb fixes
  **word 1 bit 1** to zero, whereas vsat16 has a dash there. All recorded tests
  used zero there; no equivalence is established for it set. The observed
  four-halfword-to-four-byte saturation matches packb, including flags.
- `unpack4.u.pr` versus `unpackb.u.pr`, and `unpack4.s.pr` versus
  `unpackb.s.pr`: word 0 is identical (`11100100000010--`). Rename destination
  p to r: word 1 is identical except **bit 1** (set for unpack4, clear for
  unpackb); unsigned/signed bit 0 is shared. These forms have only the original
  12 cases each; no unpack cases were in the first follow-up. Their byte-to-
  halfword expansion agrees with unpackb, including flags.

These single-bit differences are consistent with an older core ignoring a
revision-3 selector and executing its older operation. They are fixed selectors
in the table, not already documented dash bits: the table alone does not prove
what pre-rev3 hardware ignores. Hardware behavior supports the hypothesis for
these six forms on this AC791N, rather than establishing a universal revision or
support claim. P's reported unchanged `popcnt.rr` is compatible with an
unsupported revision-3 instruction, but a no-op alone does not identify an older
operation alias. This report makes no claim about the other analysts' revision-3
forms, parallel twins or memory forms. No encoding was changed.

## Copex follow-up findings

The new 80 cases cross controls `0,1,2,3,4,7,8,15,16,31,32,63,64,127,128,255`
with even/odd basis inputs `0/0`, `1/0`, `0/1`, `0x40000000/0`, and
`0/0x40000000`. Only the destination pair changes and low psr bits are preserved
in all 92 original/follow-up cases.

- Controls **0/32/64/128** give identical outputs at all five basis inputs;
  **31/63/127/255** also agree. This supports ignoring immediate bits 7:5 for
  the sampled low modes 0 and 31; it does not establish that for every mode.
- Bit 4 can matter: input `0x40000000/0` gives `0x35009019/0xfffffff5` with
  control 15, but `0x3500901c/0x0000000b` with control 31. A few equal outputs
  for smaller inputs do not make these controls synonyms.
- Zero input gives `0x20000000/0` for control 0, `0x80000000/0x80` for control 7,
  and `0x3f800000/0x30800000` for control 16. Controls 0/32/64/128 give
  `0x20000001/0x6b` on input `1/0` but `0x20000000/0` on `0x40000000/0`.
  The operation is nonlinear and depends on the selected mode. The outputs
  reject a simple shift count or an unchanged operation; they do not yet identify
  the numerical transformation.

The patterns suggest specialized numerical modes, but the sampled basis values
and incomplete low-mode coverage do not establish their formulas, formats,
rounding or exceptional cases. No lookup table or forced numerical model was
added. In particular, coincidental float-looking bit patterns are insufficient
to establish a floating-point input/output convention.

## Table changes: old claim to observed behavior

Across both rounds, table edits are restricted to `summary`, `notes`, and
`sources` of the 108 assigned entries. Round 2 changes 100 notes and seven
summaries; the existing `hardware` source ids already cover the new evidence.
Every entry cites source `hardware` and `hw/fm1-2026-10-24`; round 2 adds the
specific follow-up filename and case counts to the 98 entries it exercised.
These are observations on the tested chip, not a claim about every pi32v2
implementation. Encoding,
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
  A selected-halfword write preserves the other half. Flags preserved. Round 2
  settles the minimum input: saturate to the signed maximum in all six forms.
  `abs.rr` confirms its existing compiler meaning, including this new edge fact.
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
  horizontal sum. Round 2 confirms independent unsigned lane saturation on overflow,
  without inter-lane carry. Example: source 0x0000ffff versus 0x00007fff adds 0x80 to lane
  1, changing pair even/odd 0x8b22b400/0x0000ffff to
  0x8ba2b400/0x0000ffff. Flags preserved. The original clamp hypothesis is now
  hardware-confirmed by follow-up overflows in every lane.
- **`copex.ppi`:** previously unknown beyond syntax; still numerically unresolved.
  Only the destination pair and no low flags change in all 92 cases. Inputs
  even/odd 0x7fffffff/0x8d68c25e, control 0, give
  0x20000006/0xffffffb5. Inputs 0x13bcc27e/0x00000080, control 1, give
  0x00000043/0x0000001d. Control 77 takes
  0x23ae7f5d/0xce564b90 to 0/0xce564b90. The controlled follow-up adds repeated
  control behavior but still does not establish a general formula. No lookup
  table or forced model was added.

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

## Next hardware request

`hw/followup-q2.json` contains **284 cases across five forms**, all raw field
values, and was successfully built into two batches (182 and 106 cases including
four calibration cases). The generated images were validated locally only.

- **192 copex cases:** every low-five-bit mode 0..31 crossed with six structured
  input pairs: `0x10000000/0`, `0x20000000/0`, `0/0x20000000`,
  `0x10000000/0x08000000`, `0xf0000000/0x08000000`, and
  `0x3f800000/0x3f800000`. These probe scale, source order and sign on useful
  nonzero values, while filling the missing low modes and comparing bit 4.
- **32 copex cases:** eight low modes (0,1,2,3,4,7,8,15) with upper control masks
  32,64,128,224 on the same nonzero input. Compare to the 192-case group to test
  the apparent ignored upper immediate bits beyond the sparse basis results.
- **48 copex cases:** modes 0..15 with the same nonzero source but zeroed or
  all-ones destination inputs, or source/destination overlap. Compare to the
  baseline group to distinguish a pure source transform from dependence on the
  previous destination and check overlap semantics.
- **12 unpack cases:** matched old/revision-3 signed/unsigned forms with mixed
  byte signs, all zero and all ones, including source/destination overlap.
  This adds controlled direct alias comparisons, absent from followup-q.jsonl.

Build command (output stayed inside this worktree and was removed after checking):

```
python3 tools/hwtest/gen.py .hw-q2-build --cases hw/followup-q2.json --first-slot 0x01C28000
```

The next hardware runner must choose its first slot according to the then-active
runner; this local build does not claim that 0x01C28000 will still be the next
safe slot. No hardware or ssh commands were run here.

## Validation

- `python3 -m pi32v2isa check`: 1165 entries, 0 problems.
- `python3 -m unittest discover -s tests`: 118 tests, OK (13 skipped).
- `python3 tools/hwtest/check.py hw/fm1-2026-10-24/results.jsonl`:
  113/113 modeled entries match; assigned models 107/107, 1284/1284 cases.
- `python3 tools/hwtest/check.py hw/fm1-2026-10-24/followup-q.jsonl`:
  98/98 modeled entries match; assigned models 97/97, 271/271 cases; only copex
  lacks a model. Four nop calibration cases also match.
- Follow-up image generation succeeds for all 284 new cases.
- Table diff audit: only summary/notes/sources may differ for assigned entries;
  no encoding, syntax, fields, examples, requirements or status changes.
