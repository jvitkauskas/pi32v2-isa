#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Differential test of the LLVM PI32V2 target against JieLi's compiler, in the simulator (tools/llvm/sim.py).

    python3 tools/llvm/ctest.py LLVM_BIN_DIR [--opt 2] [--cases 40] [--only-jieli]

tools/llvm/ctest.c is compiled by JieLi's clang (the oracle) and by LLVM_BIN_DIR/clang, each object linked alone
with this repo's linker; both run in the simulator on the same inputs (edge values and seeded random ones) and
every function's results must agree. Library helpers the compilers call (64-bit shifts, memcpy, ...) are done by
the simulator in Python. --only-jieli runs JieLi's build alone (to see that the simulator covers it).
"""
import argparse
import os
import random
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from pi32v2isa import elf, ld, oracle  # noqa: E402
import sim  # noqa: E402

M = 0xFFFFFFFF
M64 = (1 << 64) - 1
STUBS = 0x02100000          # library helpers: within reach of call.l from .text
EDGE = [0, 1, 2, 3, 7, 15, 16, 31, 32, 63, 100, 255, 256, 0x7FFF, 0x8000, 0xFFFF, 0x10000, 0x7FFFFFFF,
        0x80000000, 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFF00, 0x12345678, 0x87654321]


def run(cmd, timeout=120):
    """A command with a hard timeout (the oracle can hang); (status, stderr)."""
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
    try:
        _, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        return -1, b"timeout"
    return p.returncode, err


def link(obj, workdir):
    """obj linked alone at 0x02000000 (data at 0x01C40000); undefined symbols get stub addresses. (ELF bytes,
    {stub address: name})."""
    o = elf.read(Path(obj).read_bytes())
    undef = sorted({s.name for s in o.symbols if s.name and s.shndx == 0})
    stubs = {STUBS + 16 * k: n for k, n in enumerate(undef)}
    script = Path(workdir) / "sim.ld"
    script.write_text("""MEMORY { flash (rx) : ORIGIN = 0x02000000, LENGTH = 0x100000
         ram (rwx) : ORIGIN = 0x01C40000, LENGTH = 0x30000 }
