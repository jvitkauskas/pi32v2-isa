# FM-1, 2026-10-25: an application from the open toolchain alone

`examples/fm1-blink` built with `-DAUTOTEST` by `clang --target=pi32v2 -O2` (C and the start-up code) and
`ld.lld`, packed by `tools/hwtest/fm1app.py --from-elf`; no JieLi tool, object or library. It sets up its stacks,
`.data` and `.bss`, drives the LED shift registers, starts TIMER5 at 100 Hz with its handler a C function
(`__attribute__((interrupt))`), counts 300 interrupts while TIMER4 counts the crystal, writes a record and
returns to download mode by itself.

    examples/fm1-blink/build.sh LLVM_BIN DIR -DAUTOTEST   # DIR/blink.fwsc, installed as app.fwsc
    tools/hwtest/runapp.sh RUNDIR                         # after a verified backup

Result ([results.json](results.json)): the record says 300 ticks in 72001202 crystal counts at 24 MHz:
3.00005 s for 300 periods. The 1202 counts over 72000000 are 300 × 4 + 2: a period is PRD + 1 = 60001 counts
of TIMER5's 6 MHz (4 crystal counts each), not 60000, and the rest is the loop's latency. (The run used
PRD 60000; the example now sets 59999.) So the interrupt was
taken every time, the C handler saved what it used, acknowledged the timer
and returned with `rti` to the loop, which kept running. The `ticks` variable in `.bss` reads 300 too.

Before the run, a backup was taken; afterwards it was restored (CRC32 verified) and the firmware started: the
unit came back as FM-1. The RAM dump stays on the desktop; it is not committed.
