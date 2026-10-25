#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Assemble files with llvm-mc (the PI32V2 target) and with this repo's assembler and compare the objects:
section contents, sizes, relocations and symbol values (not the file layout, which differs).

    python3 tools/llvm/check_objs.py LLVM_BIN_DIR [FILE.s | FILE.c]... [--c-flags -O2] [--show N]

Without files: tests/asm/*.s, and tests/corpus/*.c compiled to assembly by JieLi's clang (the oracle, if it is
under oracle/) at -O0, -O2 and -Os. The repo's assembler writes the same objects as JieLi's (docs/ELF.md), so
agreeing with it is agreeing with JieLi's.
"""
import argparse
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from pi32v2isa import asm, elf, oracle  # noqa: E402

MATTR = "-mattr=+instrev3,+fprev1"
LAYOUT = ("section order", "symbol order", "header:")


def jieli_asm_source(c_file, flags):
    """JieLi's clang -S output for a C file, or None (a hard timeout: the oracle can hang)."""
    o = oracle.Oracle()
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "c.s"
        cmd = [str(o.clang), "-target", "pi32v2", f"-mcpu={oracle.CPU}", *flags, "-S", str(c_file), "-o", str(out)]
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            p.wait(timeout=60)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            return None
        return out.read_text() if p.returncode == 0 and out.exists() else None


def compare(mc, text, name, include):
    with tempfile.TemporaryDirectory() as d:
        src, obj = Path(d) / "in.s", Path(d) / "llvm.o"
        src.write_text(text)
        p = subprocess.run([str(mc), "-triple=pi32v2", MATTR, "-filetype=obj", *[f"-I{i}" for i in include],
                            "-o", str(obj), str(src)], capture_output=True, text=True, timeout=120)
        try:
            mine = asm.assemble_source(text, name, [str(i) for i in include])
        except asm.AsmError as e:
            return None, [f"pi32v2isa refuses it: {e}"]
        if p.returncode:
            return False, [f"llvm-mc: {ln}" for ln in p.stderr.strip().splitlines()[:6]]
        diffs = oracle.diff_objects(oracle._describe(elf.read(mine)), oracle._describe(elf.read(obj.read_bytes())))
        diffs = [x for x in diffs if not x.startswith(LAYOUT)]
        return not diffs, diffs


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("bin", type=Path)
    p.add_argument("files", type=Path, nargs="*")
    p.add_argument("--show", type=int, default=4)
    a = p.parse_args()
    mc = a.bin / "llvm-mc"
    jobs = []
    files = a.files or sorted((ROOT / "tests" / "asm").glob("*.s"))
    for f in files:
        if f.suffix == ".c":
            for flags in (["-O0"], ["-O2"], ["-Os"]):
                jobs.append((f"{f.name} {flags[0]}", f, flags))
        else:
            jobs.append((f.name, f, None))
    if not a.files and (ROOT / "oracle").exists():
        for f in sorted((ROOT / "tests" / "corpus").glob("*.c")):
            for flags in (["-O0"], ["-O2"], ["-Os"]):
                jobs.append((f"{f.name} {flags[0]}", f, flags))
    good = bad = skipped = 0
    for label, f, flags in jobs:
        text = jieli_asm_source(f, flags) if flags else f.read_text()
        if text is None:
            skipped += 1
            continue
        ok, diffs = compare(mc, text, str(f), [f.parent])
        if ok is None:
            skipped += 1
            continue
        if ok:
            good += 1
        else:
            bad += 1
            print(f"{label}:")
            for x in diffs[:a.show]:
                print("   ", x)
    print(f"{good} files agree, {bad} differ, {skipped} skipped (refused by pi32v2isa or not compiled)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
