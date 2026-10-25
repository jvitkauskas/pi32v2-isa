# FM-1, 2026-10-25: code compiled by the LLVM PI32V2 target

The first code from the LLVM backend ([docs/LLVM.md](../../docs/LLVM.md)) run on the unit (the same AC791N FM-1,
stock firmware 016, m-bootloader 1.2-22e2559). `tools/llvm/cgtest.ll` (integer arithmetic and division, all ten
compare conditions, shifts, constants, byte/half/word loads and stores, globals, a loop, recursion, six arguments,
values live across calls, 64-bit add/sub/shift, a switch, variadic calls including a 64-bit value split between
`r3` and the stack) was compiled with `llc -O2` (with the shorter forms), linked with the test application
`tools/hwtest/app/cgdriver.S` and installed over the application area with M-Flasher after a backup.

    python3 tools/llvm/cgtest.py build LLVM_BIN DIR      # then app.fwsc, reset.bin, reader.bin: tools/hwtest/runapp.sh
    python3 tools/llvm/cgtest.py check DIR RAM.bin@0x01C30000

The application ran once (`starts` 1), finished all 255 calls and returned to download mode by itself.
**All 255 calls returned the expected values** (computed in Python, `cgtest.py`); [results.json](results.json)
has each call. The same build gives the same results in the simulator (`tools/llvm/sim.py`).

Afterwards the backup taken just before was restored (M-Flasher: CRC32 of the flash verified) and the firmware
started with `app/reset.S`; the unit came back as `4c4a:c755` (FM-1).
