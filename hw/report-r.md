# Analyst R: DSP arithmetic and multiply group

Forms: 111 (the list in ids-r.txt of the round). Models: `tools/hwtest/semantics/r.py` and `_r_util.py`. Evidence:
`hw/fm1-2026-10-24/results.jsonl` (12 cases per form) and `hw/fm1-2026-10-24/followup-r.jsonl` (403 hand-built cases,
3 batches, no hang). All 111 forms match on every case of the first run; the follow-up matches on all 96 forms it
covered (97 ids with `nop`).

## Corrections to the table (old claim -> hardware)

- `sum.{s,u}`, `sum.acc.{s,u}`, `sum.nacc.{s,u}` `.prhrhrhrh`: "meaning unknown" -> no horizontal sum. They write two
  separate 32-bit products into the pair (`rs.n*rt.p` to the odd register, `rs.m*rt.q` to the even one) and are
  the pair `mul2`, `madd.mul2` and `msub.mul2` forms with `(s)` = `ssat`, `(u)` = `usat`; second-word bit 12 is ignored.
- `sum.acc.{usat,ssat,msat}.rrr`: "accumulate a sum of four lane products" -> all three execute as
  `add4.rrr.rnd.uavg` (per-byte unsigned `(a+b+1)>>1` of `rs` and `rt`; old `rd` unused). Second-word bits 2 and 1 are
  ignored when bit 3 is set. The follow-up gave the same result for all three.
- `shl3` (`<<<`, all four shapes): "unknown" -> saturating signed shift left on 16-bit lanes (0xb42a <<< 16 =
  0x8000, 0x7f80 <<< 14 = 0x7fff, 0xffff <<< 3 = 0xfff8). The id keeps the printed operator;
  `docs/GAPS.md` still lists `shl3` as open (not edited, outside my files).
- Everything else was "unknown beyond the syntax" and is now specified in the entries: halfword and two-lane
  add/sub with modes, `add4`, shifts, 64-bit right shifts with narrowing, 16 x 16 multiplies and their accumulate
  forms, `mul4`.

## What the follow-up settled

- Register shift counts (`lsl/lsr/asr/shl3` `.rhrhr` and `.v.rrr`, `lsr.{s,u}.rpr`): the count is the low 8 bits of
  `rt`. 6- and 7-bit counts are ruled out, counts of 128..255 are large counts and not right/left reversals, and bit 8
  and up are ignored (seen on `lsl/lsr/asr` and the pair shifts; `shl3` saturates either way so it cannot show it).
- `(usat,x2)` on a subtracted lane: a difference of exactly 0x8000 (double does not fit) gives 0, as the larger ones
  did; differences up to 0x6a61 double normally. 0x7fff was not tried.
- Saturation edges reached and held: `madd.rrhi.*`, `msub.rrhi.ssat`, `msub.mul2.prhrhi.*`, `addsub.rhrhi.sat`,
  the 16- and 32-bit accumulate forms, `add.rrre`/`sub.rrre`, `addsub.pqq.sat`, `addsub.ppp.mode`.
  Still unreached: clamping in `madd.mul2.prhrhi.{ssat,usat}` (my operand signs did not overflow).
- Accumulator reads: halfword and `mul2.rr` accumulators are read as unsigned even in `ssat` mode; 32-bit ones are
  signed under `ssat`; the sum is clamped once after the accumulate (clamping the product first failed).
- `madd`/`msub` `.prr` carry rule held on the edge accumulators; `add4.ppr` wraps modulo 2^16.
- `sum.acc.*.rrr` aliasing: confirmed (see above).

## Other behaviour worth knowing

- Odd: `(usat,x2)` on a subtracted lane gives 0, not 0xffff, once the doubled difference exceeds 16 bits (above).
- Halfword `madd`/`msub` read the accumulator half as unsigned in `ssat` mode (0xaaaa + 0 gave 0x7fff).
- `mul4` / `madd.mul4`: `rs` bytes unsigned, `rt` bytes (or the immediate) signed for `(m)`; results are 16-bit lanes in
  the pair and wrap modulo 2^16.
- `mul.rhrhrhe`: the 16-bit result is the clamped product itself, not a high half.
- Averaging subtraction takes the exact difference modulo 2^17 before halving (0 - 0x82ee -> 0xbe89 in `(uavg)`).

## Flags

`psr` is unchanged for every form except these (all cases, both runs):

- `lsr.{s,u}.rpi` / `lsr.{s,u}.rpr`: bit 3 = bit 31 of the result (N), bit 2 = result zero (Z), bit 1 = last bit
  shifted out (bit n-1 of the 64-bit input; bit 63 for counts of 64 and up; 0 for count 0), bit 0 never written,
  not even when the result saturates.
- `madd.{s,u}.prr`: bit 1 = carry out of the 64-bit add; other bits unchanged.
- `msub.{s,u}.prr`: bit 1 = 1 when there is no borrow (old pair >= product mod 2^64); other bits unchanged.
- `mul.{s,u}.prr` leaves `psr` alone.

For analyst P: bit 3 behaves as the sign flag and bit 2 as the zero flag here; bit 0 (probably overflow) is not
touched by shifts.
