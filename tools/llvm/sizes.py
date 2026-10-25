#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Code size of the LLVM PI32V2 target against JieLi's compiler, function by function.

    python3 tools/llvm/sizes.py LLVM_BIN_DIR [--opt s] [FILE.c...] [--top 20]

Each C file (default: tools/llvm/ctest.c and tests/corpus/*.c) is compiled by both; a function's size is its
symbol's st_size, or the distance to the next symbol of its section. Prints the totals, the functions where the
two differ most, and with --dump NAME both disassemblies of one function.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
from pi32v2isa import oracle  # noqa: E402


def functions(obj):
    """{name: size} of the STT_FUNC symbols of an object."""
    out = subprocess.run([str(BIN / "llvm-readobj"), "--symbols", str(obj)], capture_output=True, text=True,
                         check=True).stdout
    syms, cur = {}, {}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Symbol {"):
            cur = {}
        elif ":" in line:
            k, v = line.split(":", 1)
            cur[k.strip()] = v.strip()
        elif line == "}" and cur.get("Type", "").startswith("Function"):
            syms[cur["Name"].split(" ")[0]] = int(cur["Size"])
    return syms


def compile_both(src, opt, d, mcpu):
    jl = oracle.Oracle()
    j, m = Path(d) / (src.stem + ".jieli.o"), Path(d) / (src.stem + ".llvm.o")
    subprocess.run([str(jl.clang), "-target", "pi32v2", f"-mcpu={oracle.CPU}", f"-O{opt}", "-c", str(src), "-o",
                    str(j)], check=True, capture_output=True)
    subprocess.run([str(BIN / "clang"), "--target=pi32v2", f"-mcpu={mcpu}", f"-O{opt}", "-c", str(src), "-o", str(m)], check=True,
                   capture_output=True)
    return j, m


def main():
    global BIN
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("bin", type=Path)
    p.add_argument("files", type=Path, nargs="*")
    p.add_argument("--opt", default="s")
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--dump", help="disassemble this function from both builds")
    p.add_argument("--mcpu", default=oracle.CPU, help="the LLVM build's -mcpu (default: JieLi's)")
    a = p.parse_args()
    BIN = a.bin
    files = a.files or [HERE / "ctest.c", *sorted((ROOT / "tests/corpus").glob("*.c"))]
    rows, tj, tm = [], 0, 0
    with tempfile.TemporaryDirectory() as d:
        for f in files:
            try:
                j, m = compile_both(f, a.opt, d, a.mcpu)
            except subprocess.CalledProcessError as e:
                print(f"{f.name}: {e.stderr.decode(errors='replace')[:200]}", file=sys.stderr)
                continue
            fj, fm = functions(j), functions(m)
            for name in sorted(set(fj) & set(fm)):
                rows.append((f.name, name, fj[name], fm[name]))
                tj += fj[name]
                tm += fm[name]
            if a.dump and a.dump in fj and a.dump in fm:
                for tag, o in (("JieLi", j), ("LLVM", m)):
                    print(f"== {tag}")
                    out = subprocess.run([str(BIN / "llvm-objdump"), "-dr", f"--disassemble-symbols={a.dump}",
                                          str(o)], capture_output=True, text=True).stdout
                    print("\n".join(out.splitlines()[5:]))
    print(f"{len(rows)} functions: JieLi {tj} bytes, LLVM {tm} bytes ({100 * (tm - tj) / max(tj, 1):+.1f}%)")
    for f, n, sj, sm in sorted(rows, key=lambda r: r[2] - r[3])[:a.top]:
        print(f"  {sm - sj:+5d}  {sj:5d} {sm:5d}  {f}:{n}")


if __name__ == "__main__":
    main()
