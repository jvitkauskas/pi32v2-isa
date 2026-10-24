# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Models of the self-test forms (see check.py for the interface)."""

MODELS = {
    "nop": lambda R, f, o: ({}, f),
    "mov.rr": lambda R, f, o: ({o["x"]: R[o["y"]]}, None),
    "add.rrr": lambda R, f, o: ({o["d"]: R[o["a"]] + R[o["b"]]}, None),
    "sub.rrr": lambda R, f, o: ({o["d"]: R[o["a"]] - R[o["b"]]}, None),
    "li.u8": lambda R, f, o: ({o["r"]: o["n"]}, None),
    "lsl.rri": lambda R, f, o: ({o["d"]: R[o["s"]] << o["n"] if o["n"] < 32 else 0}, None),
}
