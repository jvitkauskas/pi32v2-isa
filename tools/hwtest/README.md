# Hardware tests

Run single instructions on a real AC791N (an M-VAVE FM-1 or SMK-37) and record what they do: the evidence
for the table's meanings that JieLi's tools cannot give (docs/GAPS.md, "Meaning").

## How it works

- `runner.S` is a RAM plug-in for the chip's mask-ROM USB download mode, the same mechanism as M-Flasher's
  flash loader (m-bootloader `docs/SPEC.md` §10.1). The ROM calls its entry with three callbacks; it installs
  a command handler and returns. It answers two private commands and leaves everything else to the ROM:
  `FC60` runs every test case in the image, `FD61` sends a range of RAM back (the results).
- Each test case is the instruction under test as **raw bytes** (its exact encoding from the table), followed by
  `goto hw_exit`. The runner loads all sixteen registers and the low four `psr` bits from the case's inputs,
  enters the case, then pushes every register and reads `psr`, and copies them out.
- Every batch starts with two `nop` cases. Their outputs must be their inputs; `analyze.py` uses them to find the
  order the push stored the registers in, and refuses a batch where they do not agree.
- Images are built with this repository's assembler and linker only, for the flash loader's two RAM slots
  (`0x01C20000` and `0x01C28000`, 32 KiB each): consecutive batches alternate, so an upload never lands on the
  runner that is answering the ROM's commands. Start from a freshly powered unit in download mode (M-Flasher
  refuses to upload over its own running loader); the runner stays until the unit is power-cycled. Nothing is
  written to flash.

## Waves

