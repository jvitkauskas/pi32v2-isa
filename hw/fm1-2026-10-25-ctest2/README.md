# FM-1, 2026-10-25: C from the size-tuned code generator, hardware float

`tools/llvm/ctest.c` as the second C run on this unit ([the first](../fm1-2026-10-25-ctest/README.md)), now compiled
by the code generator after the code-size work (LLVM fork 87cd98aa5, [LLVM.md](../../docs/LLVM.md), code size)
with `-mcpu=r3`, at -O2 and at -Os: 1140 calls each (the functions of the first run plus atomics, tail calls,
single-instruction idioms, JieLi's builtins and pointer walks), linked with compiler-rt's builtins and the
`__sync_*` runtime, both compiled by the same clang.

    python3 tools/llvm/chwtest.py LLVM_BIN BUILTINS.a DIR --opt 2 --lib libpi32v2.a    # then tools/hwtest/runapp.sh
    python3 tools/llvm/cgtest.py check DIR RAM.bin@0x01C30000

The images use, among the rest, `if (...) {` blocks (selects and short conditional code, `return` and `goto`
inside them), post-increment loads and stores, the `(f)` float forms, `iff` blocks, `itof`/`ftoi`, the carry
chain (`+ c`, `- !c`), the pair multiply, `clz`/`cls`/`rev8`/rotates, `uextra`/`sextra`, min/max, indexed
addressing, tail calls, and `lockset`/`lockclr` in the atomics.

Result ([results.json](results.json)): **all 1140 calls gave the simulator's results at -O2, and all 1140 at
-Os**; the simulator's results agree with ctest.c compiled by JieLi's clang (`tools/llvm/ctest.py`).

The backup taken just before (identical to the earlier ones) was restored (CRC32 verified) and the firmware
started; the unit came back as FM-1. The RAM dumps stay on the desktop.
