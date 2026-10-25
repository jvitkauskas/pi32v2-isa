#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Run code compiled by the LLVM PI32V2 target on the FM-1 and compare its results with the expected ones.

    python3 tools/llvm/cgtest.py build LLVM_BIN_DIR OUTDIR [--opt 2]
    python3 tools/llvm/cgtest.py check OUTDIR RAM.bin@ADDRESS

build: llc compiles tools/llvm/cgtest.ll; the test application (tools/hwtest/app/cgdriver.S) calls each test
function with the arguments below and keeps r0 and r1; fm1app.py packs it into OUTDIR/cgtest.fwsc. Install it,
start it (app/reset.S), and when the unit is back in download mode read OUTDIR's results range (printed by build)
with m-flasher run-ram --read. check: compares that dump with the expected results, computed here in Python.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "hwtest"))

M = 0xFFFFFFFF


def s32(x):
    x &= M
    return x - (1 << 32) if x >> 31 else x


def tdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


WORDS = [1, -2, 300, -40000, 5, 6000000, 7, -8]
BYTES = [1, -2, 127, -128, 5, 200 - 256, 7, -8]
HALVES = [1, -2, 32767, -32768]


def sum6(a, b, c, d, e, f):
    return a + 10 * b + 100 * c + 1000 * d + 10000 * e + 100000 * f


def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)


