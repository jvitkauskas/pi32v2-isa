# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Format-2 branch/call models, hw/fm1-2026-10-24-v2.

All these forms preserve N/Z/C/V. Compare-and-branch tests its operands
without publishing a subtraction/AND/float-compare result to psr.
ifs2ns.c/s are the r0 bit-zero tests despite their unusual printed names.
See hw/report5-b.md for evidence limits and follow-up boundaries.
"""

MASK = 0xFFFFFFFF


def signed(x):
    x &= MASK
    return x - (1 << 32) if x & (1 << 31) else x


RELATIONS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "ge": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "gt": lambda a, b: a > b,
    "le": lambda a, b: a <= b,
}


def compare(condition, signed_compare=False, masked=False, floating=False):
    def model(R, f, o, st):
        a = R[o["r"]]
        b = R[o["s"]] if "s" in o else o.get("i", o.get("n"))
        b &= MASK
        unordered = False
        if floating:
            unordered = (a & 0x7FFFFFFF) > 0x7F800000 or (b & 0x7FFFFFFF) > 0x7F800000
            # Float ordering by sign/magnitude, including infinities, subnormals,
            # and +0 == -0; never depend on the host's NaN handling.
            a = -(a & 0x7FFFFFFF) if a >> 31 else a
            b = -(b & 0x7FFFFFFF) if b >> 31 else b
        elif masked:
            a, b = a & b, 0
        elif signed_compare:
            a, b = signed(a), signed(b)
        cond = condition.removeprefix("u")
        taken = condition.startswith("u") if unordered else RELATIONS[cond](a, b)
        return {"exit": int(taken), "flags": f}
    return model


def flag_branch(condition):
    def model(R, f, o, st):
        n, z, c, v = bool(f & 8), bool(f & 4), bool(f & 2), bool(f & 1)
        taken = {"eq": z, "ne": not z, "cs": c, "cc": not c,
                 "hi": c and not z, "ls": not c or z,
                 "ge": n == v, "lt": n != v,
                 "gt": not z and n == v, "le": z or n != v}[condition]
        return {"exit": int(taken), "flags": f}
    return model


def call(R, f, o, st):
    return {"exit": 1, "rets": st.end, "flags": f}


def jump(R, f, o, st):
    return {"exit": 1, "flags": f}


def bnez(R, f, o, st):
    return {"exit": int(R[o["r"]] != 0), "flags": f}


def dbnz(R, f, o, st):
    value = (R[o["r"]] - 1) & MASK
    return {"regs": {o["r"]: value}, "exit": int(value != 0), "flags": f}


def ifs2ns_c(R, f, o, st):
    return {"exit": int((R[0] & 1) == 0), "flags": f}


def ifs2ns_s(R, f, o, st):
    return {"exit": R[0] & 1, "flags": f}


MODELS = {
    "call.r": call, "call.s": call, "goto.r": jump, "goto.s": jump,
    "bnez": bnez, "dbnz.r": dbnz, "ifs2ns.c": ifs2ns_c, "ifs2ns.s": ifs2ns_s,
}
for condition in ("eq", "ne", "cs", "cc", "hi", "ls", "ge", "lt", "gt", "le"):
    MODELS[f"bc.{condition}"] = flag_branch(condition)
for condition in RELATIONS:
    for shape in ("rr", "rr.l", "ri", "ri.l", "ri.l.modimm"):
        MODELS[f"b{condition}.{shape}"] = compare(condition)
    if condition in ("eq", "ne"):
        for shape in ("rr", "ri", "modimm.ri.l"):
            MODELS[f"b{condition}.and.{shape}"] = compare(condition, masked=True)
    else:
        for shape in ("rr", "rr.l", "ri", "ri.l", "ri.l.modimm"):
            MODELS[f"b{condition}s.{shape}"] = compare(condition, signed_compare=True)
for condition in ("eq", "une", "ge", "lt", "gt", "le", "uge", "ult", "ugt", "ule"):
    for shape in ("rr", "rr.l"):
        MODELS[f"bf{condition}.{shape}"] = compare(condition, floating=True)
