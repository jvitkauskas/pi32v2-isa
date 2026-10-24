# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Models of the DSP arithmetic and multiply forms (analyst R; see check.py for the interface)."""
from semantics._r_util import *  # noqa: F401,F403

MODELS = {}


def model(*ids):
    def deco(fn):
        for i in ids:
            MODELS[i] = fn
        return fn
    return deco


# ---- halfword add/sub ------------------------------------------------------------------------
def _hsel(R, reg, which):
    return half(R[reg], which == ".h")


def _mk_hh(sign, imm):
    def fn(R, f, o):
        a = _hsel(R, o["s"], o["m"])
        b = o["p"] if imm else _hsel(R, o["t"], o["p"])
        v = (a + sign * b) & 0xFFFF
        return {o["r"]: sethalf(R[o["r"]], o["n"] == ".h", v)}, None
    return fn


MODELS["add.rhrhi"] = _mk_hh(1, True)
MODELS["sub.rhrhi"] = _mk_hh(-1, True)
MODELS["add.rhrhrh"] = _mk_hh(1, False)
MODELS["sub.rhrhrh"] = _mk_hh(-1, False)


def _mk_hhe(sign):
    def fn(R, f, o):
        a = _hsel(R, o["s"], o["m"])
        b = _hsel(R, o["t"], o["p"])
        v = lane(a, b, sign, o["q"])
        return {o["r"]: sethalf(R[o["r"]], o["n"] == ".h", v)}, None
    return fn


MODELS["add.rhrhrhe"] = _mk_hhe(1)
MODELS["sub.rhrhrhe"] = _mk_hhe(-1)


def _mk_rrre(sign):
    def fn(R, f, o):
        a, b = R[o["s"]], R[o["t"]]
        signed = o["n"] == "(ssat)"
        if signed:
            a, b = s32(a), s32(b)
        t = a + sign * b
        t = ssat(t, 32) if signed else usat(t, 32)
        return {o["r"]: t & M32}, None
    return fn


MODELS["add.rrre"] = _mk_rrre(1)
MODELS["sub.rrre"] = _mk_rrre(-1)


def _mk_hshift(kind, imm, cmask=0xFF):
    def fn(R, f, o):
        a = _hsel(R, o["s"], o["m"])
        n = o["p"] if imm else R[o["t"]] & cmask
        v = shift_lane(kind, a, n, 16)
        return {o["r"]: sethalf(R[o["r"]], o["n"] == ".h", v)}, None
    return fn


for _k in ("lsl", "lsr", "asr", "shl3"):
    MODELS[f"{_k}.rhrhi"] = _mk_hshift(_k, True)
    MODELS[f"{_k}.rhrhr"] = _mk_hshift(_k, False)


def _mk_vshift(kind, imm, cmask=0xFF):
    def fn(R, f, o):
        n = o["n"] if imm else R[o["t"]] & cmask
        a = R[o["s"]]
        v = shift_lane(kind, a & M16, n, 16) | shift_lane(kind, a >> 16, n, 16) << 16
        return {o["r"]: v}, None
    return fn


for _k in ("lsl", "lsr", "asr", "shl3"):
    MODELS[f"{_k}.v.rri"] = _mk_vshift(_k, True)
    MODELS[f"{_k}.v.rrr"] = _mk_vshift(_k, False)


def _mk_pshr(signed, imm):
    def fn(R, f, o):
        p = R[o["s"]] | R[o["s"] + 1] << 32
        n = o["n"] if imm else R[o["t"]] & 0xFF
        if signed:
            t = ssat(s64(p) >> min(n, 63), 32) & M32
        else:
            t = usat(p >> n if n < 64 else 0, 32)
        c = p >> (min(n, 64) - 1) & 1 if n else 0
        # N = sign of the result, Z = result zero, C = last bit shifted out, bit 0 left alone
        return {o["r"]: t}, f & 1 | (t >> 31) << 3 | (t == 0) << 2 | c << 1
    return fn


for _s in "su":
    MODELS[f"lsr.{_s}.rpi"] = _mk_pshr(_s == "s", True)
    MODELS[f"lsr.{_s}.rpr"] = _mk_pshr(_s == "s", False)


