<!-- SPDX-FileCopyrightText: 2026 Julius Vitkauskas -->
<!-- SPDX-License-Identifier: CC0-1.0 -->

# Analyst K, round 5: stack, special-register and register-list forms

Worktree `k`, branch `hw2/k`. Evidence: `hw/fm1-2026-10-24-v2/results.jsonl` (12 cases per form), `followup5-k.jsonl` (259 cases) and `followup5-k-pc.jsonl` (6), 673 cases of the 34 forms in all. Models in
`tools/hwtest/semantics/k2.py`. **All 34 assigned forms match on every case of all three files, flags included** (`check.py ... --id` over the list: 34/34,
28/28 and 2/2). Nothing was run by me on the hardware. `check.py` gained `State.batch` (the models of `reti` and `usp` need it) and
now accepts a record whose 16 recorded scratch words are a truncation, as long as they agree with the model and the count is right
(a 16-register push plus the stub word changes 17). The lead's `patterns()` change is committed with it.

## Order of register lists (settled)

- **Push:** sp drops 4 per item; the lowest-numbered register goes to the lowest address, the highest to `[old sp - 4]`; `rets` is
  always the topmost word. Special registers go in number order (reti lowest ... pc highest). The `.c` forms store exactly the same
  words, sp and flags as the plain forms, also for empty and full masks: what c does is still unknown.
- **Pop:** with distinct words under sp (follow-up) the registers take consecutive words in ascending order of register number, lowest
  from the lowest address; `rets` and `pc` come from the topmost word. The pc order was tested alone (6 cases, lower words not
  addresses): execution continued at the topmost word every time. This is the exact mirror of the push, as the compiler's
  prologue/epilogue pairs and the runner's own `{rets, r15-r4}` / `{pc, r15-r4}` already needed.
- **ldm/stm:** `post1 [r+]` words at base, base kept; `post2 [r++]` same words, base += 4n; `pre1 [-r]` words at base - 4n .. base - 4,
  base kept; `pre2 [--r]` same words, base -= 4n; lowest-numbered register at the lowest address. Base in the list: a load leaves the
  loaded word in it (it beats the update); a store stores the old base value (the update still happens). Empty and full masks work.
- **New finding, `rets` is 27 bits wide:** a word popped into `rets` comes back as `word & 0x07FFFFFE` (0x81355c53 -> 0x01355c52,
  0x7c240d49 -> 0x04240d48, 0x5b569643 -> 0x03569642, 0x58989008 -> 0x00989008; 0x07295e42 unchanged). The runner's own write of
  `rets` before a case is cut the same way (literal 0x12345678 reads back 0x02345678). Bit 0 and bits 31..27 are not stored. Not tested
  for pc, reti, rete or retx.

## Special registers (mov.r_sr, all sixteen read 4 times each; pushes give the same values)

| sr | value | kind |
| --- | --- | --- |
| `sp` | the current sp (a push stores the value before its decrement) | program state |
| `pc` | the address of the reading instruction itself | program state |
| `rets` | what was set, cut to bits 26..1 | program state |
| `psr` | the flags in bits 3..0, the rest 0; reading does not change them | program state |
| `icfg` | `0x01090700` | constant |
| `ssp` | `0x01C00E00` | constant |
| `reti` | one of `0x01E00368`, `0x01E00E72`, `0x01E0168E`, `0x01E01674`, `0x01E01718`: fixed within a batch, different between batches | ROM state, not a counter |
| `usp` | `0x01C0117C`, `0x01C01180` or `0x01C011A0`, fixed within a batch | ROM state, not a counter |
| `rete`, `retx`, `sr4`, `cnum`, `uspn`, `sspn`, `icfgn`, `icfgs` | 0 in every read | zero |

Nothing counts during a batch (reti and usp were re-read up to 8 times per batch, and the batches' pushes agree). The simplest
reading is that the runner runs inside the ROM's download-command handler and reti/usp are the interrupted ROM context's address
and stack pointer at that time; this was not tested. The models carry a per-batch table of the observed reti/usp.

## Flags

- Leave N Z C V alone: all push/pop/ldm/stm/sp-add/`r = sp + n`/`mov.r_sr` (psr included)/`csync` cases.
- Bit fields (`insert/uextra/sextra .rrriirii`): N and Z follow the result, C and V kept. Bits of rt outside rt[12:8] and rt[4:0] are
  ignored; edge p/l and aliasing of r, s, t behave as in the rrii forms.
- **A push that includes `psr` leaves all four flags 0** (every such case, all 16 flag values; pushes without psr and reads of psr by
  `mov.r_sr` leave them alone). The pushed value is the flags before the push.

## Corrections (old claim -> hardware)

- `insert/uextra/sextra .rrriirii`: "meaning unknown beyond the syntax" -> the rrii operations with p = rt[12:8], l = rt[4:0].
- `ldm.post2`, `ldm.pre1`, `ldm.pre2`, `stm.post2`, `stm.pre1`, `stm.pre2`: "assumed from the syntax" -> confirmed as above.
- `push.rmask.c`, `push.rets_rmask.c`, `push.srmask.c`: "meaning of c unknown" -> still unknown; no observable difference.
- `pop.*`: order was assumed in the first pass -> settled by the follow-up; `pop.rets_*` notes gain the 27-bit cut.
- `push.srl`/`push.srmask`: value table, flag clearing; `mov.r_sr`: all values; `csync`: no visible effect. `docs/ISA.md`'s special-register
  table now has a column of what was seen.
- Hedge dropped from my first reading: reti/usp were "ROM state" in the first report; they are now documented as batch-constant, with
  the interrupted-context idea marked as untested.

## Follow-up

Done (none left). The follow-up of 265 cases (`hw/followup5-k.json`, run as `followup5-k-main.json` of 259 plus `followup5-k-pc.json` of 6)
answered the open questions: pop order, all sixteen special registers, psr read versus push, junk bits of rt, empty/full masks, sp
extremes. Remaining unknowns: what the (c) pushes change; whether pc/reti/rete/retx are cut like rets; why reti and usp differ between
batches.

## Surprises

- Pushing psr clears the flags; reading it does not.
- rets keeps only bits 26..1.
- reti and usp differ between batches while constant within one.
- `pc` read or pushed is the instruction's own address.
- (c) forms do nothing different that this setup can see.
