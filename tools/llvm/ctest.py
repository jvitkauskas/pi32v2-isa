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
import struct
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


BUILTINS = None     # a library of compiler-rt's builtins for the LLVM build (--builtins)


def link(obj, workdir, libs=()):
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
    args = ["-T", str(script), str(obj), *map(str, libs), "-o", str(out)]
    if libs:                # helpers the library has are not stubs
        undef = [n for n in undef if n not in library_symbols(libs)]
        stubs = {STUBS + 16 * k: n for k, n in enumerate(undef)}
    args += [f"--defsym={n}={a:#x}" for a, n in stubs.items()]
    if ld.main(type("A", (), {"argv": args})()):
        raise SystemExit(f"link of {obj} failed")
    return out.read_bytes(), stubs


def library_symbols(libs):
    """The symbols an archive's members define (llvm-nm)."""
    out = set()
    for lib in libs:
        p = subprocess.run([str(Path(BIN) / "llvm-nm"), "--defined-only", "-g", str(lib)], capture_output=True,
                           text=True)
        out |= {ln.split()[-1] for ln in p.stdout.splitlines() if len(ln.split()) == 3}
    return out


BIN = None


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
    elif name.startswith("__sync_"):
        sync_helper(name, cpu)
    elif name in FLOAT_HELPERS:
        float_helper(name, cpu)
    elif name == "memcpy" or name == "memmove":
        cpu.mem.write(R[0], cpu.mem.read(R[1], R[2]))
    elif name == "memset":
        cpu.mem.write(R[0], bytes([R[1] & 0xFF]) * R[2])
    else:
        raise RuntimeError(f"library helper {name} is not in the simulator")


def sync_helper(name, cpu):
    """GCC's __sync_* functions on one core: old value back, the new one stored."""
    R = cpu.R
    m = re.fullmatch(r"__sync_(\w+)_([124])", name)
    if not m:
        raise RuntimeError(f"library helper {name} is not in the simulator")
    op, n = m.group(1), int(m.group(2))
    mask, bits = (1 << 8 * n) - 1, 8 * n
    old = int.from_bytes(cpu.mem.read(R[0], n), "little")
    v = R[1] & mask

    def s(x):
        return x - (1 << bits) if x >> (bits - 1) else x
    if op == "val_compare_and_swap":
        new = R[2] & mask if old == v else old
    else:
        new = {"fetch_and_add": old + v, "fetch_and_sub": old - v, "fetch_and_and": old & v,
               "fetch_and_or": old | v, "fetch_and_xor": old ^ v, "fetch_and_nand": ~(old & v),
               "fetch_and_max": old if s(old) > s(v) else v, "fetch_and_min": old if s(old) < s(v) else v,
               "fetch_and_umax": max(old, v), "fetch_and_umin": min(old, v), "lock_test_and_set": v}[op]
    cpu.mem.write(R[0], (new & mask).to_bytes(n, "little"))
    R[0] = old


def _f(bits):
    return struct.unpack("<f", struct.pack("<I", bits & M))[0]


def _fb(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]       # rounds to nearest, ties to even


def _d(lo, hi):
    return struct.unpack("<d", struct.pack("<II", lo & M, hi & M))[0]


def _db(x):
    return struct.unpack("<II", struct.pack("<d", x))


def _cmp(name, x, y):
    """libgcc's comparison helpers: <0, 0 or >0, and the unordered value per helper."""
    if x != x or y != y:
        return {"eq": 1, "ne": 1, "lt": 1, "le": 1, "gt": -1, "ge": -1, "unord": 1}[name]
    if name == "unord":
        return 0
    return -1 if x < y else (1 if x > y else 0)


def _toint(x, bits, signed):
    if x != x:
        return 0
    v = int(x)                                     # truncates toward zero
    lo, hi = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)
    return max(lo, min(hi, v))