# ---- add4: four byte lanes -------------------------------------------------------------------
def _bytes(v):
    return [(v >> (8 * i)) & 0xFF for i in range(4)]


def _lanes16(lo, hi):
    return [lo & M16, lo >> 16, hi & M16, hi >> 16]


def _pack16(ls, d):
    ls = [x & M16 for x in ls]
    return {d: ls[0] | ls[1] << 16, d + 1: ls[2] | ls[3] << 16}


@model("add4.ppr")
def _add4_ppr(R, f, o):
    acc = _lanes16(R[o["s"]], R[o["s"] + 1])
    return _pack16([a + b for a, b in zip(acc, _bytes(R[o["t"]]))], o["r"]), f


@model("add4.prr")
def _add4_prr(R, f, o):
    sign = 1 if o["n"].startswith("+") else -1
    return _pack16([a + sign * b for a, b in zip(_bytes(R[o["s"]]), _bytes(R[o["t"]]))], o["r"]), f


@model("add4.rrr.rnd.uavg")
def _add4_avg(R, f, o):
    v = 0
    for i, (a, b) in enumerate(zip(_bytes(R[o["s"]]), _bytes(R[o["t"]]))):
        v |= ((a + b + 1) >> 1) << (8 * i)
    return {o["r"]: v}, f


# ---- two-lane add/subtract with a mode ----------------------------------------------------------
_SIGNS = {"addadd": (1, 1), "addsub": (1, -1), "subadd": (-1, 1), "subsub": (-1, -1)}


def _mode_of(suffix):
    parts = suffix.split(".")
    if parts[-1] == "x2":
        return "(" + parts[-2] + ",x2)"
    if parts[0] == "rnd":
        return "(rnd," + parts[1] + ")"
    return "(" + parts[0] + ")"


def _mk_two(signs, mode):
    def fn(R, f, o):
        s, t = R[o["s"]], R[o["t"]]
        hi = lane(half(s, o["n"] == ".h"), half(t, o["p"] == ".h"), signs[0], mode)
        lo = lane(half(s, o["m"] == ".h"), half(t, o["q"] == ".h"), signs[1], mode)
        return {o["r"]: hi << 16 | lo}, f
    return fn


for _op, _sg in _SIGNS.items():
    for _suffix in ("rnd.savg", "rnd.uavg", "savg", "uavg", "ssat", "usat", "ssat.x2", "usat.x2"):
        MODELS[f"{_op}.rrhrhrhrh.{_suffix}"] = _mk_two(_sg, _mode_of(_suffix))


# ---- add/subtract a small constant -------------------------------------------------------------
@model("addsub.rhrhi.sat")
def _addsub_imm_h(R, f, o):
    sign = 1 if o["o"] == "+" else -1
    v = lane(half(R[o["s"]], o["m"] == ".h"), o["p"], sign, o["q"])
    return {o["r"]: sethalf(R[o["r"]], o["n"] == ".h", v)}, f


@model("addsub.rhrhi.mode")
def _addsub_imm_2(R, f, o):
    s1, s2 = (1 if c == "+" else -1 for c in o["p"].split("|"))
    hi = lane(half(R[o["s"]], o["n"] == ".h"), o["q"], s1, o["i"])
    lo = lane(half(R[o["s"]], o["m"] == ".h"), o["q"], s2, o["i"])
    return {o["r"]: hi << 16 | lo}, f


# ---- pair forms ---------------------------------------------------------------------------------
def _signs(text):
    return [1 if c == "+" else -1 for c in text.split("|")]


@model("addsub.pqq.sat")
def _addsub_pqq(R, f, o):
    s1, s2 = _signs(o["n"])
    (a0, a1), (b0, b1) = o["s"], o["m"]
    hi = lane(R[a0], R[b0], s1, o["p"], 32)
    lo = lane(R[a1], R[b1], s2, o["p"], 32)
    return {o["r"] + 1: hi, o["r"]: lo}, f


@model("addsub.ppp.mode")
def _addsub_ppp(R, f, o):
    sg = _signs(o["n"])[::-1]  # printed from the top lane down
    a = _lanes16(R[o["s"]], R[o["s"] + 1])
    b = _lanes16(R[o["t"]], R[o["t"] + 1])
    return _pack16([lane(x, y, g, o["m"]) for x, y, g in zip(a, b, sg)], o["r"]), f


