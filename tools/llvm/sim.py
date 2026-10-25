#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""A small pi32v2 simulator built on the instruction models fitted to the FM-1 (tools/hwtest/semantics), for
testing compiled code without the unit.

    python3 tools/llvm/sim.py OUTDIR            # the tests of cgtest.py build OUTDIR, run in the simulator

Each instruction is decoded with the table (pi32v2isa.codec) and its effect on registers, flags, sp, rets and
memory is the model's, the same models that agree with every hardware result in hw/. Control flow is the
simulator's own: a branch or call goes to the end of the instruction plus its displacement, call.r and goto.r to
the register, rts to rets, a pop into pc to the popped word. A form without a model stops the run.
"""
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "hwtest"))
from pi32v2isa import codec, table  # noqa: E402
from pi32v2isa.oracle import read_exec  # noqa: E402
import check  # noqa: E402

M = 0xFFFFFFFF
RETURN = 0x01C70000          # where a test call returns to: stops the run (survives rets' bits 26..1)
STACK_TOP = 0x01C7B000


class Memory:
    def __init__(self):
        self.pages = {}

    def _page(self, a):
        p = self.pages.get(a >> 12)
        if p is None:
            p = self.pages[a >> 12] = bytearray(4096)
        return p

    def read(self, a, n):
        return bytes(self._page(a + k)[(a + k) & 0xFFF] for k in range(n))

    def write(self, a, data):
        for k, b in enumerate(data):
            self._page(a + k)[(a + k) & 0xFFF] = b


class State:
    """What a model of a format-2 case gets (check.State), backed by the whole memory."""

    def __init__(self, cpu, pc, size, tgt):
        self.sp, self.rets, self.stub, self.end, self.tgt = cpu.sp, cpu.rets, pc, pc + size, tgt
        self.taken = 0xFFFFFFFF          # never a real return address: pops report the word themselves
        self.scratch, self.batch, self.rec = 0, "sim", {"text": ""}
        self.mem = cpu.mem

    def load(self, address, size=4):
        return int.from_bytes(self.mem.read(address & M, size), "little")


class CPU:
    def __init__(self):
        self.tab = table.load()
        self.models = check.load_models()
        self.mem = Memory()
        self.R = [0] * 16
        self.flags = 0
        self.sp = STACK_TOP
        self.rets = 0
        self.pc = 0
        self.steps = 0
        self.cache = {}
        self.after_then = None      # inside an if-block's then-part: [instructions left, else-part to skip]

    def load_elf(self, data):
        exe = read_exec(data)
        for s in exe["sections"]:
            if s["flags"] & 2 and s["addr"]:                 # allocated: at its address
                body = s["data"] if s["type"] == 1 else bytes(s.get("size", len(s["data"])))
                self.mem.write(s["addr"], body)
        return {name: value for name, value, *_ in exe["symbols"] if name}

    def decode(self, pc):
        got = self.cache.get(pc)
        if got is None:
            got = codec.decode(self.tab, self.mem.read(pc, 6))
            if got is None:
                raise RuntimeError(f"{pc:#x}: no instruction decodes here")
            self.cache[pc] = got
        return got

    def effect(self, insn, raw, pc, size, R):
        """The model's result for one instruction at pc on registers R (not applied)."""
        op = check.operands(insn, raw)
        model = self.models.get(insn.id)
        if model is None:
            raise RuntimeError(f"{pc:#x}: {insn.id} has no model")
        disp = op.get(branch_field(insn)) if branch_field(insn) else None
        tgt = pc + size + disp if disp is not None else None
        st = State(self, pc, size, tgt)
        try:
            if check.takes_state(model):
                return model(list(R), self.flags, op, st), op, tgt
            w, fl = model(list(R), self.flags, op)
        except (KeyError, ValueError) as e:      # a model that needs its hardware run's context
            raise RuntimeError(f"{pc:#x}: {insn.id}: its model needs the hardware run's context ({e})") from None
        return {"regs": w, "flags": fl}, op, tgt

    def pair(self, insn, raw, size):
        """`A #` then B (hw/fm1-2026-10-24-v3): B reads the registers as they were before A; when both write a
        register, A's result stays, except that a half A writes merges with what B loaded."""
        from semantics.v3 import half_mask
        base = self.tab.by_id(insn.id[:-2]) if insn.id.endswith(".p") else insn
        braw = raw
        if base is not insn:        # the twin's fields, by their place in the syntax, are the base form's
            tp, bp = table.placeholders(insn.syntax), table.placeholders(base.syntax)
            braw = dict(zip(bp, (raw[f] for f in tp)))
            braw.update({f: raw[f] for f in base.fields if f not in braw and f in raw})
        a_res, _, _ = self.effect(base, braw, self.pc, size, self.R)
        b_insn, b_raw, b_size = self.decode(self.pc + size)
        b_res, b_op, b_tgt = self.effect(b_insn, b_raw, self.pc + size, b_size, self.R)
        regs = dict(b_res.get("regs", {}))
        mask = half_mask(codec.format(insn, raw))
        for r, v in a_res.get("regs", {}).items():
            if mask is not None and r in regs:
                v = (regs[r] & ~mask) | (v & mask)
            regs[r] = v
        res = dict(b_res)
        res["regs"] = regs
        res["flags"] = a_res.get("flags", b_res.get("flags"))
        return res, b_insn, b_op, b_tgt, self.pc + size + b_size

    def skip(self, n):
        """Move pc past n instructions (a parallel pair is one)."""
        for _ in range(n):
            insn, _, size = self.decode(self.pc)
            self.pc += size
            if insn.id.endswith(".p"):
                self.pc += self.decode(self.pc)[2]

    def step(self):
        insn, raw, size = self.decode(self.pc)
        if self.after_then is not None:
            self.after_then[0] -= 1
        if insn.block:
            # if (...) { then } else { else }: t and e instructions after the opener (hw/fm1-2026-10-24-v3)
            op = check.operands(insn, raw)
            res, _, _ = self.effect(insn, raw, self.pc, size, self.R)
            taken = res.get("regs", {}).get(8) == 0x100
            self.pc += size
            self.steps += 1
            if taken:
                self.after_then = [op["t"], op["e"]]
            else:
                self.skip(op["t"])
            self.check_then()
            return
        if insn.id in ("tbb", "tbh"):
            # a table of bytes (halfwords) after the instruction, the register its byte offset (tbh: the case
            # number times 2): target = the instruction's end + 2 * entry (docs/COMPILER.md)
            op = check.operands(insn, raw)
            end = self.pc + size
            w = 1 if insn.id == "tbb" else 2
            entry = int.from_bytes(self.mem.read(end + self.R[op["x"]], w), "little")
            self.pc = end + 2 * entry
            self.steps += 1
            return
        if insn.id in ("push.srl", "pop.srl", "push.srmask", "pop.srmask"):
            self.special_list(insn, raw, size)
            self.check_then()
            return
        self.step1(insn, raw, size)
        self.check_then()

    def special_list(self, insn, raw, size):
        """Push or pop special registers: register n at the n-th lowest address (as the run-4 model,
        tools/hwtest/semantics/v4.py). Only rets (3), psr (5, its flags) and pc (15, a return) are kept here."""
        mask = raw.get("m", raw.get("n"))
        regs = [k for k in range(16) if mask >> k & 1]
        if insn.id.startswith("push"):
            vals = {3: self.rets, 5: self.flags}
            self.sp -= 4 * len(regs)
            for k, r in enumerate(regs):
                if r not in vals:
                    raise RuntimeError(f"{self.pc:#x}: push of special register {r}")
                self.mem.write(self.sp + 4 * k, struct.pack("<I", vals[r] & M))
            self.pc += size
        else:
            a = self.sp
            new_pc = self.pc + size
            for r in regs:
                v = self.mem_word(a)
                a += 4
                if r == 3:
                    self.rets = v & 0x07FFFFFE            # rets keeps bits 26..1 (hw/fm1-2026-10-24-v2)
                elif r == 5:
                    self.flags = v & 0xF
                elif r == 15:
                    new_pc = v & 0xFFFFFFFE
                else:
                    raise RuntimeError(f"{self.pc:#x}: pop of special register {r}")
            self.sp = a
            self.pc = new_pc
        self.steps += 1

    def check_then(self):
        if self.after_then is not None and self.after_then[0] <= 0:
            e = self.after_then[1]
            self.after_then = None
            self.skip(e)

    def step1(self, insn, raw, size):
        if insn.id.endswith(".p"):
            res, b_insn, b_op, tgt, end = self.pair(insn, raw, size)
            before = list(self.R)
            self.apply(res)
            if b_insn.id.startswith("pop.pc"):
                self.pc = self.mem_word(self.sp - 4) & 0xFFFFFFFE
            else:
                self.pc = end
            self.steps += 1
            return
        before = list(self.R)
        res, op, tgt = self.effect(insn, raw, self.pc, size, self.R)
        for r, v in res.get("regs", {}).items():
            self.R[r] = v & M
        if res.get("flags") is not None:
            self.flags = res["flags"] & 0xF
        for a, v in res.get("mem", {}).items():
            a = int(a, 16) if isinstance(a, str) else a
            self.mem.write(a, struct.pack("<I", v & M))
        old_sp = self.sp
        self.sp = res.get("sp", self.sp) & M
        self.rets = res.get("rets", self.rets) & M
        end = self.pc + size
        i = insn.id
        if i in ("rts",):
            self.pc = self.rets
        elif i.startswith("pop.pc"):
            self.pc = self.mem_word(self.sp - 4) & 0xFFFFFFFE
        elif i in ("call.r", "goto.r"):
            self.pc = before[op["x"]]
        elif tgt is not None:
            self.pc = tgt if res.get("exit") else end
        else:
            self.pc = end
        self.steps += 1

    def mem_word(self, a):
        return int.from_bytes(self.mem.read(a & M, 4), "little")

    def apply(self, res):
        for r, v in res.get("regs", {}).items():
            self.R[r] = v & M
        if res.get("flags") is not None:
            self.flags = res["flags"] & 0xF
        for a, v in res.get("mem", {}).items():
            a = int(a, 16) if isinstance(a, str) else a
            self.mem.write(a, struct.pack("<I", v & M))
        self.sp = res.get("sp", self.sp) & M
        self.rets = res.get("rets", self.rets) & M

    def call(self, address, args, limit=2_000_000):
        self.R[:len(args)] = [a & M for a in args]
        self.rets = RETURN
        self.pc = address
        start = self.steps
        while self.pc != RETURN:
            self.step()
            if self.steps - start > limit:
                raise RuntimeError("too many steps")
        return self.R[0], self.R[1]


def branch_field(insn, _cache={}):
    if insn.id not in _cache:
        from pi32v2isa import asm
        _cache[insn.id] = asm.branch_field(insn)
    return _cache[insn.id]


def main():
    out = Path(sys.argv[1])
    meta = json.loads((out / "tests.json").read_text())
    cpu = CPU()
    syms = cpu.load_elf((out / "cgtest.elf").read_bytes())
    bad = 0
    for f, args, e0, e1 in meta["tests"]:
        try:
            r0, r1 = cpu.call(syms[f], args)
        except RuntimeError as e:
            bad += 1
            print(f"STOP {f}({', '.join(hex(a) for a in args)}): {e}")
            continue
        if r0 != e0 or (e1 is not None and r1 != e1):
            bad += 1
            print(f"FAIL {f}({', '.join(hex(a) for a in args)}): got {r0:#x} {r1:#x}, expected {e0:#x}"
                  + (f" {e1:#x}" if e1 is not None else ""))
    n = len(meta["tests"])
    print(f"{n - bad}/{n} tests give the expected result in the simulator ({cpu.steps} instructions)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
