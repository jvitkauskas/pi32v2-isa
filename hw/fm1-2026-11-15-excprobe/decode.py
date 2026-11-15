#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Print excprobe's group 13 and 14 readbacks (0x01C70000, read with a run-ram reader) as text.

    python3 decode.py x2 excprobe-g13-x2.bin      # 20 words a run: r0..r15, psr, traps, EMU_MSG, the instruction
    python3 decode.py x14 excprobe-g14-x14.bin    # 40 words a run: r0..r15, psr, traps, EMU_MSG, DBG_MSG, then up to
                                                  # 10 (address, value) scratch words that changed

The inputs come from src/x2_cases.h and src/x14_cases.h.
"""
import re
import struct
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"


def arrays(header):
    text = (SRC / header).read_text()
    out = {}
    for name, body in re.findall(r"(\w+)\[[^\]]*\](?:\[[^\]]*\])?\s*=\s*\{(.*?)\};", text, re.S):
        nums = [int(x.rstrip("uU"), 0) for x in re.findall(r"0x[0-9a-fA-F]+u?|\d+u?", body)]
        out[name] = nums
    return out


def main():
    kind, path = sys.argv[1], sys.argv[2]
    data = Path(path).read_bytes()
    if kind == "x2":
        a = arrays("x2_cases.h")
        insns = [a["x2_insn"][4 * i:4 * i + 4] for i in range(len(a["x2_insn"]) // 4)]
        sets = [a["x2_sets"][16 * i:16 * i + 16] for i in range(len(a["x2_sets"]) // 16)]
        n = 0
        for c, insn in enumerate(insns):
            for s, regs in enumerate(sets):
                w = struct.unpack_from("<20I", data, 80 * n)
                changed = " ".join(f"r{k} {regs[k]:08x}->{w[k]:08x}" for k in range(16) if w[k] != regs[k])
                print(f"{bytes(insn).hex(' ')} set {s}: psr {w[16]:x} traps {w[17]} emu {w[18]:x} | {changed or 'no register changed'}")
                n += 1
    else:
        a = arrays("x14_cases.h")
        insns = [a["x14_insn"][4 * i:4 * i + 4] for i in range(len(a["x14_insn"]) // 4)]
        regs = a["x14_regs"]
        for n, insn in enumerate(insns):
            w = struct.unpack_from("<40I", data, 160 * n)
            changed = " ".join(f"r{k} {regs[k]:08x}->{w[k]:08x}" for k in range(16) if w[k] != regs[k] and k != 2)
            r2 = "r2 +1 ran" if w[2] == (regs[2] + 1) & 0xFFFFFFFF else f"r2 {regs[2]:08x}->{w[2]:08x}"
            mem = " ".join(f"[{w[20 + 2 * m]:08x}]={w[21 + 2 * m]:08x}" for m in range(10) if w[20 + 2 * m])
            print(f"{bytes(insn).hex(' ')}: psr {w[16]:x} traps {w[17]} emu {w[18]:x} dbg {w[19]:x} | {r2} "
                  f"{changed} {('mem ' + mem) if mem else ''}".rstrip())


if __name__ == "__main__":
    main()