# ---- 32 x 32 -> 64 multiply and accumulate ----------------------------------------------------------
def _mk_mulp(signed, acc):
    def fn(R, f, o):
        a, b = R[o["s"]], R[o["t"]]
        if signed:
            a, b = s32(a), s32(b)
        p = (a * b) & (1 << 64) - 1
        flags = f
        if acc:
            old = R[o["r"]] | R[o["r"] + 1] << 32
            if acc > 0:
                full = old + p
                carry = full >> 64
            else:
                full = old - p
                carry = old >= p  # no borrow, as for sub
            p = full & (1 << 64) - 1
            flags = f & ~2 | carry << 1
        return {o["r"]: p & M32, o["r"] + 1: p >> 32}, flags
    return fn


for _s in "su":
    MODELS[f"mul.{_s}.prr"] = _mk_mulp(_s == "s", 0)
    MODELS[f"madd.{_s}.prr"] = _mk_mulp(_s == "s", 1)
    MODELS[f"msub.{_s}.prr"] = _mk_mulp(_s == "s", -1)


# ---- 16 x 16 multiplies ---------------------------------------------------------------------------
def _mode_parts(mode):
    parts = mode.strip("()").split(",")
    return ("ssat" in parts), ("x2" in parts)


def _mulsat(a, b, mode, bits, acc=0):
    """16 x 16 product (signed for ssat, unsigned for usat), optionally doubled, added to acc (+1 or -1 times
    the accumulator argument's sign is applied by the caller), then saturated to `bits` bits."""
    signed, x2 = _mode_parts(mode)
    if signed:
        a, b = sext(a, 16), sext(b, 16)
    p = a * b * (2 if x2 else 1)
    return p, signed


def _sat(v, signed, bits):
    return (ssat(v, bits) if signed else usat(v, bits)) & ((1 << bits) - 1)


@model("mul.rhrhrhe")
def _mul_h(R, f, o):
    p, sg = _mulsat(half(R[o["s"]], o["m"] == ".h"), half(R[o["t"]], o["p"] == ".h"), o["q"], 16)
    return {o["r"]: sethalf(R[o["r"]], o["n"] == ".h", _sat(p, sg, 16))}, f


@model("mul.rrhrhe")
def _mul_w(R, f, o):
    p, sg = _mulsat(half(R[o["s"]], o["n"] == ".h"), half(R[o["t"]], o["m"] == ".h"), o["p"], 32)
    return {o["r"]: _sat(p, sg, 32)}, f


def _mk_madd_h(sign):
    def fn(R, f, o):
        p, sg = _mulsat(half(R[o["s"]], o["m"] == ".h"), half(R[o["t"]], o["p"] == ".h"), o["q"], 16)
        a = half(R[o["r"]], o["n"] == ".h")  # the accumulator lane is read as unsigned even for ssat
        return {o["r"]: sethalf(R[o["r"]], o["n"] == ".h", _sat(a + sign * p, sg, 16))}, f
    return fn


def _mk_madd_w(sign):
    def fn(R, f, o):
        p, sg = _mulsat(half(R[o["s"]], o["n"] == ".h"), half(R[o["t"]], o["m"] == ".h"), o["p"], 32)
        a = R[o["r"]]
        a = s32(a) if sg else a
        return {o["r"]: _sat(a + sign * p, sg, 32)}, f
    return fn


MODELS["madd.rhrhrhe"] = _mk_madd_h(1)
MODELS["msub.rhrhrhe"] = _mk_madd_h(-1)
MODELS["madd.rrhrhe"] = _mk_madd_w(1)
MODELS["msub.rrhrhe"] = _mk_madd_w(-1)


def _mk_mulimm(acc, signed):
    def fn(R, f, o):
        a = half(R[o["s"]], o["n"] == ".h")
        if signed:
            a = sext(a, 16)
        p = a * o["m"]
        if acc:
            base = s32(R[o["r"]]) if signed else R[o["r"]]
            p = base + acc * p
        return {o["r"]: _sat(p, signed, 32)}, f
    return fn


for _m, _a in (("mul", 0), ("madd", 1), ("msub", -1)):
    MODELS[f"{_m}.rrhi.ssat"] = _mk_mulimm(_a, True)
    MODELS[f"{_m}.rrhi.usat"] = _mk_mulimm(_a, False)