| Wave | What | Risk |
| --- | --- | --- |
| `selftest` | `nop`, `r = r`, `+`, `-`, `<<`, a constant | checks the runner itself; run first |
| `1` | 306 register-only integer forms: arithmetic, logic, shifts, multiplies, bit operations, DSP, constants, register moves | none expected: no memory, stack, `sp`, special registers or control flow |
| `fpu` | 24 floating-point forms | the FPU may need enabling before use (Felucca's start-up code may do it); if they hang, that is the finding |
| `2` | 22 forms: integer division, `div.f`, and the instruction-revision-3 forms (`popcnt`, `sum`, `sat8`, `vsat16`, `unpack4`) | division by zero may trap; this chip may not implement revision 3 |
| `misc` | `csync`, `mov.r_sr` (reading every special register), the bit-field forms with a register operand | none seen |
| `stack` | pushes and pops (not pops into special registers), `sp += n`, `r = sp + n` | none seen |
| `mem` | loads, stores, read-modify-write, the DSP multiplies with memory operands, cache operations | six `mem2.hh.i` forms and misaligned word loads reset the chip ([run 2](../../hw/fm1-2026-10-24-v2/README.md)) |
| `branch` | pc-relative branches and calls, `goto r`, `call r`, `rts` | none seen |
| `3` | 12 vector compares with unnamed (`??`) conditions, which JieLi's assembler cannot write | **reset the FM-1** (hw/fm1-2026-10-24): the unit drops off USB and boots its app; put it back with `m-flasher download-mode` |

Each case sets the low four `psr` bits (the condition flags, [COMPILER.md](../../docs/COMPILER.md)) from its inputs.
If the self-test hangs, try `--flag-mask 0`, which leaves `psr` alone.

Since record format 2 each case also sets `sp` (inside a 1 KiB scratch that is reset to a known pattern before
every case) and `rets`, and the runner records `sp`, `rets`, the exit the stub took and the scratch words that
changed; that is what the `misc`, `stack`, `mem` and `branch` waves need. Blocks, loops and parallel pairs ran in
[run 3](../../hw/fm1-2026-10-24-v3/README.md); control and special-register probes are recorded in
[run 4](../../hw/fm1-2026-10-24-v4/README.md). Consult that report for completed and pending tests.

## Running

```sh
python3 tools/hwtest/gen.py /tmp/hw --wave selftest --per-entry 6
python3 tools/hwtest/gen.py /tmp/hw --wave 1 --first-slot 0x01C20000
cd /tmp/hw && ./run-selftest.sh         # a freshly powered unit in USB download mode; needs M-Flasher's run-ram
python3 tools/hwtest/analyze.py /tmp/hw  # check the self-test before running wave 1
./run-1.sh
python3 tools/hwtest/analyze.py /tmp/hw --json results.jsonl
```

`gen.py` prints the slot of each wave's last batch. To run waves one after another without a power cycle, start
the next wave in the other slot (`--first-slot`); otherwise its first upload would land on the runner that is
answering the ROM. Results of real runs are kept under [hw/](../../hw/).

On the desktop, `tools/hwtest/runstep.sh DIR WAVE` runs the generated script one batch at a time with the
installed `/opt/m-flasher/m-flasher`. It bounds flasher and USB checks, refuses a slot equal to
`/tmp/hw/LASTSLOT`, and stops on a hang. Only an observed app identity after a failure triggers
`download-mode` and continuation. After a confirmed manual power cycle, clear that slot marker before
resuming; otherwise preserve it. A hang requires a power cycle and operator confirmation, even if USB
still enumerates. Keep batches outside the desktop's `/tmp` if a reboot may be needed.

### As an application

The same batches can run as an FM-1 application instead ([APP.md](APP.md)): installed in flash, up to nine
batches, each at its own RAM base, results read back from download mode. This writes the flash's application
area; make a backup first and restore it afterwards.

```sh
python3 tools/hwtest/gen.py /tmp/app --wave 1 --per-entry 2 --batch 82 --app
python3 tools/hwtest/fm1app.py /tmp/app/app.fwsc tools/hwtest/app/driver.S /tmp/app/app.S
python3 tools/hwtest/fm1app.py /tmp/app/reset.bin tools/hwtest/app/reset.S --plugin 0x01C28000
m-flasher firmware /tmp/app/app.fwsc --yes             # the unit in download mode
m-flasher run-ram /tmp/app/reset.bin --addr 0x01C28000 # starts the application; it times out, as it should
# the application runs its batches and comes back in download mode (a second or so)
m-flasher run-ram RUNNER.bin --addr 0x01C20000 --read 0x01C30000:0x50000 -o ram.bin   # any runner image for that slot
python3 tools/hwtest/analyze.py /tmp/app --ram ram.bin@0x01C30000 --json results.jsonl
```

For handlers, watchdog recovery and timer gating, use the optional experiment profile described in
[APP.md](APP.md#steps-3–4-experiment-profile). `appcollect.py` excludes unfinished batches from instruction
results; `appverify.py` checks trap tags and timing-dependent counter relations. These observations and
ordinary numerical instruction models are complementary.

## Checking meanings

`check.py RESULTS.jsonl` runs every case through an executable model of its form (`semantics/*.py`, interface
in `check.py`) and lists the forms whose hardware results differ. To test particular inputs, write them as a
JSON list of `{"id", "values" (raw field values), "in" (16 registers), "flags"}` and build batches with
`gen.py OUTDIR --cases FILE.json --first-slot ...`.

Cases may also supply `sp` and `rets` (numbers or symbols), `misalign` (start the tested instruction at
2 mod 4), `taken` (aim a branch at the stub's taken exit), or exact `bytes` (which must decode as the given
entry and field values). `before` and `after` are lists of `{"id", "values"}` instructions for setup,
readback and restoration. They appear in the manifest and analyzed records; their effects are part of the
result. `entry`, when present, is where setup starts; `stub` is still the tested instruction's address.
For blocks, readback follows the generated then/else markers. An unconditional jump skips fall-through
readback, so return probes must explicitly target their restore sequence.

`model` optionally names a context model in `check.py`, overriding the form's ordinary model. It is carried
through the manifest and analysis without changing the image. An unknown name is reported as unmodeled;
this prevents a trap experiment's setup from being checked as if it were a bare instruction.

The optional `hw_probe_handler` in `runner.S` saves GPRs and flags, increments `hw_probe_seen`, records
icfg/reti/retx/rete and entry sp at `hw_probe_context+52..68`, then sets reti from `hw_probe_resume` and
tries `rti`. Nothing installs it automatically. Probes must save/restore their RAM vector pointers and core
state. Its presence does not establish the ROM's vector layout or exception-return convention.
Entries `hw_probe_handler_0`, `_1`, `_2` and `_120` first preserve r0/r1 and write that tag at
`hw_probe_context+72`, then join the same handler. The caller must install each at the intended RAM entry.
`hw_probe_handler_0_rete` also sets `hw_probe_context+76` to 1: the common handler then writes the
continuation to rete and returns with `rte`. Its default zero selects reti/rti. Run 5 found that both
debug forms returned captures with reti/rti but the following upload hung; rete/rte permitted subsequent
uploads in both slots. A capture alone is insufficient to establish a usable exception return.

`"force": true` permits a form outside the automatic waves and requires `--batch 1` (in addition to the
two calibration nops). It does not prove that a form is safe. Preserve the ROM's state around special-register
writes and keep all stack/store addresses in the allocated RAM. The generator verifies bytes and layout;
it cannot verify the effects of unknown instructions. See `cases_from_file` in `gen.py`.

A case that hangs the unit (a trap, a missing instruction) leaves the batch without an `.out` file: power-cycle,
note the batch, and split it (`--batch`) to find the case.
