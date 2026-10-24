# FM-1 hardware run, 2026-10-24

The first run of [tools/hwtest](../../tools/hwtest/README.md) on a real chip: Julius Vitkauskas's M-VAVE FM-1
(JieLi AC791N), in USB download mode (it enumerated as `4c4a:8057`), driven from a Linux desktop with
M-Flasher 0.6.0 `run-ram`. Nothing was written to flash.

`results.jsonl` holds one JSON object per case: `batch`, entry `id`, `bytes` (the encoding run), `text`, field
`values`, `in` (r0..r15 before), `flags_in` (the low four `psr` bits set before), `out` (r0..r15 after),
`psr_out` (the whole `psr` after) and `changed` (the registers that differ).

How it was made, from table and tools at commit 18d67d8 plus `--first-slot` (each wave continues the slot
alternation of the one before, so the unit ran all waves without a power cycle):

```sh
python3 tools/hwtest/gen.py DIR --wave selftest --per-entry 6
python3 tools/hwtest/gen.py DIR --wave 1   --first-slot 0x01C20000
python3 tools/hwtest/gen.py DIR --wave fpu --first-slot 0x01C28000
python3 tools/hwtest/gen.py DIR --wave 2   --first-slot 0x01C28000
# run-selftest.sh, run-1.sh, run-fpu.sh, run-2.sh on the unit, in that order
python3 tools/hwtest/analyze.py DIR --json results.jsonl
```

All 26 batches (4312 cases, 353 forms, seed 1) completed: none hung or trapped, including division by zero
and the instruction-revision-3 forms. Every batch's `nop` cases gave back their inputs, with the registers in
stack slots 0..15 in order r0..r15, and the self-test was 38/38 as expected. Upper `psr` bits (4..31) read 0
after every case.

`followup-q.jsonl` records analyst Q's controlled follow-up: 351 instruction cases
targeting minimum-integer abs/negs, per-lane accumulator overflow, saturation and
shift boundaries, lane comparisons, and `copex` inputs/controls, plus four `nop`
calibration cases. The lead built it with
`python3 tools/hwtest/gen.py DIR --cases hw/followup-q.json --first-slot 0x01C28000`.
Both batches completed without a hang, and their calibration cases passed.

`followup-q2.jsonl` records analyst Q's second controlled follow-up: 272 `copex`
cases covering all low-five-bit controls, upper control masks, previous destination
values and overlapping pairs, plus 12 matched old/revision-3 unpack cases and four
`nop` calibration cases (288 records total). The lead ran `hw/followup-q2.json`
in two batches; neither hung, and both batches' calibration cases passed. All 284
instruction records match the requested inputs and fields. The `copex` mode-15
results leave previous destination versus internal state/history dependence
unresolved; see [report-q.md](../report-q.md). No further `copex` follow-up is
requested.

`followup-s.jsonl` records analyst S's 400 targeted cases from `hw/followup-s.json`, plus 16 calibration
`nop`s (416 records). It targets float rounding, NaNs/infinities/subnormals, multiply-accumulate fusion,
conversion boundaries, and integer division by zero/overflow. The lead split the cases into 308 non-division
float cases and 92 division cases (including 12 `div.f`), built both parts with `gen.py --cases`, and built
the division part with `--batch 16`: two float batches and six division batches. Every batch calibrated;
nothing hung or trapped, including every division by zero. Check it with
`python3 tools/hwtest/check.py hw/fm1-2026-10-24/followup-s.jsonl`.

`followup-s2.jsonl` records all 208 cases from `hw/followup-s2.json`, plus four calibration `nop`s
(212 records, two batches). It separates NaN sign, quiet/signalling class and payload in arithmetic,
conversions, min/max and comparisons, and checks invalid/overflowed products before accumulation.
Both batches calibrated; nothing hung or trapped. Check it with
`python3 tools/hwtest/check.py hw/fm1-2026-10-24/followup-s2.jsonl`.
