#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Run tools/llvm/ctest.c, compiled by the LLVM target's clang, on the FM-1.

    python3 tools/llvm/chwtest.py LLVM_BIN_DIR BUILTINS.a OUTDIR [--opt 2] [--cases 6]

Compiles ctest.c, links it with compiler-rt's builtins (tools/llvm/build_builtins.sh) and the test application
tools/hwtest/app/cgdriver.S, and writes OUTDIR/cgtest.fwsc and OUTDIR/tests.json as cgtest.py does, so that the
same run and `cgtest.py check` apply. The expected results are this build's results in the simulator
(tools/llvm/sim.py), which agree with JieLi's compiler (ctest.py): the hardware run checks that the chip does
what the simulator says.
"""
import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "hwtest"))
sys.path.insert(0, str(HERE))
import ctest  # noqa: E402
import fm1app  # noqa: E402
import sim  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("bin", type=Path)
    p.add_argument("builtins", type=Path)
    p.add_argument("outdir", type=Path)
    p.add_argument("--opt", default="2")
    p.add_argument("--cases", type=int, default=6)
    a = p.parse_args()
    out = a.outdir
    out.mkdir(parents=True, exist_ok=True)
    obj = out / "ctest.o"
    subprocess.run([str(a.bin / "clang"), "--target=pi32v2", f"-O{a.opt}", "-c", str(HERE / "ctest.c"), "-o",
                    str(obj)], check=True)
    rng = random.Random(1)
    calls = []
    for name, n, wide in ctest.functions():
        for args in ctest.inputs(n, a.cases, rng):
            calls.append((name, args + [0] * (4 - len(args)), wide))
    lines = ["\t.section .rodata", "\t.p2align 2", "\t.globl cg_tests", f"cg_tests:\t.4byte {len(calls)}"]
    lines += [f"\t.4byte {f}, " + ", ".join(f"{v:#x}" for v in args) for f, args, _ in calls]
    lines += ["\t.bss", "\t.p2align 2", "\t.globl cg_results", f"cg_results:\t.space {8 * len(calls)}", ""]
    table = out / "cgtable.S"
    table.write_text("\n".join(lines))
    image, entry, syms, elf = fm1app.build([HERE.parent / "hwtest" / "app" / "cgdriver.S", table, obj, a.builtins],
                                           out, 0x01C78000)
    (out / "cgtest.bin").write_bytes(image)
    elf.replace(out / "cgtest.elf")
    # the expected results: the same calls in the simulator, on this very image
    cpu = sim.CPU()
    s = cpu.load_elf((out / "cgtest.elf").read_bytes())
    tests = []
    for f, args, wide in calls:
        r0, r1 = cpu.call(s[f], args)
        tests.append((f, args, r0, r1 if wide else None))
    (out / "cgtest.fwsc").write_bytes(fm1app.package(fm1app.flash_image(image, entry, 0x980F), "FM-1_903"))
    (out / "tests.json").write_text(json.dumps({"results": syms["cg_results"], "tests": tests}))
    end = syms["cg_results"] + 8 * len(calls)
    print(f"{out / 'cgtest.fwsc'}: {len(calls)} calls, app.bin {len(image)} bytes; results at {syms['cg_results']:#x}"
          f"..{end:#x} ({cpu.steps} instructions in the simulator)")
    if end > 0x01C7C000:
        raise SystemExit("the results run into the record at 0x01C7C000: fewer --cases")


if __name__ == "__main__":
    main()
