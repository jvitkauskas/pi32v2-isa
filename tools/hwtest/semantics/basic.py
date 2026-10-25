# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Models of the self-test forms (see check.py for the interface)."""


def _like(long_id):
    """The 16-bit three-register add and sub set N Z C V as their 32-bit forms do (hw/fm1-2026-10-24: 18 cases
    each)."""
    def model(R, f, o):
        from semantics.p import MODELS as P
        w, fl = P[long_id](R, f, {"r": o["d"], "s": o["a"], "t": o["b"]})
        return {o["d"]: w[o["d"]]}, fl
    return model


MODELS = {
    "nop": lambda R, f, o: ({}, f),
    "mov.rr": lambda R, f, o: ({o["x"]: R[o["y"]]}, f),         # moves and constants leave the flags alone
    "add.rrr": _like("add.rrr.l"),
    "sub.rrr": _like("sub.rrr.l"),
    "li.u8": lambda R, f, o: ({o["r"]: o["n"]}, f),
    "lsl.rri": lambda R, f, o: ({o["d"]: R[o["s"]] << o["n"] if o["n"] < 32 else 0}, None),
}
