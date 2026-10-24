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

## Follow-up for analyst P's forms

`followup-p.jsonl` (same record format, 308 records including the `nop` calibration cases) ran the 304 cases of
`hw/followup-p.json` on the same unit afterwards, in 2 batches, with no hang or trap and the calibration cases
returning their inputs. It targeted what the 12 random cases per form had not reached: zero, carry and overflow
results of the add and subtract forms, N and Z results of other forms, register shift counts with bits 8 and up set
and at the 32/64 boundaries, exact rounding ties of `shiftr.*` and `asr.ppi.rnd.vh`, bit fields running past bit 31,
`cls`/`clz` edge values and simple inputs for `popcnt.*`.
