# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Format-2 models of the stack, special-register and register-list forms, hw/fm1-2026-10-24-v2 (results.jsonl,
followup5-k.jsonl, followup5-k-pc.jsonl).

Pushes store the lowest-numbered register at the lowest address (the last item, rets or pc, highest); pops, loads and
stores of register lists use the same order (pop: rets/pc from the topmost word). rets keeps bits 26..1 of what is
written to it. Every model also records the runner's stub-address word at [sp_in - 4], which stays a changed
scratch word unless the exit's own push covers it.
"""
from semantics.p import insert as _insert, uextra as _uextra, sextra as _sextra

M = 0xFFFFFFFF
SR = "reti rete retx rets sr4 psr cnum uspn sspn icfgn icfgs icfg usp ssp sp pc".split()
N_ = {n: i for i, n in enumerate(SR)}

# Special registers that read as constants or as state of the unit. reti and usp were the same for every case of a
# batch but differed between batches (the ROM's state when the batch's command arrived, see hw/report5-k.md); every
# other register read the same all through.
CONST = {"cnum": 0, "uspn": 0, "sspn": 0, "icfgn": 0, "icfgs": 0, "icfg": 0x1090700, "ssp": 0x1c00e00,
         "rete": 0, "retx": 0, "sr4": 0}
STATE = {"batch-stack-001": {"reti": 0x1e00368, "usp": 0x1c011a0},
         "batch-followup5-k-main-000": {"reti": 0x1e01674},
         "batch-followup5-k-main-001": {"reti": 0x1e00e72, "usp": 0x1c011a0},
         "batch-followup5-k-main-002": {"reti": 0x1e01718, "usp": 0x1c0117c}}
STATE_DEFAULT = {"reti": 0x1e0168e, "usp": 0x1c01180}      # batch-misc-000 and batch-stack-004
RETS_MASK = 0x07FFFFFE      # rets holds bits 26..1 of what is written to it (a pop, or the runner's start-up)


def sr_value(name, flags, st):
    if name == "psr":
        return flags & 0xF
    if name == "rets":
        return st.rets & RETS_MASK
    if name == "sp":
        return st.sp
    if name == "pc":
        return st.stub
    if name in ("reti", "usp"):
        return STATE.get(st.batch, STATE_DEFAULT)[name]
    return CONST[name]


def rlist(k):
    """Registers of an rlist4 field: 0..3 is r3 down to r<k>, 4..15 is r<k> down to r4."""
    return list(range(k, 4)) if k < 4 else list(range(4, k + 1))


def bits(mask):
    return [i for i in range(16) if mask >> i & 1]


def fin(st, mem, sp_out=None):
    """The runner's entry stub address at [sp_in - 4] is a changed scratch word unless the case overwrites it or the
    exit's own push (the 16 words below the final sp, which check.py leaves out) covers it."""
    mem.setdefault(st.sp - 4, st.stub)
    return mem


def push(items):
    """items: [(value)...] lowest address first."""
    def f(R, fl, o, st):
        vals = items(R, o, st)
        sp = st.sp - 4 * len(vals)
        mem = {sp + 4 * k: v for k, v in enumerate(vals)}
        return {"sp": sp, "mem": mem, "flags": fl}
    return f


def pop(regs, special):
    """regs(o) -> register numbers (ascending, lowest address first); special: None, "rets" or "pc" (topmost)."""
    def f(R, fl, o, st):
        rs = regs(o)
        out = {"flags": fl}
        a = st.sp
        for r in rs:
            out.setdefault("regs", {})[r] = st.load(a)
            a += 4
        if special == "rets":
            out["rets"] = st.load(a) & RETS_MASK
            a += 4
        elif special == "pc":
            out["exit"] = int(st.load(a) == st.taken)
            a += 4
        out["sp"] = a
        return out
    return f


def srmask_vals(R, o, st, mask, fl):
    return [sr_value(SR[i], fl, st) for i in range(16) if mask >> i & 1]


MODELS = {}
for _name, _lead in (("rl", None), ("rets_rl", "rets")):
    MODELS["push." + _name] = push(lambda R, o, st, _l=_lead: [R[r] for r in rlist(o["raw"]["l"])] +
                                   ([st.rets] if _l else []))
    MODELS["pop." + _name] = pop(lambda o: rlist(o["raw"]["l"]), _lead)
