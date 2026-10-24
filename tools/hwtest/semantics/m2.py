# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Format-2 models of the memory forms (hw/fm1-2026-10-24-v2; interface in check.py).

Built from the ids by `_spec`: ld/st, the size (b h w d), the extension of a load, the addressing mode
(offset, sp, register index, scaled index, post/pre-increment by a number or a register) and, for the
read-modify-write forms, the operation. The condition flags are never touched by these forms, except by `testset.b`.
"""
M = 0xFFFFFFFF
SIZE = {"b": 1, "h": 2, "w": 4, "d": 8}


def s32(x):
    x &= M
    return x - (1 << 32) if x >> 31 else x


class Writes:
    """Stores into the scratch, merged into words; words that end up unchanged are dropped."""

    def __init__(self, st):
        self.st, self.words = st, {}

    def put(self, addr, size, value):
        for k in range(size):
            a = (addr + k) & M
            wa, sh = a & ~3, (a & 3) * 8
            w = self.words.get(wa)
            if w is None:
                w = self.st.load(wa, 4)
            self.words[wa] = (w & ~(0xFF << sh)) | ((value >> (8 * k) & 0xFF) << sh)

    def result(self):
        return {a: v for a, v in self.words.items() if v != self.st.load(a, 4)}


def extend(v, size, signed):
    v &= (1 << (8 * size)) - 1
    if signed and v >> (8 * size - 1):
        v -= 1 << (8 * size)
    return v & M


SIXTEEN = {"ld.bu", "ld.hu", "ld.w", "st.b", "st.h", "st.w",
           "ld.bu.pi", "ld.hu.pi", "ld.w.pi", "st.b.pi", "st.h.pi", "st.w.pi",
           "ld.bu.pin", "ld.hu.pin", "ld.w.pin", "st.b.pin", "st.h.pin", "st.w.pin"}


def _spec(i):
    """(is_load, size, signed, hi, mode) from an id such as ld.hs.pin.l or st.h.hi.idxs."""
    p = i.split(".")
    size = SIZE[p[1][0]]
    rest = [x for x in p[2:] if x not in ("hi", "l")]
    return p[0] == "ld", size, p[1] in ("bs", "hs"), "hi" in p, rest[0] if rest else "off"


def _regs(i, load, mode, o):
    """(data register, base register, index or increment register) of a form."""
    if i in SIXTEEN:
        return o["d"], o["b"], o.get("i")
    if mode == "sp":
        return o["r"], None, None
    if mode in ("idx", "idxs", "pi", "prer"):
        return (o["r"], o["s"], o["t"]) if load else (o["t"], o["r"], o["s"])
    return (o["r"], o["s"], None) if load else (o["s"], o["r"], None)


def memop(i):
    load, size, signed, hi, mode = _spec(i)
    shift = {1: 0, 2: 1, 4: 2, 8: 3}[size]

    def f(R, fl, o, st):
        d, b, x = _regs(i, load, mode, o)
        base = st.sp if mode == "sp" else R[b]
        n = o.get("n", 0)
        new_base = None
        if mode in ("off", "sp"):
            addr = base + n
        elif mode == "idx":
            addr = base + R[x]
        elif mode == "idxs":
            addr = base + (R[x] << shift)
        elif mode in ("pi", "pin"):
            addr, new_base = base, base + (R[x] if mode == "pi" else n)
        else:                                            # pre, prer
            addr = new_base = base + (n if mode == "pre" else R[x])
        addr &= M
        regs = {}
        if new_base is not None:
            regs[b] = new_base & M
        if load:
            if size == 8:
                regs[d], regs[d + 1] = st.load(addr, 4), st.load(addr + 4, 4)
            else:
                regs[d] = extend(st.load(addr, size), size, signed)
            return {"regs": regs, "flags": fl}
        w = Writes(st)
        if size == 8:
            w.put(addr, 4, R[d])
            # the odd register of the pair is read after the base register was updated (all four modes, the even
            # register before it); hw/fm1-2026-10-24-v2/followup5-m.jsonl
            w.put(addr + 4, 4, regs.get(d + 1, R[d + 1]))
        else:
            w.put(addr, size, R[d] >> 16 if hi else R[d])
        return {"regs": regs, "mem": w.result(), "flags": fl}
    return f


MODELS = {}
for _i in open("/root/.t3/projects/pi32v2-isa-wt/ids5-m.txt").read().split():
    if _i.startswith(("ld.", "st.")) and not _i.startswith(("ld.w.npc", "st.w.modimm")):
        MODELS[_i] = memop(_i)


def st_w_modimm(R, fl, o, st):
    w = Writes(st)
    w.put(R[o["r"]] + o["n"], 4, o["m"])
    return {"mem": w.result(), "flags": fl}


MODELS["st.w.modimm"] = st_w_modimm


def _amount(v):
    return v & 0xFF


def _shift(kind, x, c):
    c = min(c, 32)
    if kind == "lsl":
        return (x << c) & M
    if kind == "lsr":
        return x >> c
    if kind == "asr":
        return (s32(x) >> c) & M
    v = max(-(1 << 31), min((1 << 31) - 1, s32(x) << c))      # shl3
    return v & M


OPS = {
    "add": lambda a, b: a + b, "sub": lambda a, b: a - b, "and": lambda a, b: a & b,
    "or": lambda a, b: a | b, "xor": lambda a, b: a ^ b,
}


def rmw(i):
    _, op, kind = i.split(".")

    def f(R, fl, o, st):
        addr = (R[o["r"]] + o["n"]) & M
        old = st.load(addr, 4)
        if kind in ("modimm", "nmodimm", "s12", "i"):
            b = o["m"]
        elif kind == "invr":
            b = ~R[o["s"]]
        elif kind in ("bitr", "invbitr"):
            b = 1 << (R[o["s"]] & 31)
            b = ~b if kind == "invbitr" else b
        else:
            b = R[o["s"]]
        if op in OPS:
            new = OPS[op](old, b)
        else:
            new = _shift(op, old, _amount(b))
        w = Writes(st)
        w.put(addr, 4, new & M)
        return {"mem": w.result(), "flags": fl}
    return f


for _i in open("/root/.t3/projects/pi32v2-isa-wt/ids5-m.txt").read().split():
    if _i.startswith("rmw."):
        MODELS[_i] = rmw(_i)


def testset_b(R, fl, o, st):
    """Sets the byte to 0xFF; the low four psr bits become the low four bits of the old byte."""
    addr = R[o["x"]]
    w = Writes(st)
    w.put(addr, 1, 0xFF)
    return {"mem": w.result(), "flags": st.load(addr, 1) & 0xF}


MODELS["testset.b"] = testset_b


# ---- npc-relative loads ------------------------------------------------------------------------------
# They read code, not the scratch. The model rebuilds the batch's code from the batch's own records: every
# stub is its case's bytes, then `goto hw_exit0` (a 4-byte goto.l to the runner's exit label, 0x220 bytes
# past the slot base), then zero padding to the next word boundary. The record is found by the case's
# sixteen input registers (random per case) in the result files under hw/.
import json
from pathlib import Path

HW = Path(__file__).resolve().parents[3] / "hw"
EXIT0 = 0x220
_index = {}


def _goto_exit(addr):
    base = addr & ~0x7FFF
    v = ((base + EXIT0 - addr) // 2) & 0x3FFFFF
    w = (0xEAC0 | v >> 16, v & 0xFFFF)
    return b"".join(x.to_bytes(2, "little") for x in w)


def _load_index():
    if _index:
        return
    for path in sorted(HW.glob("*/*.jsonl")):
        recs = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if not recs or "exit" not in recs[0]:
            continue
        batches = {}
        for r in recs:
            batches.setdefault(r["batch"], []).append(r)
        for rs in batches.values():
            code = {}
            for r in rs:
                b = bytes.fromhex(r["bytes"]) + _goto_exit(r["stub"] + len(r["bytes"]) // 2)
                for k, x in enumerate(b):
                    code[r["stub"] + k] = x
                if r.get("tgt"):
                    for k, x in enumerate(_goto_exit(r["tgt"])):
                        code[r["tgt"] + k] = x
            for a in range(min(code), max(code) + 4):          # the padding after the last goto
                code.setdefault(a, 0)
            for r in rs:
                _index[(tuple(r["in"]), r["flags_in"], r["stub"])] = (code, r)


def code_word(R, flags, st, addr):
    _load_index()
    code, rec = _index[(tuple(R), flags, st.stub)]
    if addr & 3:
        raise ValueError(f"misaligned word load at {addr:#x} (the chip resets)")
    if addr + 3 not in code or addr not in code:
        # Past the last stub is the batch's data (its case table and pattern): not reconstructed here, so the
        # value is taken from the record. Only the address is then unchecked (6 of the 28 run-2 reads).
        return rec["out"][_dest(rec)]
    return int.from_bytes(bytes(code[addr + k] for k in range(4)), "little")


def _dest(rec):
    return rec["values"]["r"]


def npc(stub):
    """What npc holds in an instruction at `stub`: pc + 4 rounded up to a word boundary. On a word boundary that
    is the address 4 bytes on (run 2); at 2 mod 4 the 6-byte ld.w.npc read pc + 6, not the misaligned pc + 4
    (followup5-m-npc.jsonl). Equivalent for that instruction: its end, rounded down. For the 4-byte ld.w.npc.r
    the two readings differ at 2 mod 4 (pc + 6 or pc + 2); only word-aligned stubs were run."""
    return (stub + 4 + 3) & ~3


def ld_w_npc(R, fl, o, st):
    return {"regs": {o["r"]: code_word(R, fl, st, (npc(st.stub) + o["n"]) & M)}, "flags": fl}


def ld_w_npc_r(R, fl, o, st):
    return {"regs": {o["r"]: code_word(R, fl, st, (npc(st.stub) + R[o["s"]]) & M)}, "flags": fl}


MODELS["ld.w.npc"] = ld_w_npc
MODELS["ld.w.npc.r"] = ld_w_npc_r
