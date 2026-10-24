<!-- SPDX-FileCopyrightText: 2026 Julius Vitkauskas -->
<!-- SPDX-License-Identifier: CC0-1.0 -->

# Analyst M, round 5: memory forms (hardware run 2)

Worktree `m`, branch `hw2/m`. Models: `tools/hwtest/semantics/m2.py`. Evidence: `hw/fm1-2026-10-24-v2/results.jsonl`.
Follow-up: `hw/followup5-m.json` (110 cases, builds with `gen.py`). Nothing was run on hardware.

## Result

**All 130 forms match on every case** (1564 cases), flags included; with `ld.w` and `st.w` (basic2 models, untouched)
`check.py ... --id` gives 132/132. `check.py` on run 1 still gives 352/352.

- Loads and stores of every size and mode, the read-modify-write forms and `st.w.modimm` need no more than the
  obvious reading. They never touch the flags N Z C V (random flags in every case, all kept), also not the
  read-modify-write shifts (unlike the register shifts, which set N Z C).
- Only `testset.b` writes flags (below).

## Corrections to the table (old claim -> hardware)

- `ld.w.npc`, `ld.w.npc.r`: "meaning of npc and its base address unknown" -> with the instruction on a word boundary
  the load reads the word at (address of the instruction + 4) + offset. For the 6-byte `ld.w.npc` that address is
  inside the instruction (`[npc + 0]` = its third halfword and the next one); for the 4-byte `ld.w.npc.r` it is the
  next instruction. The summary said "even signed 32-bit offset": the sum must be word-aligned (offsets 2 and 6,
  probed alone, reset the chip), so in practice multiples of 4. Not told apart yet: `pc + 4` vs `(pc + 4) & ~3` vs
  "end of the instruction rounded down" (all stubs were aligned): see the follow-up.
- `testset.b`: "atomicity and result flag not tested" -> the byte becomes 0xFF and psr bits 3..0 (N Z C V) become
  bits 3..0 of the *old* byte; the flags before do not matter (12/12, old bytes 0x13..0xE5). Summary rewritten. This
  fits the AC79 SDK lock (`testset` then `ifeq goto` retry): a held lock is 0xFF so Z is set, a free 0x00 clears it.
- `ld.{bu,hu,w}.pi`, `st.{b,h,w}.pi` (and the other `.pi`/`.pin`): "what happens to the base register is read from the
  syntax (meaning not tested)" -> confirmed: access at the old base, then the base register gets the sum.
- All `rmw.*`: "meaning of the whole read-modify-write assumed from the syntax" -> confirmed. Word at base + offset,
  result stored back; register shift counts are the low 8 bits and 32 or more acts as 32 (`shl3`: signed saturation);
  a count field of 0 means 32; `bitr` forms use the low 5 bits of the register; `and.nmodimm` ANDs with the printed
  constant.
- `ld.w`, `st.w`, and every other entry: hardware source and a note added; no other claim was wrong.

## Surprises

- `st.d.pi.l`, `st.d.pin.l` (post-increment 64-bit store): when the base register is the odd register of the stored
  pair, the *high word stored is the already updated base* (3 cases: `d[r9++=r5] = r9_r8` stored r9 + r5 as the high
  word). Every scalar store with source = base stored the value from before the update (also pre-increment, and
  `d[++r2=-4] = r3_r2` with the base as even register). Reads as two beats with the update in between. Modelled; the
  other combinations are in the follow-up.
- Loads whose destination is the base register keep the loaded value (the update is lost) in every case seen.
- `ld.d`/`st.d` ran at addresses 4 mod 8 (96 cases): 4-byte alignment is enough.
- Halfword and word accesses were only ever run aligned; no misaligned access other than the `npc` ones was tried.

## How the `npc` loads are modelled

They read code, not the scratch. `m2.py` rebuilds the batch's code from the batch's own records (every stub is its
case bytes, a 4-byte `goto hw_exit0` to slot base + 0x220, zero padding) and finds the batch through the case's 16 input
registers in the results files under `hw/*/`. 22 of the 28 reads fall inside it and match; 6 (`ld.w.npc` at offsets
8, 60, 68, 92, 100, 116, from stubs at the end of a batch) read past the last stub into the batch's data; there the
model returns the recorded value, so only the address is unchecked.

## Follow-up (`hw/followup5-m.json`, 110 cases, 2 batches with the default `--batch 60`, `--seed 1`)

1. **Data register = base register** (run 2 reached it only for some forms): every post/pre-increment load and store
   (`ld.*.{pi,pin,pre,prer}`, `st.*`, `.l` and 16-bit), 64-bit forms with the base as the even and as the odd register
   of the pair, alternating the sign of the increment. Settles which value a store keeps / a load leaves in the
   register in every form and the 64-bit store question above. (`st.h.hi.pi.l` uses an increment of 0x10000 so that the
   stored high half changes; for the other `st.h.hi` modes old and new base have the same high half, so they cannot
   tell.)
2. **Increment register = destination or base** (`ld.{w,bu,hs,bs,hu,d}.pi.l` with the increment register as the
   destination, for `d` also the odd one; `ld.w/ld.d/st.w/st.d/st.b/st.h.hi.pi.l` with increment = base): whether the
   addition uses the old or the loaded/updated value.
3. **`testset.b`, 32 cases** first in the file: addresses picked from batch 0's pattern so that the old byte is 0x00,
   0xFF and every low nibble 0..15 (with the flags before 0 or 0xF alternately). Confirms "psr = old & 15" for all
   16 values and that 0x00 and 0xFF behave. The picks depend on the batch's pattern, i.e. on running with the
   default `--batch 60` and `--seed 1` (otherwise they are still arbitrary old bytes, just not directed).
4. **One deliberate reset, last in the file**: `r5 = [npc + 0]` with `"misalign": true` (instruction at 2 mod 4). If npc
   is `pc + 4` the address is misaligned and the chip resets (run it last or alone: it kills the rest of its batch).
   If it does not reset, npc is word-aligned and the value tells which: the word at pc + 2 (`(pc + 4) & ~3`) or at
   pc + 6 (end of the 6-byte instruction rounded down). One case decides; no `[npc + 2]` is needed. After it, change
   `npc()` in `m2.py` accordingly.

## Not covered

Misaligned halfword/word accesses; `npc` offsets beyond the batch's code; atomicity of `testset.b` and the read-modify-write
forms; the docs (`ISA.md` "npc not yet known", `COMPILER.md` "flags of the memory forms unknown", `GAPS.md`) still carry the
old statements and are left to the merge.