def tests():
    """[(function, [r0..r3], expected r0, expected r1 or None)]"""
    out = []
    pairs = [(7, 5), (-7, 5), (5, -7), (0x80000000, 1), (M, M), (123456, -789), (0, 0x7FFFFFFF)]
    for a, b in pairs:
        A, B = s32(a), s32(b)
        out.append(("t_add", [a, b], A + B))
        out.append(("t_sub", [a, b], A - B))
        out.append(("t_mul", [a, b], A * B))
        if B:
            if not (A == -(1 << 31) and B == -1):
                out.append(("t_sdiv", [a, b], tdiv(A, B)))
                out.append(("t_srem", [a, b], A - tdiv(A, B) * B))
            out.append(("t_udiv", [a, b], (a & M) // (b & M)))
            out.append(("t_urem", [a, b], (a & M) % (b & M)))
        x = ((A & B) | 4096) ^ B
        out.append(("t_logic", [a, b], (x & 255) | A))
        for name, f in (("t_eq", A == B), ("t_ne", A != B), ("t_ult", (a & M) < (b & M)),
                        ("t_ule", (a & M) <= (b & M)), ("t_ugt", (a & M) > (b & M)),
                        ("t_uge", (a & M) >= (b & M)), ("t_slt", A < B), ("t_sle", A <= B),
                        ("t_sgt", A > B), ("t_sge", A >= B)):
            out.append((name, [a, b], int(f)))
        out.append(("t_max", [a, b], max(A, B)))
    for a in (0x12345678, s32(0x87654321), 1, -1):
        for n in (0, 1, 7, 31):
            out.append(("t_shl", [a, n], a << n))
            out.append(("t_lshr", [a, n], (a & M) >> n))
            out.append(("t_ashr", [a, n], s32(a) >> n))
        out.append(("t_shimm", [a], ((a << 5) + ((a & M) >> 27)) ^ (s32(a) >> 3)))
        out.append(("t_const", [a], ~(a + 305419896 - 8000)))
    for n in range(9):
        out.append(("t_sum_words", [n], sum(WORDS[:n])))
    for i in range(8):
        out.append(("t_sbyte", [i], BYTES[i]))
        out.append(("t_ubyte", [i], BYTES[i] & 0xFF))
    for i in range(4):
        out.append(("t_shalf", [i], HALVES[i]))
        out.append(("t_uhalf", [i], HALVES[i] & 0xFFFF))
    for a in (0x11223344, s32(0xA5B6C7D8)):
        w0 = (a & 0xFF) << 8
        w1 = (a & 0xFFFF) << 16
        out.append(("t_stores", [a], w0 ^ w1))
    total = 0
    for a in (5, 7, -20):
        total += a
        out.append(("t_counter", [a], total))
    for n in (0, 1, 2, 10, 15):
        out.append(("t_fib", [n], fib(n)))
    for x, y in ((1, 5), (-3, 9)):
        out.append(("t_call6", [x, y], sum6(x, 2, 3, 4, y, 6)))
    for x in (0, 3, -100):
        v = sum6(x + 1, x + 2, x + 3, x + 4, x + 5, x + 6)
        v = ((((v + x + 7) * (x + 8)) + x + 9) ^ (x + 10)) + x + 11 - (x + 12) + x + 13
        out.append(("t_pressure", [x], v))
    for a, b in ((0xFFFFFFFF, 1), (0x123456789, 0xFEDCBA987), (1 << 63, 1 << 63)):
        r = (a + b) & ((1 << 64) - 1)
        out.append(("t_add64", [a & M, a >> 32, b & M, b >> 32], r & M, r >> 32))
        r = (a - b) & ((1 << 64) - 1)
        out.append(("t_sub64", [a & M, a >> 32, b & M, b >> 32], r & M, r >> 32))
        r = (a << 13) & ((1 << 64) - 1)
        out.append(("t_shl64", [a & M, a >> 32], r & M, r >> 32))
    for x, r in ((0, 100), (1, -200), (7, 70000), (3, 9), (-1, 9)):
        out.append(("t_switch", [x], r))
    return [(f, [v & M for v in args] + [0] * (4 - len(args)), e & M, (rest[0] & M) if rest else None)
            for f, args, e, *rest in out]


def build(a):
    import fm1app
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    obj = out / "cgtest.o"
    subprocess.run([str(Path(a.bin) / "llc"), f"-O{a.opt}", "-filetype=obj", str(HERE / "cgtest.ll"), "-o", str(obj)],
                   check=True)
    subprocess.run([str(Path(a.bin) / "llc"), f"-O{a.opt}", str(HERE / "cgtest.ll"), "-o", str(out / "cgtest.s")],
                   check=True)
    ts = tests()
    lines = ["\t.section .rodata", "\t.p2align 2", "\t.globl cg_tests", f"cg_tests:\t.4byte {len(ts)}"]
    lines += [f"\t.4byte {f}, " + ", ".join(f"{v:#x}" for v in args) for f, args, _, _ in ts]
    lines += ["\t.bss", "\t.p2align 2", "\t.globl cg_results", f"cg_results:\t.space {8 * len(ts)}", ""]
    table = out / "cgtable.S"
    table.write_text("\n".join(lines))
    image, entry, syms, elf = fm1app.build([HERE.parent / "hwtest" / "app" / "cgdriver.S", table, obj], out,
                                           0x01C78000)
    (out / "cgtest.bin").write_bytes(image)
    elf.replace(out / "cgtest.elf")
    pkg = fm1app.package(fm1app.flash_image(image, entry, 0x980F), "FM-1_902")
    (out / "cgtest.fwsc").write_bytes(pkg)
    (out / "tests.json").write_text(json.dumps({"results": syms["cg_results"], "tests": ts}))
    print(f"{out / 'cgtest.fwsc'}: {len(ts)} tests, app.bin {len(image)} bytes; "
          f"results at {syms['cg_results']:#x}, {8 * len(ts)} bytes; record at 0x01C7C000")


def check(a):
    import struct
    out = Path(a.outdir)
    meta = json.loads((out / "tests.json").read_text())
    path, at = a.ram.rsplit("@", 1)
    ram, at = Path(path).read_bytes(), int(at, 0)
    rec = struct.unpack_from("<4I", ram, 0x01C7C000 - at) if at <= 0x01C7C000 < at + len(ram) else None
    if rec:
        print(f"record: magic {rec[0]:#x}, starts {rec[1]}, calls finished {rec[2]}, running {rec[3]}")
    base = meta["results"] - at
    bad = 0
    for k, (f, args, e0, e1) in enumerate(meta["tests"]):
        r0, r1 = struct.unpack_from("<II", ram, base + 8 * k)
        if r0 != e0 or (e1 is not None and r1 != e1):
            bad += 1
            print(f"FAIL {f}({', '.join(hex(v) for v in args)}): got {r0:#x} {r1:#x}, expected {e0:#x}"
                  + (f" {e1:#x}" if e1 is not None else ""))
    n = len(meta["tests"])
    print(f"{n - bad}/{n} tests give the expected result")
    return 1 if bad else 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("bin")
    b.add_argument("outdir")
    b.add_argument("--opt", default="2")
    c = sub.add_parser("check")
    c.add_argument("outdir")
    c.add_argument("ram")
    a = p.parse_args()
    return build(a) if a.cmd == "build" else check(a)


if __name__ == "__main__":
    sys.exit(main())
