# FM-1 test application, 2026-10-24: retention probe and harness check

The first two steps of [APP.md](../../tools/hwtest/APP.md), on the same AC791N FM-1 as the other runs (stock
firmware 016, m-bootloader 1.2-22e2559, chip key `0x980F`). Both applications were built with this repository's
assembler and linker only ([fm1app.py](../../tools/hwtest/fm1app.py)) and installed with M-Flasher
`firmware` over the application area (the boot area was not written). A backup of the whole flash was made
first. Each was started from download mode with [app/reset.S](../../tools/hwtest/app/reset.S) (a RAM plug-in
that clears the download-mode marker and soft-resets), and the RAM was read back with `run-ram --read` and a
runner image in `0x01C20000`.

## Step 1: retention probe

[app/probe.S](../../tools/hwtest/app/probe.S), 304 bytes, one flash sector. It ran once (`starts` = 1),
filled twelve areas with `address XOR 0x5AA5F00F`, wrote the download-mode marker and reset; the unit came
back in download mode on its own. [probe.json](probe.json) has the record and the counts.

- **Every word survived** the software reset, the ROM's download-mode entry and the upload of the reader:
  `0x01C0C000..0x01C1FFFF` (three 4 KiB samples), `0x01C30000..0x01C78FFF` (seven samples),
  `0x01C7C080..0x01C7CFFF` and `0x01C7F000..0x01C7F7FF`. The test application can keep its results anywhere
  there.
- **The ROM clears the marker**: the 16 bytes at `0x01C7FD80` read zero afterwards, so a later reset boots
  normally.
- **State at application entry** (m-bootloader 1.2): `r0` = `0x01C7FE08` (the boot object, SPEC §6.5),
  `sp` = `0x01C07BC8`, `ssp` = `0x01C06BC8`, `usp` = `0x01C01114`, `psr` = 0, `icfg` = `0x02050500`,
  `rets` = `0x01C04D46` (in the bootloader), `reti` = `0x01C02070` (the bootloader's own continuation after
  its `rti`, SPEC §4.1), `rete` = `retx` = 0.

## Step 2: harness check

[app/driver.S](../../tools/hwtest/app/driver.S) with eight batches of `gen.py --wave 1 --per-entry 2 --batch 82
--seed 1 --app` (the register-only forms, two random cases each, plus two calibration nops per batch): 74,904
bytes, 19 sectors. The application copied each batch to its own RAM base (`0x01C30000 + 0x8000 k`), ran it
through the unchanged `runner.S` (its entry and FC60 handler called as the ROM calls them), and returned to
download mode; its record shows 8 batches finished, none left running.

[results.jsonl](results.jsonl) (634 records, format 2) and [patterns.json](patterns.json):

    python3 tools/hwtest/analyze.py DIR --ram RAM.bin@0x01C30000 --json results.jsonl
    python3 tools/hwtest/check.py hw/fm1-2026-10-24-app/results.jsonl

Every calibration nop gave back its inputs (the push order is the usual one), and **309 of 309 modelled entries
match on every case**, registers, flags, sp, rets, exit and scratch: the models built from the download-mode
runs predict the application's results exactly. The one unmodelled entry is `copex.ppi` (hidden state,
`hw/fm1-2026-10-24-v5`). So the application environment runs the cases as download mode does, and the hand-over
(results in RAM, download mode, read-back) works.

The unit was left in download mode with the harness application installed; it goes straight back to download mode
at every start until a firmware is restored (`m-flasher restore BACKUP.bin`, or `m-flasher firmware` with a
package).
