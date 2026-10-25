# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Models of the arithmetic, logic, shift, bit, constant and move forms (analyst P; see check.py).

Every form matched hw/fm1-2026-10-24 on all 12 cases, flags included. Condition flags (psr bits 3..0) are
N, Z, C, V; see _p_util.py and docs/COMPILER.md ("64-bit arithmetic and the flags") for who writes which."""
from semantics._p_util import *  # noqa: F401,F403

MODELS = {}


def model(*ids):
    def deco(fn):
        for i in ids:
            MODELS[i] = fn
        return fn
    return deco


def _val(R, o, k):
    return o[k] if k in ("n", "m") else R[o[k]]


# add: rd = a + b; N Z C V all written
def _add(dst, a, b):
    def f(R, fl, o):
        r, c, v = add_full(_val(R, o, a), _val(R, o, b))
        return {o[dst]: r}, arith_flags(r, c, v)
    return f


MODELS["add.rrr.l"] = _add("r", "s", "t")
MODELS["add.rr"] = _add("d", "d", "s")
MODELS["add.rri"] = _add("d", "s", "n")
MODELS["add.modimm.rri"] = _add("r", "s", "n")
MODELS["add.s14.rri"] = _add("r", "s", "n")
for _i in ("add.ri.neg7", "add.ri.u5", "add.ri.u5_hi", "add.ri.u6_hi"):
    MODELS[_i] = _add("r", "r", "n")


def _sub(dst, a, b):
    def f(R, fl, o):
        r, c, v = sub_full(_val(R, o, a), _val(R, o, b))
        return {o[dst]: r}, arith_flags(r, c, v)
    return f


MODELS["sub.rrr.l"] = _sub("r", "s", "t")
MODELS["sub.modimm.rri"] = _sub("r", "s", "n")
MODELS["rsub.modimm.rri"] = _sub("r", "n", "s")


@model("addc.rrr")
def addc(R, fl, o):
    r, c, v = add_full(R[o["s"]], R[o["t"]], fl >> 1 & 1)
    return {o["r"]: r}, arith_flags(r, c, v)


@model("subc.rrr")
def subc(R, fl, o):
    r, c, v = sub_full(R[o["s"]], R[o["t"]], fl >> 1 & 1)
    return {o["r"]: r}, arith_flags(r, c, v)


@model("add.brev.rr")
def add_brev(R, fl, o):
    # carries run from bit 31 down to bit 0: add the bit-reversed operands and reverse the sum
    s, c, v = add_full(rev32(R[o["r"]]), rev32(R[o["s"]]))
    r = rev32(s)
    return {o["r"]: r}, arith_flags(r, c, v)


# Logic, multiply, extension, bit-field and byte-order forms: N and Z from the 32-bit result, C and V kept.
def _nz(dst, fn):
    def f(R, fl, o):
        r = fn(R, o) & M
        return {o[dst]: r}, (fl & (C_ | V_)) | nz(r)
    return f


MODELS["and.rr"] = _nz("d", lambda R, o: R[o["d"]] & R[o["s"]])
MODELS["or.rr"] = _nz("d", lambda R, o: R[o["d"]] | R[o["s"]])
MODELS["xor.rr"] = _nz("d", lambda R, o: R[o["d"]] ^ R[o["s"]])
MODELS["not.rr"] = _nz("d", lambda R, o: ~R[o["s"]])
MODELS["and.rrr"] = _nz("r", lambda R, o: R[o["s"]] & R[o["t"]])
MODELS["or.rrr"] = _nz("r", lambda R, o: R[o["s"]] | R[o["t"]])
MODELS["xor.rrr"] = _nz("r", lambda R, o: R[o["s"]] ^ R[o["t"]])
MODELS["bic.rrr"] = _nz("r", lambda R, o: R[o["s"]] & ~R[o["t"]])
MODELS["and.bit.rrr"] = _nz("r", lambda R, o: R[o["s"]] & (1 << (R[o["t"]] & 31)))
MODELS["and.invbit.rrr"] = _nz("r", lambda R, o: R[o["s"]] & ~(1 << (R[o["t"]] & 31)))
MODELS["or.bit.rrr"] = _nz("r", lambda R, o: R[o["s"]] | (1 << (R[o["t"]] & 31)))
MODELS["xor.bit.rrr"] = _nz("r", lambda R, o: R[o["s"]] ^ (1 << (R[o["t"]] & 31)))
MODELS["and.invbit"] = _nz("r", lambda R, o: R[o["r"]] & o["b"])
MODELS["or.bit"] = _nz("r", lambda R, o: R[o["r"]] | o["b"])
MODELS["xor.bit"] = _nz("r", lambda R, o: R[o["r"]] ^ o["b"])
MODELS["and.modimm.rri"] = _nz("r", lambda R, o: R[o["s"]] & o["n"])
MODELS["and.nmodimm.rri"] = _nz("r", lambda R, o: R[o["s"]] & o["n"])
MODELS["or.modimm.rri"] = _nz("r", lambda R, o: R[o["s"]] | o["n"])
MODELS["xor.modimm.rri"] = _nz("r", lambda R, o: R[o["s"]] ^ o["n"])
MODELS["mul.rr"] = _nz("d", lambda R, o: R[o["d"]] * R[o["s"]])
MODELS["mul.rrr"] = _nz("r", lambda R, o: R[o["s"]] * R[o["t"]])
MODELS["mul.modimm.rri"] = _nz("r", lambda R, o: R[o["s"]] * o["n"])
MODELS["ext.b0.u"] = _nz("d", lambda R, o: R[o["s"]] & 0xFF)
MODELS["ext.b0.s"] = _nz("d", lambda R, o: ((R[o["s"]] & 0xFF) ^ 0x80) - 0x80)
MODELS["ext.l.u"] = _nz("d", lambda R, o: R[o["s"]] & 0xFFFF)
MODELS["ext.l.s"] = _nz("d", lambda R, o: ((R[o["s"]] & 0xFFFF) ^ 0x8000) - 0x8000)


@model("clz.rr")
def clz(R, fl, o):
    x = R[o["s"]]
    r = 32 - x.bit_length()
    return {o["r"]: r}, (fl & (C_ | V_)) | nz(r)


@model("cls.rr")
def cls(R, fl, o):
    x = R[o["s"]]
    r = 32 - (x ^ M if x >> 31 else x).bit_length()
    return {o["r"]: r}, (fl & (C_ | V_)) | nz(r)


MODELS["sgn.rr"] = _nz("r", lambda R, o: 0 if R[o["s"]] == 0 else (M if R[o["s"]] >> 31 else 1))
MODELS["rev8.rr"] = _nz("r", lambda R, o: int.from_bytes(R[o["s"]].to_bytes(4, "little"), "big"))
MODELS["rev16.rr"] = _nz("r", lambda R, o: ((R[o["s"]] & 0x00FF00FF) << 8) | ((R[o["s"]] >> 8) & 0x00FF00FF))
MODELS["revs.rr"] = _nz("r", lambda R, o: s32((((R[o["s"]] & 0xFF) << 8) | ((R[o["s"]] >> 8) & 0xFF)) ^ 0x8000) - 0x8000)


# constants and moves leave the flags alone (hw/fm1-2026-10-24: every case)
def _half_ins(old, new, high):
    return (old & 0x0000FFFF) | (new << 16) if high else (old & 0xFFFF0000) | new


@model("li.byte")
def li_byte(R, fl, o):
    sh = 8 * o["raw"]["n"]
    return {o["r"]: (R[o["r"]] & ~(0xFF << sh)) | (o["m"] << sh)}, fl


@model("li.half")
def li_half(R, fl, o):
    return {o["r"]: _half_ins(R[o["r"]], o["m"], o["raw"]["n"])}, fl


for _i in ("li.modimm", "li.neg5", "li.s16", "li.u32"):
    MODELS[_i] = lambda R, fl, o: ({o["r"]: o["n"]}, fl)
MODELS["li.zero_hi"] = lambda R, fl, o: ({o["r"]: 0}, fl)
MODELS["li.zero_pair"] = lambda R, fl, o: ({o["p"]: 0, o["p"] + 1: 0}, fl)
MODELS["mov.pair"] = lambda R, fl, o: ({o["d"]: R[o["s"]], o["d"] + 1: R[o["s"] + 1]}, fl)


@model("mov.half")
def mov_half(R, fl, o):
    src = (R[o["s"]] >> 16 if o["raw"]["m"] else R[o["s"]]) & 0xFFFF
    return {o["r"]: _half_ins(R[o["r"]], src, o["raw"]["n"])}, fl


# bit fields: p is the lowest bit, l the width; a field that would pass bit 31 is cut off there
def _fieldw(p, l):
    return max(0, min(l, 32 - p))


@model("uextra.rrii")
def uextra(R, fl, o):
    w = _fieldw(o["n"], o["m"])
    r = (R[o["s"]] >> o["n"]) & ((1 << w) - 1)
    return {o["r"]: r}, (fl & (C_ | V_)) | nz(r)


@model("sextra.rrii")
def sextra(R, fl, o):
    # the field is l bits wide and its sign is bit l-1 of it, even when p+l passes bit 31 (the missing bits read 0)
    l = o["m"]
    r = (R[o["s"]] >> o["n"]) & ((1 << l) - 1)
    if l:
        r = (r ^ (1 << (l - 1))) - (1 << (l - 1))
    r &= M
    return {o["r"]: r}, (fl & (C_ | V_)) | nz(r)


@model("insert.rrii")
def insert(R, fl, o):
    w = _fieldw(o["n"], o["m"])
    mask = ((1 << w) - 1) << o["n"]
    r = (R[o["r"]] & ~mask) | ((R[o["s"]] << o["n"]) & mask)
    return {o["r"]: r}, (fl & (C_ | V_)) | nz(r)


# 32-bit shifts: N, Z and C (the last bit shifted out) are written, V is kept.
# A register count is its low 8 bits; counts above 32 act as 32.
def _shift(kind, dst, src, cnt):
    def f(R, fl, o):
        c = o[cnt] if cnt == "n" else R[o[cnt]] & 0xFF
        x = R[o[src]]
        r, cy = shift32(kind, x, c, fl >> 1 & 1)
        return {o[dst]: r}, nz(r) | (C_ if cy else 0) | (fl & V_)
    return f


for _k in ("lsl", "lsr", "asr", "shl3"):
    MODELS[_k + ".rr"] = _shift(_k, "d", "d", "s")
    MODELS[_k + ".rrr"] = _shift(_k, "r", "s", "t")
for _i, _a in (("lsl.rri.l", "r"), ("lsr.rri.l", "r"), ("asr.rri.l", "r"), ("shl3.rri.l", "r"),
               ("lsr.rri", "d"), ("asr.rri", "d"), ("shl3.rri", "d")):
    MODELS[_i] = _shift(_i.split(".")[0], _a, "s", "n")


def _ror32(x, c):
    c &= 31
    return ((x >> c) | (x << (32 - c))) & M


MODELS["ror.rri"] = _nz("r", lambda R, o: _ror32(R[o["s"]], o["n"]))
MODELS["ror.rrr"] = _nz("r", lambda R, o: _ror32(R[o["s"]], R[o["t"]]))


def _rorc(x, c, cin):
    """Rotate the 33-bit value (carry, x) right by c (0..32); returns (result, carry)."""
    v = (cin << 32) | x
    k = (33 - c) % 33
    v = ((v << k) | (v >> (33 - k))) & ((1 << 33) - 1)
    return v & M, v >> 32


def _cycc(src, cnt, dst):
    def f(R, fl, o):
        c = o[cnt] if cnt == "n" else min(R[o[cnt]] & 0xFF, 32)
        r, cy = _rorc(R[o[src]], c, fl >> 1 & 1)
        return {o[dst]: r}, nz(r) | (C_ if cy else 0) | (fl & V_)
    return f


MODELS["cycc.rri"] = _cycc("s", "n", "r")
MODELS["cycc.rrr"] = _cycc("s", "t", "r")


@model("xchg.rrr")
def xchg(R, fl, o):
    # signed 6-bit count in the low bits of rt: positive shifts left, negative shifts right (zero fill)
    x, c = R[o["s"]], R[o["t"]] & 63
    c = c - 64 if c >= 32 else c
    cy = fl >> 1 & 1
    if c > 0:
        r, cy = (x << c) & M, x >> (32 - c) & 1
    elif c < 0:
        r, cy = x >> -c, x >> (-c - 1) & 1
    else:
        r = x
    return {o["r"]: r}, nz(r) | (C_ if cy else 0) | (fl & V_)


# 64-bit shifts of a register pair: only C is written (the last bit shifted out); N, Z and V are kept.
# rotate right (ror) writes no flag. A register count is its low 8 bits; counts above 64 act as 64.
def _pair(kind, imm):
    def f(R, fl, o):
        p = o["r"]
        c = o["n"] if imm else R[o["s"]] & 0xFF
        r, cy = shift64(kind, R[p] | R[p + 1] << 32, c, fl >> 1 & 1)
        return {p: r & M, p + 1: r >> 32}, (fl & ~C_ & 15) | (C_ if cy else 0)
    return f


for _k, _n in (("lsl", "lsl.pair"), ("lsr", "lsr.pair"), ("asr", "asr.pair"), ("shl3", "shl3.pair"),
               ("ror", None), ("rorc", None)):
    if _n:
        MODELS[_n + ".i"] = _pair(_k, True)
        MODELS[_n + ".r"] = _pair(_k, False)
MODELS["ror.pi"] = _pair("ror", True)
MODELS["ror.pr"] = _pair("ror", False)
MODELS["cycc.pi"] = _pair("rorc", True)
MODELS["cycc.pr"] = _pair("rorc", False)


MODELS["cc.set"] = lambda R, fl, o: ({}, (fl & ~C_ & 15) | (C_ if o["v"] else 0))


# shiftr: shift a pair right by 0..64 (a register count is its low 8 bits, clamped to 64), round to the
# nearest integer, saturate to 32 bits (unsigned for >>, signed for >>>). N and Z come from the result, C is the
# last bit shifted out (the rounding bit; 0 for a count of 0), V is kept. Only ties differ between the modes
# (assumed: up = toward +inf, even = to even, round = away from zero, zero = toward zero).
def _shiftr(imm):
    def f(R, fl, o):
        s = o["s"]
        x = R[s] | R[s + 1] << 32
        c = o["m"] if imm else R[o["t"]] & 0xFF
        mode = o["raw"]["p"] if imm else o["raw"]["m"]
        arith = o["raw"]["n"]
        c = min(c, 64)
        xv = s64(x) if arith else x
        q = xv >> c                           # floor of the quotient
        rem2 = 2 * (xv - (q << c))            # twice the remainder, 0 <= rem2 <= 2 << c
        tie = c > 0 and rem2 == 1 << c
        if c > 0 and rem2 > 1 << c:
            q += 1
        elif tie:
            q += (1, q & 1, int(xv >= 0), int(xv < 0))[mode]
        r = max(-(1 << 31), min((1 << 31) - 1, q)) if arith else min(M, q)
        r &= M
        cy = x >> (c - 1) & 1 if c else 0
        return {o["r"]: r}, nz(r) | (C_ if cy else 0) | (fl & V_)
    return f


MODELS["shiftr.rpi.mode"] = _shiftr(True)
MODELS["shiftr.rpr.mode"] = _shiftr(False)


@model("lsr.rri.vb")
def lsr_vb(R, fl, o):
    # each of the four bytes shifted right by 0..7 on its own; no flags
    x, n = R[o["s"]], o["n"]
    r = sum(((x >> 8 * i & 0xFF) >> n) << 8 * i for i in range(4))
    return {o["r"]: r}, None


@model("asr.ppi.rnd.vh")
def asr_vh(R, fl, o):
    # each of the four halfwords of the pair shifted right (sign fill) by 0..7, rounded to nearest; no flags
    n, out = o["n"], {}
    for k in (0, 1):
        x, r = R[o["s"] + k], 0
        for i in (0, 1):
            h = s32((x >> 16 * i & 0xFFFF) << 16) >> 16
            h = h if n == 0 else (h + (1 << (n - 1))) >> n      # a tie rounds up (assumed)
            r |= (h & 0xFFFF) << 16 * i
        out[o["r"] + k] = r
    return out, None


# popcnt: this chip does not count bits (hw/fm1-2026-10-24). popcnt.rr changes nothing at all; popcnt.r_pair
# behaves as mov.half "rd.l = r(2s).l": it replaces the low half of rd with the low half of the pair's low
# register. Neither touches the flags.
MODELS["popcnt.rr"] = lambda R, fl, o: ({}, fl)
MODELS["popcnt.r_pair"] = lambda R, fl, o: ({o["r"]: _half_ins(R[o["r"]], R[o["s"]] & 0xFFFF, 0)}, fl)
