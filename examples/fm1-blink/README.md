# fm1-blink: an FM-1 application from the open toolchain alone

The PLAY LED blinks once a second, timed by a 100 Hz TIMER5 interrupt whose handler is C
(`__attribute__((interrupt))`); holding PLAY for two seconds puts the unit in USB download mode. Nothing of
JieLi's is used: `clang --target=pi32v2` compiles the C and the start-up code, `ld.lld` links them with
`fm1.ld`, and `tools/hwtest/fm1app.py --from-elf` makes the `.fwsc` package M-Flasher installs.

    examples/fm1-blink/build.sh LLVM_BIN_DIR OUT              # OUT/blink.fwsc
    examples/fm1-blink/build.sh LLVM_BIN_DIR OUT -DAUTOTEST   # the self-checking variant

| File | What |
| --- | --- |
| `crt0.S` | the entry m-bootloader calls (0x02000120): interrupts off, the application's stacks, `.data` copied, `.bss` cleared, `main` |
| `fm1.ld` | code and constants in the flash window, data and stacks in RAM 0x01C40000..0x01C7C000 |
| `blink.c` | GPIO, the LED shift registers, the PLAY key, TIMER5 and its interrupt, download mode |
| `build.sh` | the build |

The hardware facts (pins, timers, the interrupt controller, the download-mode marker) are from fm1-base and
m-bootloader's SPEC, used as facts only, and from this repo's hardware runs (`hw/`).

The `AUTOTEST` variant counts 300 ticks (3 s), then writes `BLNK`, the tick count, the TIMER4 crystal count over
those ticks and the port A outputs to 0x01C7C000 and goes to download mode by itself, so a host can read the
record back (`tools/hwtest/runapp.sh`) and check that the interrupt ran at 100 Hz: 72000000 crystal ticks, give
or take one tick period.
