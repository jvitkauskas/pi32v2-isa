# FM-1, 2026-10-25: C compiled by the LLVM target's clang

`tools/llvm/ctest.c` (integer and 64-bit arithmetic, division, shifts, comparisons, tables and globals, loops,
recursion, a switch, six-argument calls, structs by value and returned, variadic calls, float and double
arithmetic, comparisons and conversions, 64-bit multiply and divide) compiled by `clang --target=pi32v2 -O2`,
linked with compiler-rt's builtins compiled by the same clang (`tools/llvm/build_builtins.sh`) and the test
application `tools/hwtest/app/cgdriver.S`, on the same unit as the other runs.

    python3 tools/llvm/chwtest.py LLVM_BIN BUILTINS.a DIR      # then tools/hwtest/runapp.sh, as cgtest
    python3 tools/llvm/cgtest.py check DIR RAM.bin@0x01C30000

The expected results are this build's results in the simulator (`tools/llvm/sim.py`), which agree with ctest.c
compiled by JieLi's clang (`tools/llvm/ctest.py`). The application ran once, finished all 960 calls and returned
to download mode: **all 960 calls gave the simulator's results** ([results.json](results.json)).

The backup taken just before was restored (CRC32 verified) and the firmware started; the unit came back as FM-1.
