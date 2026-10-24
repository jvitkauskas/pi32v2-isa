# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Helpers shared by analyst R's models."""

M32 = 0xFFFFFFFF
M16 = 0xFFFF


def half(v, high):
    return (v >> 16 if high else v) & M16


def sethalf(old, high, h):
    h &= M16
    return (old & 0x0000FFFF | h << 16) if high else (old & 0xFFFF0000 | h)


def s16(v):
    v &= M16
    return v - 0x10000 if v & 0x8000 else v


def s32(v):
    v &= M32
    return v - (1 << 32) if v & 0x80000000 else v


def s64(v):
    v &= (1 << 64) - 1
    return v - (1 << 64) if v >> 63 else v


def usat(v, bits):
    return max(0, min((1 << bits) - 1, v))


def ssat(v, bits):
    return max(-(1 << bits - 1), min((1 << bits - 1) - 1, v))


def lane(a, b, sign, mode, bits=16):
    """One lane of an add/subtract with a mode word such as "(ssat,x2)"; a and b are raw `bits`-bit lanes.

    Returns the raw lane result."""
    parts = mode.strip("()").split(",")
    rnd = "rnd" in parts
    kind = [p for p in parts if p != "rnd" and p != "x2"][0]
    signed = kind in ("ssat", "savg")
    if signed:
        a, b = sext(a, bits), sext(b, bits)
    t = a + sign * b
    if kind in ("usat", "ssat"):
        if "x2" in parts:
            t *= 2
            if sign < 0 and not signed and t >= 1 << bits:
                t = 0  # observed on the unit: a doubled difference that overflows gives 0, not the maximum
        t = ssat(t, bits) if signed else usat(t, bits)
    else:
        t = (t + (1 if rnd else 0)) >> 1
    return t & ((1 << bits) - 1)


def sext(v, bits):
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v


def shift_lane(kind, v, n, bits):
    """Shift a raw `bits`-bit lane by n (>= 0): lsl, lsr, asr or shl3 (saturating signed shift left)."""
    m = (1 << bits) - 1
    if kind == "lsl":
        return (v << n) & m if n < bits else 0
    if kind == "lsr":
        return v >> n if n < bits else 0
    if kind == "asr":
        return (sext(v, bits) >> min(n, bits)) & m
    if kind == "shl3":
        return ssat(sext(v, bits) << n, bits) & m
    raise ValueError(kind)
