<!-- SPDX-FileCopyrightText: 2026 Julius Vitkauskas -->
<!-- SPDX-License-Identifier: CC0-1.0 -->

# Analyst K, round 5: stack, special-register and register-list forms

Worktree `k`, branch `hw2/k`. Evidence: `hw/fm1-2026-10-24-v2/results.jsonl`, 12 cases per form. Models in
`tools/hwtest/semantics/k2.py`. **All 34 assigned forms match on all 408 cases, flags included**
(`check.py ... --id` over the list: 34/34). Nothing was run on the hardware. `check.py` gained one line: `State.batch`
(the models of `reti` and `usp` need it, see below).

## Order of register lists

- **Push** (`push.rl`, `.rets_rl`, `.rmask`, `.rmask.c`, `.rets_rmask`, `.rets_rmask.c`, `.rets`, `.srl`, `.srmask`,
  `.srmask.c`): sp drops 4 per item; the lowest-numbered register goes to the lowest address, the highest to
  `[old sp - 4]`; `rets` is always the topmost word, above the general registers. Special registers go in number
  order (reti lowest ... pc highest). A list is therefore stored as r4, r5, ... r15, rets going up the memory.
- **Pop**: only the sp change (+4 per item) and the set of registers written were observable. Run 2's pop cases all read
  words holding `hw_taken` (the pattern fills them), so which word reaches which register, and which word is pc, is
  not shown. Models and notes assume the mirror of the push (ascending, pc/rets topmost); the compiler's prologue and
  epilogue pairs (`{rets, r5, r4}` ... `{pc, r5, r4}`) need exactly that. `rets` popped by `pop.rets_*` equals its old
  value in these cases, so a write to rets is not visible either. Follow-up below.
- **ldm/stm**: `post1 [r+]` words at base, base kept; `post2 [r++]` same words, base += 4n; `pre1 [-r]` words at
  base - 4n .. base - 4, base kept; `pre2 [--r]` same words, base -= 4n. Lowest-numbered register at the lowest
  address in all four. With the base in the list: a load leaves the base holding the loaded word (it beats the
  update); a store stores the old base value (and the update still happens). Before this run the three non-`post1`
  styles were "assumed from the syntax"; they are now confirmed.

## Special registers (`mov.r_sr`, and the `push.srmask` stores, which give the same values)

| sr | value in this context | kind |
| --- | --- | --- |
| `sp` (sr14) | the current sp (before a push's decrement) | program state |
| `pc` (sr15) | address of the instruction itself (push only; `mov.r_sr` not read) | program state |
| `rets` (sr3) | the rets set before the case | program state |
| `psr` (sr5) | the four flags in bits 3..0, everything else 0 (push only) | program state |
| `icfg` (sr11) | `0x01090700`, always | constant |
| `ssp` (sr13) | `0x01C00E00`, always (push only) | constant |
| `usp` (sr12) | `0x01C01180` (misc batch, stack-004) or `0x01C011A0` (stack-001) | state of the ROM, not a counter |
| `reti` (sr0) | `0x01E0168E` (misc, stack-004) or `0x01E00368` (stack-001) | state of the ROM, not a counter |
| `rete`, `retx`, `sr4`, `cnum`, `uspn`, `sspn`, `icfgn`, `icfgs` | 0 | zero in every case (cnum probably the core number, 0) |

`reti` and `usp` were constant over every case of a batch (a dozen reads each) and differ between batches, so they are
left-overs of the boot ROM's interrupt/stack state (reti looks like a ROM address, usp sits just above ssp), not
counters that run during a batch. None of the sixteen looks like a free-running counter. `mov.r_sr` itself was only run for
12 random registers (no psr, rete, rets, uspn, icfgs, ssp or pc read); `hw/followup5-k.json` reads all sixteen, four times each, plus
repeated reads of the suspicious ones.

## Flags

- Leave N Z C V alone: all push/pop/ldm/stm/sp-add/`r = sp + n`/`mov.r_sr`/`csync` cases.
- Bit fields (`insert/uextra/sextra .rrriirii`): N and Z follow the result, C and V kept (as the rrii forms).
- **Finding: a push that includes `psr` (`push.srl`, `push.srmask`, `.c`) leaves all four flags 0**, in all 19 such cases
  (flags 0001..1111 in); pushes without psr leave them alone. The pushed value is the flags before the push. Looks like
  "push and clear" (or a read side effect of psr); `mov.r_sr psr` was not run in run 2, so the follow-up asks whether reading
  psr by `mov.r_sr` clears them as well.

## Corrections (old claim -> hardware)

- `insert/uextra/sextra .rrriirii`: "meaning unknown beyond the syntax" -> same as the rrii forms with p = rt[12:8],
  l = rt[4:0] (summaries rewritten; the junk bits of rt were 0 in all cases: follow-up).
- `ldm.post2`, `ldm.pre1`, `ldm.pre2`, `stm.post2`, `stm.pre1`, `stm.pre2`: "increment style as printed" / "meaning assumed from
  the syntax" -> settled as above.
- `push.rmask.c`, `push.rets_rmask.c`, `push.srmask.c`: "meaning of c unknown" -> still unknown; words, sp and flags are
  identical to the plain forms in all 12 cases each (no observable difference).
- `push.srl`/`push.srmask`: gained the value table and the flag clearing; `mov.r_sr`: values; `csync`: no visible effect.
- Everything else: hardware source added, notes extended.

## Follow-up (`hw/followup5-k.json`, 265 cases, builds with gen.py into 5 batches)

1. Pop order: sp placed in the random part of the scratch (`hw_scratch+0x100`) so every popped word differs:
   `pop.rl`, `pop.rets_rl`, `pop.rmask`, `pop.rets_rmask` (also empty and full masks), `pop.pc` at the normal sp.
2. `mov.r_sr` of all sixteen special registers x four flag values, with other sp and rets values (including a literal
   rets), then 24 repeat reads of reti, usp, cnum, icfg, uspn, icfgn.
3. psr push: all 16 flag values through `push.srl {psr}`, the other forms, and empty and full masks of every push form.
4. sp arithmetic at the ends of the scratch, `r = sp + n` with 0, 127, 128, 4094, 4095 and r15.
5. ldm/stm of all four styles with an empty mask, full mask, base alone and r0 alone.
6. Bit fields with edge p and l (0, 31, l = 0, p + l > 32) and junk in bits 13..31 and 7..5 of rt, and aliasing of r, s, t.
7. Last (end of batch 004), 6 cases of `pop.pc_rl` / `pop.pc_rmask` with a window whose top word is `hw_taken` and whose lower
   words are random. If pc were taken from the lowest word the unit would jump into a random word and probably hang; the
   compiler's pairing makes that very unlikely, but run that batch last or split those six off.
No misaligned access is requested.

## Surprises

- Pushing psr clears the flags.
- reti and usp differ between batches while constant within one.
- `pc` pushed is the push instruction's own address, not the next one.
- (c) forms do nothing different that this setup can see.
