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
- Images are built with this repository's assembler and linker only, for RAM slot `0x01C28000`..`0x01C30000`
  (M-Flasher's flash loader uses `0x01C20000` or `0x01C28000`; the runner replaces it until the unit is
  power-cycled). Nothing is written to flash.

## Waves

| Wave | What | Risk |
| --- | --- | --- |
| `selftest` | `nop`, `r = r`, `+`, `-`, `<<`, a constant | checks the runner itself; run first |
| `1` | 306 register-only integer forms: arithmetic, logic, shifts, multiplies, bit operations, DSP, constants, register moves | none expected: no memory, stack, `sp`, special registers or control flow |
| `fpu` | 24 floating-point forms | the FPU may need enabling before use (Felucca's start-up code may do it); if they hang, that is the finding |
| `2` | 22 forms: integer division, `div.f`, and the instruction-revision-3 forms (`popcnt`, `sum`, `sat8`, `vsat16`, `unpack4`) | division by zero may trap; this chip may not implement revision 3 |

Each case sets the low four `psr` bits (the condition flags, [COMPILER.md](../../docs/COMPILER.md)) from its inputs.
If the self-test hangs, try `--flag-mask 0`, which leaves `psr` alone.

Not yet tested: memory forms, stack forms, parallel pairs (`#`), `rep` and `if` blocks, branches, special
registers, interrupts, locks and events; they need a runner that sets up memory and control state.

## Running

```sh
python3 tools/hwtest/gen.py /tmp/hw --wave selftest --per-entry 6
python3 tools/hwtest/gen.py /tmp/hw --wave 1
cd /tmp/hw && ./run-selftest.sh         # unit in USB download mode; needs M-Flasher's run-ram
python3 tools/hwtest/analyze.py /tmp/hw  # check the self-test before running wave 1
./run-1.sh
python3 tools/hwtest/analyze.py /tmp/hw --json results.json
```

A case that hangs the unit (a trap, a missing instruction) leaves the batch without an `.out` file: power-cycle,
note the batch, and split it (`--batch`) to find the case.
