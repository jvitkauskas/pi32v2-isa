# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Helpers for the models in p.py: 32-bit arithmetic and the condition flags.

The low four psr bits, as the hardware showed them (hw/fm1-2026-10-24):
bit 3 = N (result bit 31), bit 2 = Z (result is zero), bit 1 = C (carry), bit 0 = V (signed overflow).
"""
M = 0xFFFFFFFF
N_, Z_, C_, V_ = 8, 4, 2, 1


def s32(x):
    x &= M
    return x - (1 << 32) if x >> 31 else x


def nz(res):
    """The N and Z bits for a 32-bit result."""
    res &= M
    return (N_ if res >> 31 else 0) | (Z_ if res == 0 else 0)


def keep(f, mask):
    """The old flag bits selected by mask."""
    return f & mask


def add_full(a, b, c=0):
    """a + b + c: (result, carry out, signed overflow)."""
    s = (a & M) + (b & M) + c
    r = s & M
    return r, s >> 32, int(s32(a) + s32(b) + c != s32(r))


def sub_full(a, b, c=1):
    """a - b - (1 - c), computed as a + ~b + c: C is 1 when there was no borrow."""
    r, cc, _ = add_full(a, ~b & M, c)
    return r, cc, int(s32(a) - s32(b) - (1 - c) != s32(r))


def arith_flags(r, c, v):
    return nz(r) | (C_ if c else 0) | (V_ if v else 0)


def rev32(x):
    return int(f"{x & M:032b}"[::-1], 2)


def shift32(kind, x, c, cin):
    """A 32-bit shift by c (0..255; counts above 32 act as 32): (result, carry).

    Count 0 changes nothing, carry included. Otherwise the carry is the last bit shifted out.
    kind: lsl, lsr, asr, shl3 (signed saturating shift left)."""
    x &= M
    if c == 0:
        return x, cin
    c = min(c, 32)
    if kind == "lsl":
        return (x << c) & M, x >> (32 - c) & 1
    if kind == "lsr":
        return x >> c, x >> (c - 1) & 1
    if kind == "asr":
        return (s32(x) >> c) & M, x >> (c - 1) & 1
    if kind == "shl3":
        v = s32(x) << c
        if v > 0x7FFFFFFF:
            v = 0x7FFFFFFF
        elif v < -0x80000000:
            v = -0x80000000
        return v & M, x >> (32 - c) & 1
    raise ValueError(kind)

M64 = (1 << 64) - 1


def s64(x):
    x &= M64
    return x - (1 << 64) if x >> 63 else x


def shift64(kind, x, c, cin):
    """The 64-bit twin of shift32 (counts above 64 act as 64); kind also has ror (carry kept) and rorc
    (rotate right through the carry, 65 bits)."""
    x &= M64
    if kind == "ror":
        c %= 64
        return ((x >> c) | (x << (64 - c))) & M64, cin
    if c == 0:
        return x, cin
    c = min(c, 64)
    if kind == "rorc":
        v = (cin << 64) | x
        k = (65 - c) % 65
        v = ((v << k) | (v >> (65 - k))) & ((1 << 65) - 1)
        return v & M64, v >> 64
    if kind == "lsl":
        return (x << c) & M64, x >> (64 - c) & 1
    if kind == "lsr":
        return x >> c, x >> (c - 1) & 1
    if kind == "asr":
        return (s64(x) >> c) & M64, x >> (c - 1) & 1
    if kind == "shl3":
        v = max(-(1 << 63), min((1 << 63) - 1, s64(x) << c))
        return v & M64, x >> (64 - c) & 1
    raise ValueError(kind)