MODELS["pop.pc_rl"] = pop(lambda o: rlist(o["raw"]["l"]), "pc")
MODELS["push.rets"] = push(lambda R, o, st: [st.rets])
MODELS["pop.pc"] = pop(lambda o: [], "pc")

for _id, _lead in (("rmask", None), ("rmask.c", None), ("rets_rmask", "rets"), ("rets_rmask.c", "rets")):
    MODELS["push." + _id] = push(lambda R, o, st, _l=_lead: [R[r] for r in bits(o["raw"]["m" if "m" in o["raw"] else "n"])] +
                                 ([st.rets] if _l else []))
for _id, _lead in (("rmask", None), ("rets_rmask", "rets"), ("pc_rmask", "pc")):
    MODELS["pop." + _id] = pop(lambda o: bits(o["raw"]["n"]), _lead)


def _push_sr(field):
    def f(R, fl, o, st):
        mask = o["raw"][field]
        vals = srmask_vals(R, o, st, mask, fl)
        sp = st.sp - 4 * len(vals)
        out = {"sp": sp, "mem": {sp + 4 * k: v for k, v in enumerate(vals)}}
        out["flags"] = 0 if mask >> N_["psr"] & 1 else fl      # pushing psr leaves N Z C V cleared
        return out
    return f


MODELS["push.srl"] = _push_sr("m")
MODELS["push.srmask"] = _push_sr("m")
MODELS["push.srmask.c"] = _push_sr("n")


def mov_r_sr(R, fl, o, st):
    return {"regs": {o["r"]: sr_value(SR[o["raw"]["s"]], fl, st)}, "flags": fl}


MODELS["mov.r_sr"] = mov_r_sr
MODELS["csync"] = lambda R, fl, o, st: {"flags": fl}


def add_sp(R, fl, o, st):
    return {"sp": (st.sp + o["n"]) & M, "flags": fl}


MODELS["add.sp_i"] = MODELS["add.sp_i.l"] = add_sp
MODELS["add.r_sp_i"] = MODELS["add.r_sp_i.l"] = lambda R, fl, o, st: {"regs": {o["r"]: (st.sp + o["n"]) & M},
                                                                      "flags": fl}


# register-list loads and stores through a base register: post1 [r+] reads/writes at r, base kept; post2 [r++]
# the same and base += 4n; pre1 [-r] at r - 4n, base kept; pre2 [--r] at r - 4n, base -= 4n
def _ldst(store, update, pre):
    def f(R, fl, o, st):
        rs = bits(o["raw"]["n"])
        base = R[o["r"]]
        start = (base - 4 * len(rs)) & M if pre else base
        out = {"flags": fl}
        if store:
            out["mem"] = {(start + 4 * k) & M: R[r] for k, r in enumerate(rs)}
        else:
            out["regs"] = {r: st.load((start + 4 * k) & M) for k, r in enumerate(rs)}
        if update:
            new = (base + (-4 if pre else 4) * len(rs)) & M
            out.setdefault("regs", {})
            if o["r"] not in rs or store:
                out["regs"][o["r"]] = new
        return out
    return f


for _n, _upd, _pre in (("post1", False, False), ("post2", True, False), ("pre1", False, True), ("pre2", True, True)):
    MODELS["ldm." + _n] = _ldst(False, _upd, _pre)
    MODELS["stm." + _n] = _ldst(True, _upd, _pre)


# bit fields with the position and width in a register: p = t[12:8], l = t[4:0]
def _field(model):
    def f(R, fl, o):
        t = R[o["t"]]
        return model(R, fl, dict(o, n=t >> 8 & 31, m=t & 31))
    return f


MODELS_PLAIN = {"insert.rrriirii": _field(_insert), "uextra.rrriirii": _field(_uextra),
                "sextra.rrriirii": _field(_sextra)}
for _k, _fn in MODELS_PLAIN.items():
    MODELS[_k] = (lambda fn: lambda R, fl, o, st: dict(zip(("regs", "flags"), fn(R, fl, o))))(_fn)


def _with_stub(fn):
    def f(R, fl, o, st):
        out = fn(R, fl, o, st)
        out["mem"] = fin(st, dict(out.get("mem", {})))
        out.setdefault("rets", st.rets & RETS_MASK)       # the runner's own write of rets is cut the same way
        return out
    return f


for _k in list(MODELS):
    MODELS[_k] = _with_stub(MODELS[_k])
