# Analyst P: ALU, logic, shifts, bit operations, constants, moves, `cc.set`

99 forms (`ids-p.txt`). Models: `tools/hwtest/semantics/p.py` (helpers in `_p_util.py`). Evidence:
`hw/fm1-2026-10-24/results.jsonl` (12 cases per form) and `hw/fm1-2026-10-24/followup-p.jsonl` (304 edge cases from
`hw/followup-p.json`, 2 batches, no hang).

## Result

All 99 forms match on every case of the first run, flags included (`check.py`: 105/105 modelled entries, counting the 6
of `basic.py`), and all 56 forms of the follow-up match on every case.

## Corrections to the table (old claim -> hardware)

- `rev16.rr`: reverse the order of the halfwords -> swaps the two bytes inside each halfword.
- `revs.rr`: unknown -> byte-swap of the low halfword, sign-extended.
- `shl3.*` (32-bit and pair): unknown -> signed saturating shift left (clamps to 0x7FFFFFFF / 0x80000000, or the 64-bit limits).
- `cycc.*`: unknown -> rotate right through the carry (33 bits; 65 for pairs; count 32 is a rotate left by 1).
- `xchg.rrr`: unknown -> shift by the low 6 bits of `rt` as a signed count (positive left, negative right, zero fill).
- `add.brev.rr`: exact meaning unknown -> `rev(rev(a) + rev(b))`, flags of the reversed addition.
- `shiftr.*`: unknown -> shift a pair right by the count, round to nearest, saturate to 32 bits (unsigned for `>>`,
  signed for `>>>`); the mode only decides exact ties: up toward +inf, even, round away from zero, zero toward zero.
  C is the rounding bit.
- `asr.ppi.rnd.vh`: unknown -> each halfword shifted right (sign fill) by 0..7, rounded to nearest, ties toward +inf.
- `lsr.rri.vb`: unknown -> each byte shifted right by 0..7 on its own.
- `popcnt.rr`: population count -> changes nothing (no register, no flag, no trap) on this chip.
- `popcnt.r_pair`: population count of a pair -> behaves as `mov.half` `rd.l = r(2s).l`; no flags.
- `lsl`/`lsr`/`asr` by register: counts of 32 or more "not established" -> act as 32; the count is the low 8 bits.
- `lsr.rr`/`lsr.rri`: logical vs arithmetic "not tested" -> logical. `mul.*`: truncation "not tested" -> low 32 bits.
- `sextra.rrii`: a field running past bit 31 reads the missing bits as 0, so it is not sign-extended from bit 31
  (the first model clipped the field at bit 31; the follow-up showed otherwise). `uextra` and `insert` drop the bits
  past bit 31; `insert` with l:0 and the extracts with l:0 give no field.
- `cc.set`: "the condition flag" -> psr bit 1 (C), the other flag bits untouched.

## Flags (psr bits 3..0)

Bit 3 N (result bit 31), bit 2 Z (result is zero), bit 1 C, bit 0 V. Add, subtract, `addc`, `subc`, `rsub`,
`add.brev.rr` write all four (subtract: C = no borrow). Logic, multiply, extensions, `clz`/`cls`/`sgn`, `rev*`,
bit fields, `ror.rri`/`ror.rrr` write N and Z. 32-bit shifts, `shl3`, `cycc.rri`/`rrr`, `xchg`, `shiftr.*` write N, Z
and C (last bit shifted out; a count of 0 keeps C). Pair shifts and `cycc.pi`/`pr` write only C; `ror.pi`/`ror.pr`
write none. `li.*`, `mov.*`, `popcnt.*`, `lsr.rri.vb`, `asr.ppi.rnd.vh` write none. Details in `docs/COMPILER.md`.

## Follow-up: what it settled

Z, C and V of every add/subtract form (each reached); register counts use only the low 8 bits (0x100 = 0, 0x105 = 5;
0x41 = 64 for pairs; `xchg` ignores bits 6 and up, rotates reduce modulo 32/64); the `shiftr` and `asr.ppi.rnd.vh` tie
rules; `cls`/`clz` edges (cls(0xFFFFFFFF) = 32, clz(0) = 32); `popcnt.rr` still changes nothing and `popcnt.r_pair`
still fits `mov.half`; N and Z results of the forms that had none. The only miss was `sextra` past bit 31, now fixed.

## Surprises

`popcnt` is absent from this chip in both forms; `shl3` and `xchg`, unexplained mnemonics, are saturating and
bidirectional shifts; the pair shifts leave N and Z alone although the result has a sign.
