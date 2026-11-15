#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Decode a boot probe record (src/) read back from 0x01C7C000.  bootprobe_decode.py REC.bin [REC2.bin]"""
import struct, sys

NAMES = ["nop", "add dep", "2 indep adds", "mov32", "ld", "ld+use", "st", "mul", "div", "fadd", "fdiv", "goto",
         "br not taken", "br taken", "call+goto+rts", "ld from XIP"]


def words(d, off, n):
    return struct.unpack_from(f"<{n}I", d, off)


def show(d):
    out = {}
    m, starts = words(d, 0, 2)
    out["magic"] = d[:4]
    out["starts"] = starts
    r = words(d, 8, 16)
    out["regs"] = " ".join(f"r{i}={v:08x}" for i, v in enumerate(r))
    sr = words(d, 72, 9)
    out["sregs"] = " ".join(f"{n}={v:08x}" for n, v in zip("sp ssp usp psr icfg rets reti rete retx".split(), sr))
    c, ec, em, dm, de = words(d, 108, 5)
    out["misc"] = f"ckcnt={c:08x} EMU_CON={ec:08x} EMU_MSG={em:08x} DBG_MSG={dm:08x} DBG_EN={de:08x}"
    out["fd80.."] = d[0x100:0x110]
    out["vectors 0..9 (fe00..)"] = " ".join(f"{v:08x}" for v in words(d, 0x180, 2)) + " | boot obj: " + \
        " ".join(f"{v:08x}" for v in words(d, 0x188, 6)) + " | header copy fe20: " + d[0x1a0:0x1c0].hex()
    out["at r0"] = d[0x200:0x240].hex()
    out["clock 0x10000"] = " ".join(f"{v:08x}" for v in words(d, 0x240, 16))
    out["SFC 0x40200"] = " ".join(f"{v:08x}" for v in words(d, 0x280, 4))
    out["SFCENC 0x40300"] = " ".join(f"{v:08x}" for v in words(d, 0x290, 6))
    out["ANA 0x11900"] = " ".join(f"{v:08x}" for v in words(d, 0x2c0, 64))
    out["corex2 0x1eee000"] = " ".join(f"{v:08x}" for v in words(d, 0x3c0, 8))
    out["0x1eee340"] = " ".join(f"{v:08x}" for v in words(d, 0x3e0, 8))
    out["PC limits"] = " ".join(f"{v:08x}" for v in words(d, 0x600, 4))
    t = words(d, 0x400, 34)
    base = t[1]
    out["timing (cold warm, per insn warm)"] = "\n    ".join(
        f"{n:16} {t[2*i+2]:6} {t[2*i+3]:6}  {(t[2*i+3]-base)/256:.2f}" for i, n in enumerate(NAMES)) + f"\n    empty: {t[0]} {t[1]}"
    return out


recs = [show(open(p, "rb").read()) for p in sys.argv[1:]]
for k in recs[0]:
    vals = [r[k] for r in recs]
    same = all(v == vals[0] for v in vals)
    print(f"## {k}{'' if len(vals) == 1 or same else '  (DIFFERS)'}")
    for v in (vals[:1] if same else vals):
        print(f"    {v}")
