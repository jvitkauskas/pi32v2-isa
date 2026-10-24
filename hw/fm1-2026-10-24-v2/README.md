# FM-1 hardware run 2, 2026-10-24: memory, stack, branches

The second run of [tools/hwtest](../../tools/hwtest/README.md) on the same M-VAVE FM-1 (JieLi AC791N, USB
download mode, M-Flasher 0.6.0 `run-ram`), with the runner's record format 2: each case also sets `sp` and
`rets`, starts with a 1 KiB scratch reset to a known pattern, and records `sp`, `rets`, which exit its stub took
and the scratch words that changed. Nothing was written to flash.

- `results.jsonl`: one JSON object per case, as in [run 1](../fm1-2026-10-24/README.md), plus `sp_in`, `sp_out`,
  `rets_in`, `rets_out`, `exit` (0: fell through to the end of the stub, 1: reached the stub's own taken label or
  `hw_taken`), `mem` (`{address: value}` of the scratch words that differ from the pattern afterwards, at most 16),
  `mem_count` (how many differ), `stub`, `tgt` (the stub's taken label), `hw_taken`, `scratch`.
- `patterns.json`: each batch's scratch pattern (256 words). The words from `sp_in` up (17 of them) hold
  `hw_taken`, so a popped `pc` lands there; the word at `sp_in - 4` holds the stub address when the case starts.
  The runner's exit pushes the registers into the 16 words below the final `sp`; changes there are not recorded.

Every case: address registers point into the scratch (two regions, `scratch + 0x100` and `+ 0x200`, each ± 32),
index registers are small (-8..16), offsets at most 0x80 (0x40 next to `sp`), `sp_in = scratch + 0x380`,
`rets_in = hw_taken`; branches are aimed at their stub's taken label, right after the stub's 4-byte
`goto hw_exit0`; `goto r`/`call r` registers hold `hw_taken`. Stubs start on a word boundary (except the
first batches, built before `.p2align 2` was added: the `ld.w.npc` cases of `memfix` and later are aligned).

How it was made (table and tools at the commit that adds this directory):

```sh
python3 tools/hwtest/gen.py DIR --wave selftest --per-entry 6 --first-slot 0x01C28000
python3 tools/hwtest/gen.py DIR --wave misc   --first-slot 0x01C20000   # 1 batch
python3 tools/hwtest/gen.py DIR --wave stack  --first-slot 0x01C28000   # 6
python3 tools/hwtest/gen.py DIR --wave mem    --first-slot 0x01C28000   # 40
python3 tools/hwtest/gen.py DIR --wave branch --first-slot 0x01C28000   # 20
```

The self-test was 38/38, and every `nop` case left `sp`, `psr`, the scratch and the exit alone. All batches
completed except four memory batches, which reset the unit (it dropped off USB and booted its app; it was put
back in download mode with `m-flasher download-mode`). Run case by case:

- `madd.mem2.hh.i.{u,s}`, `msub.mem2.hh.i.{u,s}`, `mul.mem2.hh.i.{u,s}` (two halfword memory operands with
  immediate increments) reset the chip in every case, also with both increments 0 and aligned addresses. The
  `hw.i`, `ww.i` and `.rh` two-operand forms run. `gen.py` now leaves the six out (`RESETS`).
- `ld.w.npc` reset the chip with offsets 2 and 6 (`r5 = [npc + 2]`), and ran with 0, 4, 8 and -4: a misaligned
  word load. With the stub on a word boundary, `[npc + 0]` read the word at the stub address + 4.

The cases of those batches that do not reset were run again as `batch-memfix-*` (with 12 new `ld.w.npc` cases,
offsets multiples of 4), and the single-case probes as `batch-bis-*`; both are in `results.jsonl`.

`followup5-d.jsonl` records the 336 cases from `hw/followup5-d.json` for all 54 runnable memory
DSP multiply forms, plus 12 calibration nops. It targeted arithmetic and carry/no-borrow boundaries,
halfword-aligned loads, independent signed high/low-halfword increments, and operand/pointer/result
overlaps, including shared bases and the `.hh.rh` second-load width. All six batches completed without
a reset; calibration passed. All 55 modelled entries match every case. Scratch patterns are in
`followup5-d.patterns.json`, read alongside `patterns.json` by `check.py`.

Analyst B's `followup5-b.jsonl` records 435 cases from `hw/followup5-b-run.json` plus 16 nop calibrations
in eight batches, all completed without a reset; calibration passed. Its scratch patterns are in
`followup5-b.patterns.json`. The 399 boundary/NaN/flag/decrement probes agree with the branch models. The
additional 12 cases each of `call.l`, `goto.l` and `call.xl` cover forms omitted by the original generator's
wide-offset solver: all take the target, calls save the next instruction address (`stub + 4` / `stub + 6`),
and `goto.l` preserves `rets`. All 451 records match, including preserved N/Z/C/V. See
[the analyst B report](../report5-b.md) for the evidence and remaining scope limits.

## Follow-up for the memory forms (analyst M, round 5)

`followup5-m.jsonl` (with `followup5-m.patterns.json`) holds the 109 cases of `hw/followup5-m-main.json`, built with the
default `--batch 60 --seed 1` (2 batches, no reset): `testset.b` on old bytes 0x00, 0xFF and every low nibble, the data
register equal to the base register in every pre/post-increment load and store (64-bit forms with the base as the even
and as the odd register), and post-increment loads whose increment register is the destination or the base.
`followup5-m-npc.jsonl` is `hw/followup5-m-npc.json`, one `ld.w.npc` with the stub at 2 mod 4, run alone: it did not
reset and read the word at the stub address + 6. Findings: `hw/report5-m.md`; models: `tools/hwtest/semantics/m2.py`.