# ---- two parallel 16 x 16 multiplies -------------------------------------------------------------------
def _products(R, o, mode, imm):
    """The (high, low) lane products of a `*|*` form, as plain integers (doubled for x2)."""
    sg, x2 = _mode_parts(mode)
    out = []
    for sel_s, sel_t in ((o["n"], "p"), (o["m"], "q")):
        a = half(R[o["s"]], sel_s == ".h")
        a = sext(a, 16) if sg else a
        b = o["p"] if imm else half(R[o["t"]], o[sel_t] == ".h")
        if not imm and sg:
            b = sext(b, 16)
        out.append(a * b * (2 if x2 else 1))
    return out, sg


def _mk_mul2(pair, imm, acc, mode=None):
    def fn(R, f, o):
        m = mode or o["i"]
        (hi, lo), sg = _products(R, o, m, imm)
        d = o["r"]
        if pair:
            res = {}
            for reg, p in ((d + 1, hi), (d, lo)):
                base = R[reg]
                base = s32(base) if sg else base
                res[reg] = _sat(base + acc * p, sg, 32) if acc else _sat(p, sg, 32)
            return res, f
        parts = []
        for shift, p in ((16, hi), (0, lo)):
            lane_acc = R[d] >> shift & M16  # read unsigned, as in the halfword accumulators
            parts.append(_sat(lane_acc + acc * p, sg, 16) if acc else _sat(p, sg, 16))
        return {d: parts[0] << 16 | parts[1]}, f
    return fn


for _m, _a in (("mul2", 0), ("madd.mul2", 1), ("msub.mul2", -1)):
    MODELS[f"{_m}.rrhrhrhrhe"] = _mk_mul2(False, False, _a)
    MODELS[f"{_m}.prhrhrhrhe"] = _mk_mul2(True, False, _a)
    MODELS[f"{_m}.prhrhi.ssat"] = _mk_mul2(True, True, _a, "(ssat)")
    MODELS[f"{_m}.prhrhi.usat"] = _mk_mul2(True, True, _a, "(usat)")


# ---- four byte lanes multiplied ------------------------------------------------------------------------
def _sb(v):
    return v - 256 if v & 0x80 else v


@model("mul4.u.prr")
def _mul4_u(R, f, o):
    return _pack16([a * b for a, b in zip(_bytes(R[o["s"]]), _bytes(R[o["t"]]))], o["r"]), f


@model("mul4.m.prr")
def _mul4_m(R, f, o):
    return _pack16([a * _sb(b) for a, b in zip(_bytes(R[o["s"]]), _bytes(R[o["t"]]))], o["r"]), f


@model("mul4.m.pri")
def _mul4_mi(R, f, o):
    return _pack16([a * o["n"] for a in _bytes(R[o["s"]])], o["r"]), f


def _mk_madd4(signed_t):
    def fn(R, f, o):
        acc = _lanes16(R[o["r"]], R[o["r"] + 1])
        prods = [a * (_sb(b) if signed_t else b) for a, b in zip(_bytes(R[o["s"]]), _bytes(R[o["t"]]))]
        return _pack16([x + y for x, y in zip(acc, prods)], o["r"]), f
    return fn


MODELS["madd.mul4.u.prr"] = _mk_madd4(False)
MODELS["madd.mul4.m.prr"] = _mk_madd4(True)


# ---- sum(... *|* ...) with a pair result: this chip runs them as the mul2/madd.mul2/msub.mul2 forms with
# (usat) for (u) and (ssat) for (s); the extra encoding bit (rrr1 instead of rrr0) makes no difference ----------
for _s, _mode in (("s", "(ssat)"), ("u", "(usat)")):
    for _name, _a in (("sum", 0), ("sum.acc", 1), ("sum.nacc", -1)):
        _id = f"{_name}.{_s}.prhrhrhrh"
        MODELS[_id] = _mk_mul2(True, False, _a, _mode)


# ---- sum.acc.{usat,ssat,msat}.rrr: instruction revision 3 forms that this chip executes as add4 (rnd,uavg) ---
for _m in ("usat", "ssat", "msat"):
    MODELS[f"sum.acc.{_m}.rrr"] = _add4_avg
