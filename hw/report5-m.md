<!-- SPDX-FileCopyrightText: 2026 Julius Vitkauskas -->
<!-- SPDX-License-Identifier: CC0-1.0 -->

# Analyst M, round 5: memory forms (hardware run 2)

Worktree `m`, branch `hw2/m`. Models: `tools/hwtest/semantics/m2.py`. Evidence: `hw/fm1-2026-10-24-v2/results.jsonl`.
Follow-up: `hw/followup5-m.json` (110 cases), run by the lead as `followup5-m-main.json` (109 cases) and
`followup5-m-npc.json` (the misaligned probe, alone); results `hw/fm1-2026-10-24-v2/followup5-m.jsonl` and
`followup5-m-npc.jsonl`. I ran nothing on hardware.

## Result

**All 130 forms match on every case** (1564 cases of run 2 plus 109 + 1 of the follow-up), flags included; with `ld.w`
and `st.w` (basic2 models, untouched) `check.py ... --id` gives 132/132 on `results.jsonl`, 57/57 on `followup5-m.jsonl`
and 1/1 on `followup5-m-npc.jsonl`. `check.py` on run 1 still gives 352/352.

- Loads and stores of every size and mode, the read-modify-write forms and `st.w.modimm` need no more than the
  obvious reading. They never touch the flags N Z C V (random flags in every case, all kept), also not the
  read-modify-write shifts (unlike the register shifts, which set N Z C).
- Only `testset.b` writes flags (below).

## Corrections to the table (old claim -> hardware)

- `ld.w.npc`, `ld.w.npc.r`: "meaning of npc and its base address unknown" -> with the instruction on a word boundary
  the load reads the word at (address of the instruction + 4) + offset. For the 6-byte `ld.w.npc` that address is
  inside the instruction (`[npc + 0]` = its third halfword and the next one); for the 4-byte `ld.w.npc.r` it is the
  next instruction. The summary said "even signed 32-bit offset": the sum must be word-aligned (offsets 2 and 6,
  probed alone, reset the chip), so in practice multiples of 4. **Settled by the probe**: with the 6-byte `ld.w.npc` at 2 mod 4, `[npc + 0]` did not reset and read the word at
  address + 6 (the goto after it). So npc = pc + 4 rounded up to a word boundary (here also the instruction's end
  rounded down); not `pc + 4` (misaligned, would reset) and not `pc + 2`. For the 4-byte `ld.w.npc.r` at 2 mod 4 the
  two readings differ (address + 6 or + 2) and were not run.
- `testset.b`: "atomicity and result flag not tested" -> the byte becomes 0xFF and psr bits 3..0 (N Z C V) become
  bits 3..0 of the *old* byte; the flags before do not matter (12/12, old bytes 0x13..0xE5; the follow-up's 32 cases
  add old 0x00 -> no flags, 0xFF -> all four and unchanged, and every low nibble). Summary rewritten. This
  fits the AC79 SDK lock (`testset` then `ifeq goto` retry): a held lock is 0xFF so Z is set, a free 0x00 clears it.
- `ld.{bu,hu,w}.pi`, `st.{b,h,w}.pi` (and the other `.pi`/`.pin`): "what happens to the base register is read from the
  syntax (meaning not tested)" -> confirmed: access at the old base, then the base register gets the sum.
- All `rmw.*`: "meaning of the whole read-modify-write assumed from the syntax" -> confirmed. Word at base + offset,
  result stored back; register shift counts are the low 8 bits and 32 or more acts as 32 (`shl3`: signed saturation);
  a count field of 0 means 32; `bitr` forms use the low 5 bits of the register; `and.nmodimm` ANDs with the printed
  constant.
- `ld.w`, `st.w`, and every other entry: hardware source and a note added; no other claim was wrong.

## Surprises

- Every 64-bit store (`st.d.pi.l`, `st.d.pin.l`, `st.d.pre`, `st.d.prer`): the pair's **odd register is read after the
  base update, the even one before**. Base = odd register: the high word stored is the updated base (run 2: 3 cases,
  follow-up: all four modes); base = even register: the low word stored is the old base. Scalar stores with
  source = base store the old value. Reads as two beats with the update in between. (Run 2's pre-increment cases
  only had the even register as base, which is why the first model assumed "post-increment only".)
- Loads whose destination is the base register keep the loaded value (the update is lost): all `ld.*` post/pre forms,
  follow-up included. Post-increment loads whose increment register is the destination add the *old* value
  (`r4 = [r9++=r4]`: base + old r4); with increment = base the base doubles.
- `ld.d`/`st.d` ran at addresses 4 mod 8 (96 cases): 4-byte alignment is enough.
- Halfword and word accesses were only ever run aligned; no misaligned access other than the `npc` ones was tried.

## How the `npc` loads are modelled

They read code, not the scratch. `m2.py` rebuilds the batch's code from the batch's own records (every stub is its
case bytes, a 4-byte `goto hw_exit0` to slot base + 0x220, zero padding) and finds the batch through the case's 16 input
registers in the results files under `hw/*/`. 22 of the 28 reads fall inside it and match; 6 (`ld.w.npc` at offsets
8, 60, 68, 92, 100, 116, from stubs at the end of a batch) read past the last stub into the batch's data; there the
model returns the recorded value, so only the address is unchecked.

## What the follow-up settled (`followup5-m.jsonl`, `followup5-m-npc.jsonl`)

All 109 + 1 cases match the models once the 64-bit store rule above and the new `npc()` are in.
1. Data register = base register, every pre/post-increment form: loads keep the loaded value, scalar stores store the
   old value, 64-bit stores as above. `st.h.hi` with `pre`/`prer`/`pin` cannot tell old from new (the update leaves the
   high half alone); `st.h.hi.pi.l` with an increment of 0x10000 stores the old high half.
2. Increment register = destination or base (post-increment loads and stores): the add uses the register's value
   from before the instruction.
3. `testset.b`: psr bits 3..0 = old byte bits 3..0 for all 16 nibbles; old 0x00 and 0xFF as above.
4. npc at 2 mod 4: see the correction above.

## Not covered

Misaligned halfword/word accesses (other than the `npc` ones); `npc` offsets beyond the batch's code; atomicity of
`testset.b` and the read-modify-write forms; `ld.w.npc.r` at 2 mod 4. `docs/GAPS.md` and `docs/COMPILER.md` still carry
the old statements (flags of the memory forms unknown, memory forms untested) and are left to the lead.