FLOAT_HELPERS = set()
for _op in ("add", "sub", "mul", "div"):
    FLOAT_HELPERS |= {f"__{_op}sf3", f"__{_op}df3"}
for _c in ("eq", "ne", "lt", "le", "gt", "ge", "unord"):
    FLOAT_HELPERS |= {f"__{_c}sf2", f"__{_c}df2"}
FLOAT_HELPERS |= {"__fixsfsi", "__fixunssfsi", "__fixdfsi", "__fixunsdfsi", "__fixsfdi", "__fixdfdi",
                  "__fixunssfdi", "__fixunsdfdi", "__floatsisf", "__floatunsisf", "__floatsidf", "__floatunsidf",
                  "__floatdisf", "__floatdidf", "__floatundisf", "__floatundidf", "__extendsfdf2", "__truncdfsf2"}


def float_helper(name, cpu):
    """IEEE helpers in Python: single precision through double, then rounded (exact for + - * /)."""
    import operator
    R = cpu.R
    ops = {"add": operator.add, "sub": operator.sub, "mul": operator.mul,
           "div": lambda x, y: x / y if y else (float("nan") if x == 0 or x != x else
                                               (float("inf") if (x > 0) == (str(y)[0] != "-") else -float("inf")))}
    m = re.fullmatch(r"__(add|sub|mul|div)(sf|df)3", name)
    if m:
        op = ops[m.group(1)]
        if m.group(2) == "sf":
            R[0] = _fb(op(_f(R[0]), _f(R[1])))
        else:
            R[0], R[1] = _db(op(_d(R[0], R[1]), _d(R[2], R[3])))
        return
    m = re.fullmatch(r"__(eq|ne|lt|le|gt|ge|unord)(sf|df)2", name)
    if m:
        x, y = (_f(R[0]), _f(R[1])) if m.group(2) == "sf" else (_d(R[0], R[1]), _d(R[2], R[3]))
        R[0] = _cmp(m.group(1), x, y) & M
        return
    m = re.fullmatch(r"__fix(uns)?(sf|df)(si|di)", name)
    if m:
        x = _f(R[0]) if m.group(2) == "sf" else _d(R[0], R[1])
        v = _toint(x, 32 if m.group(3) == "si" else 64, not m.group(1))
        R[0], R[1] = v & M, (v >> 32) & M
        return
    m = re.fullmatch(r"__float(un)?(si|di)(sf|df)", name)
    if m:
        v = R[0] if m.group(2) == "si" else R[0] | R[1] << 32
        bits = 32 if m.group(2) == "si" else 64
        if not m.group(1) and v >> (bits - 1):
            v -= 1 << bits
        if m.group(3) == "sf":
            from fractions import Fraction
            R[0] = _fb(float(Fraction(v))) if abs(v) < (1 << 53) else _round_single(v)
        else:
            R[0], R[1] = _db(float(v))
        return
    if name == "__extendsfdf2":
        R[0], R[1] = _db(_f(R[0]))
    elif name == "__truncdfsf2":
        R[0] = _fb(_d(R[0], R[1]))


def _round_single(v):
    """An integer of more than 53 bits to single precision, rounded once (to nearest, ties to even)."""
    neg, v = v < 0, abs(v)
    shift = v.bit_length() - 24
    q, r = divmod(v, 1 << shift)
    half = 1 << (shift - 1)
    if r > half or (r == half and q & 1):
        q += 1
    return _fb((-1 if neg else 1) * float(q * (1 << shift)))


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
    for m in re.finditer(r"^(int|i64) ([fgl]_\w+)\(([^)]*)\)", text, re.M):
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
    p.add_argument("--builtins", type=Path, action="append", default=[],
                   help="libraries linked into the LLVM build: libclang_rt.builtins and libpi32v2 for pi32v2 "
                        "(tools/llvm/build_builtins.sh); repeatable")
    a = p.parse_args()
    global BIN
    BIN = a.bin
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
            builds["llvm"] = link(lobj, d, a.builtins)
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