SECTIONS {
  .text : { *(.text*) *(.rodata*) } > flash
  .data : { *(.data*) *(.sdata*) } > ram
  .bss : { *(.bss*) *(.sbss*) *(COMMON) } > ram
}
""")
    out = Path(workdir) / (Path(obj).stem + ".elf")
    args = ["-T", str(script), str(obj), "-o", str(out)] + [f"--defsym={n}={a:#x}" for a, n in stubs.items()]
    if ld.main(type("A", (), {"argv": args})()):
        raise SystemExit(f"link of {obj} failed")
    return out.read_bytes(), stubs


def helper(name, cpu):
    """A library helper, done in Python: sets r0 (and r1) like the real one."""
    R = cpu.R
    a64 = R[0] | R[1] << 32
    b64 = R[2] | R[3] << 32

    def s64(x):
        x &= M64
        return x - (1 << 64) if x >> 63 else x

    def ret64(v):
        R[0], R[1] = v & M, (v >> 32) & M
    if name == "__ashldi3":
        ret64(a64 << (R[2] & 63))
    elif name == "__lshrdi3":
        ret64(a64 >> (R[2] & 63))
    elif name == "__ashrdi3":
        ret64(s64(a64) >> (R[2] & 63))
    elif name == "__muldi3":
        ret64(a64 * b64)
    elif name in ("__udivdi3", "__umoddi3", "__divdi3", "__moddi3"):
        if name in ("__udivdi3", "__umoddi3"):
            q, r = divmod(a64, b64) if b64 else (0, 0)
        else:
            x, y = s64(a64), s64(b64)
            q = (abs(x) // abs(y)) * (1 if (x < 0) == (y < 0) else -1) if y else 0
            r = x - q * y
        ret64(q if "div" in name else r)
    elif name == "memcpy" or name == "memmove":
        cpu.mem.write(R[0], cpu.mem.read(R[1], R[2]))
    elif name == "memset":
        cpu.mem.write(R[0], bytes([R[1] & 0xFF]) * R[2])
    else:
        raise RuntimeError(f"library helper {name} is not in the simulator")


class StubCPU(sim.CPU):
    def __init__(self, stubs):
        super().__init__()
        self.stubs = stubs

    def step(self):
        if self.pc in self.stubs:
            helper(self.stubs[self.pc], self)
            self.pc = self.rets
            self.steps += 1
            return
        super().step()


def functions():
    """[(name, number of int arguments, returns long long)] from ctest.c."""
    text = (HERE / "ctest.c").read_text()
    out = []
    for m in re.finditer(r"^(int|i64) ([fl]_\w+)\(([^)]*)\)", text, re.M):
        args = [a for a in m.group(3).split(",") if a.strip() and a.strip() != "void"]
        out.append((m.group(2), len(args), m.group(1) == "i64"))
    return out


def inputs(n_args, cases, rng):
    out = [[EDGE[(k + j * 7) % len(EDGE)] for j in range(n_args)] for k in range(len(EDGE))]
    out += [[rng.choice(EDGE) if rng.random() < 0.3 else rng.getrandbits(32) for _ in range(n_args)]
            for _ in range(cases)]
    return out


def results(elf_bytes, stubs, tests):
    cpu = StubCPU(stubs)
    syms = cpu.load_elf(elf_bytes)
    out = []
    for name, args, wide in tests:
        try:
            r0, r1 = cpu.call(syms[name], args)
            out.append((r0, r1) if wide else (r0,))
        except RuntimeError as e:
            out.append(("stop", str(e)))
    return out, cpu.steps


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("bin", type=Path)
    p.add_argument("--opt", default="2")
    p.add_argument("--cases", type=int, default=40)
    p.add_argument("--only-jieli", action="store_true")
    a = p.parse_args()
    rng = random.Random(1)
    tests = []
    for name, n, wide in functions():
        for args in inputs(n, a.cases, rng):
            tests.append((name, args, wide))
    jl = oracle.Oracle()
    with tempfile.TemporaryDirectory() as d:
        builds = {}
        jobj = Path(d) / "jieli.o"
        code, err = run([str(jl.clang), "-target", "pi32v2", f"-mcpu={oracle.CPU}", f"-O{a.opt}", "-c",
                         str(HERE / "ctest.c"), "-o", str(jobj)])
        if code:
            raise SystemExit(f"JieLi's clang failed: {err.decode()[:500]}")
        builds["jieli"] = link(jobj, d)
        if not a.only_jieli:
            lobj = Path(d) / "llvm.o"
            code, err = run([str(a.bin / "clang"), "--target=pi32v2", f"-O{a.opt}", "-c",
                             str(HERE / "ctest.c"), "-o", str(lobj)])
            if code:
                raise SystemExit(f"clang failed: {err.decode()[:2000]}")
            builds["llvm"] = link(lobj, d)
        got = {}
        for k, (e, stubs) in builds.items():
            got[k], steps = results(e, stubs, tests)
            stops = sum(1 for r in got[k] if r[0] == "stop")
            print(f"{k}: {len(tests)} calls, {steps} instructions, {stops} stopped"
                  + (f" (first: {next(r[1] for r in got[k] if r[0] == 'stop')})" if stops else ""))
    if a.only_jieli:
        return 0
    bad = {}
    for t, x, y in zip(tests, got["jieli"], got["llvm"]):
        if x != y and x[0] != "stop":
            bad.setdefault(t[0], []).append((t[1], x, y))
    for name, cases in bad.items():
        print(f"DIFFER {name}: {len(cases)} cases, e.g. args {[hex(v) for v in cases[0][0]]}: "
              f"JieLi {[hex(v) if isinstance(v, int) else v for v in cases[0][1]]}, "
              f"LLVM {[hex(v) if isinstance(v, int) else v for v in cases[0][2]]}")
    agree = sum(1 for x, y in zip(got["jieli"], got["llvm"]) if x == y and x[0] != "stop")
    print(f"{agree}/{len(tests)} calls agree; {len(bad)} functions differ")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
