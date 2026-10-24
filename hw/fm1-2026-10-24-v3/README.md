# FM-1 hardware run 3, 2026-10-24: blocks, loops, table branches, parallel pairs

The third run of [tools/hwtest](../../tools/hwtest/README.md) on the same FM-1, in record format 2 as
[run 2](../fm1-2026-10-24-v2/README.md), with stubs laid out by the generator (`gen.py --wave block`,
`--wave pair`):

- `if`/`ifs`/`iff` blocks (44 openers, 12 cases each): the opener with random then/else lengths (1..4, 0..3),
  then-part markers `r8.. = 0x100 + k`, else-part markers `r12.. = 0x200 + k`; condition registers r0..r7.
- `rep` / `rep.i`: a body of 1..3 `r7 += 1`; the count register (r0..r6) holds 1, 2, 3, 5 or 7.
- `tbb` / `tbh`: a three-entry table right after the instruction, each entry landing on `r8 = k + 1` and the
  taken exit; index 0..2 (tbh: twice that).
- Parallel twins (282 of the 340 whose plain form has a model, 8 cases each): `A #` then `[rb+n] = rd` or
  `rd = [rb+n]` (16-bit), rd = A's first destination register (r0..r7), rb an address into the scratch.

```sh
python3 tools/hwtest/gen.py DIR --wave block --first-slot 0x01C20000                 # 11 batches
python3 tools/hwtest/gen.py DIR --wave pair --per-entry 8 --first-slot 0x01C28000    # 38 batches
```

All 49 batches completed, no reset. `results.jsonl` (3002 records) and `patterns.json` as in run 2; pair records
carry `pair_b` (the second instruction: id, d, b, n). Models: `tools/hwtest/semantics/v3.py`; all match except
the six `iff.ne.rr.N` variants, which have none. What the run showed:

- Blocks: the then-part runs when the condition holds, else the else-part, with the part lengths the shape bits
  give; `if` compares unsigned, `ifs` signed, `iff` as floats with `u` conditions also true for NaNs. No flags.
- `rep`: the body runs as many times as the register says and the register ends at 0. `rep.i`, `tbb`, `tbh`
  as their summaries say.
- Pairs: B reads the registers as they were before A; when both write a register, A's result stays (a
  half-register A keeps the other half from B's load).
- `iff.ne.rr.1`..`.6` (objdump prints them all as `iff (a != b)`): with random words they took the then-part for
  equal pairs and for many ordered unequal ones; with clean operands (`iffgrid.json`: 1.0, 2.0, NaN against
  1.0, every flag value; `iffgrid.jsonl`) each is true exactly for equal or unordered operands, whatever the
  flags; a preceding `fcmp` does not change that (`iffstate.jsonl`). No rule tried fits both (flags, block
  shape, bits of a^b, a-b, a+b, a&b, a|b, double compares of register pairs).
