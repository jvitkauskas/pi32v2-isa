# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Format-2 models for hardware run 3 (hw/fm1-2026-10-24-v3): if/iff/ifs blocks, rep, rep.i, tbb, tbh and the
parallel twins. The blocks' bodies, laid out by gen.py, write r8.. = 0x100 + k (then part) and r12.. = 0x200 + k
(else part); a rep body is `r7 += 1` repeated; tbb/tbh land on `r8 = k + 1` and the taken exit."""
import re

from semantics.b2 import compare

MASK = 0xFFFFFFFF


def block(condition, **kw):
    pred = compare(condition, **kw)

    def model(R, f, o, st):
        taken = pred(R, f, o, st)["exit"]
        regs = {8 + k: 0x100 + k for k in range(o["t"])} if taken else {12 + k: 0x200 + k for k in range(o["e"])}
        return {"regs": regs, "flags": f}
    return model


def rep_model(count_of, body_of):
    def model(R, f, o, st):
        n = count_of(R, o) * (body_of(o) // 2)
        regs = {7: (R[7] + n) & MASK}
        if "r" in o and "b" in o:                 # rep.i has no count register
            pass
        elif "r" in o:
            regs[o["r"]] = 0                      # rep counts its register down to 0
        # the last `r7 += 1` sets the flags (r7 starts below 0x100: no N, Z, C or V); none if the body never ran
        return {"regs": regs, "flags": 0 if n else f}
    return model


def table_branch(width):
    def model(R, f, o, st):
        k = R[o["x"]] // width
        return {"regs": {8: k + 1}, "exit": 1, "flags": f}
    return model


MODELS = {
    "rep": rep_model(lambda R, o: R[o["r"]], lambda o: o["n"]),
    "rep.i": rep_model(lambda R, o: o["n"], lambda o: o["b"]),
    "tbb": table_branch(1),
    "tbh": table_branch(2),
}

_REL = {"==": "eq", "!=": "ne", ">=": "ge", "<": "lt", ">": "gt", "<=": "le"}


def _block_models():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from pi32v2isa import table
    for i in table.load().insns:
        if not i.block or i.id.endswith(".p") or i.asm_no_syntax or re.fullmatch(r"iff\.ne\.rr\.\d", i.id):
            continue                          # iff.ne.rr.1..6: no model fits (hw/fm1-2026-10-24-v3/README.md)
        m = re.match(r"(iff|ifs|if) \(\(?\{r\} (?:& \{[sn]\}\) )?(u?)(==|!=|>=|<=|<|>) (?:\{[sn]\}|0)\)? \{\{", i.syntax)
        if not m:
            continue
        kind, u, rel = m.groups()
        masked = "&" in i.syntax
        MODELS[i.id] = block(u + _REL[rel], signed_compare=kind == "ifs", masked=masked, floating=kind == "iff")


_block_models()


# --------------------------------------------------------------------------------------- parallel twins ---

def half_mask(text):
    """The bits a form writes in its destination register when it writes one half (`r3.h = ...`), from the
    case's text (the half is often an enum field)."""
    m = re.match(r"r\d+\.([hl]) ", text)
    return None if not m else (0xFFFF0000 if m.group(1) == "h" else 0x0000FFFF)


def pair(plain):
    """`A #` then B (a 16-bit `[rb+n] = rd` or `rd = [rb+n]`, rd = A's first destination): B reads the registers
    as they were before A; when both write rd, A's result is what stays."""
    def model(R, f, o, st):
        writes, flags = plain(R, f, o)
        b = st.rec["pair_b"]
        regs = {}
        out = {"regs": regs, "flags": flags}
        addr = (R[b["b"]] + b["n"]) & MASK
        if b["id"] == "st.w":
            out["mem"] = {addr: R[b["d"]]}
        else:
            regs[b["d"]] = st.load(addr)
        mask = half_mask(st.rec["text"])
        for r, v in writes.items():
            if mask is not None and r in regs:      # A writes one half; the other half is what B loaded
                v = (regs[r] & ~mask) | (v & mask)
            regs[r] = v & MASK
        return out
    return model


def _pair_models():
    from semantics import basic, p, q, r, s
    plain = {}
    for mod in (basic, p, q, r, s):
        plain.update(mod.MODELS)
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from pi32v2isa import table
    tab = {i.id: i for i in table.load().insns}
    for k, fn in plain.items():
        if k + ".p" in tab:
            MODELS[k + ".p"] = pair(fn)


_pair_models()
