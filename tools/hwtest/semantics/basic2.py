# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Examples of format-2 models (memory, branches; see check.py for the interface)."""


def ld_w(R, f, o, st):
    return {"regs": {o["d"]: st.load(R[o["b"]] + o["n"])}, "flags": f}


def st_w(R, f, o, st):
    return {"mem": {(R[o["b"]] + o["n"]) & 0xFFFFFFFF: R[o["d"]]}, "flags": f}


def beqz(R, f, o, st):
    return {"exit": int(R[o["r"]] == 0), "flags": f}


def rts(R, f, o, st):
    return {"exit": 1, "flags": f}


MODELS = {"ld.w": ld_w, "st.w": st_w, "beqz": beqz, "rts": rts}
