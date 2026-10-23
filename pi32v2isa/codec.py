# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Encode and decode single instructions from the table. The assembler and disassembler build on this."""

from .table import PLACEHOLDER


def _words(data, offset, n):
    """n little-endian 16-bit words from data, as one integer (first word highest), or None if short."""
    if offset + 2 * n > len(data):
        return None
    value = 0
    for k in range(n):
        value = (value << 16) | data[offset + 2 * k] | (data[offset + 2 * k + 1] << 8)
    return value


def _to_bytes(value, n):
    out = bytearray()
    for k in range(n):
        w = (value >> (16 * (n - 1 - k))) & 0xFFFF
        out += bytes((w & 0xFF, w >> 8))
    return bytes(out)


def fields_of(insn, data, offset=0):
    """The raw field values of insn encoded at data[offset:]."""
    value = _words(data, offset, len(insn.words))
    if value is None:
        return {}
    out = {}
    for letter in insn.fields:
        v = 0
        for pos in insn.field_bits(letter):
            v = (v << 1) | ((value >> (insn.nbits - 1 - pos)) & 1)
        out[letter] = v
    return out


def decode(table, data, offset=0):
    """(insn, field values, length in bytes) for the instruction at data[offset:], or None."""
    for insn in table.insns:
        value = _words(data, offset, len(insn.words))
        if value is not None and value & insn.mask == insn.value:
            return insn, fields_of(insn, data, offset), 2 * len(insn.words)
    return None


def encode(insn, values):
    """The bytes of insn with the given raw field values."""
    value = insn.value
    for letter in insn.fields:
        bits = insn.field_bits(letter)
        v = values[letter]
        if not 0 <= v < (1 << len(bits)):
            raise ValueError(f"{insn.id}: field {letter!r} value {v} does not fit {len(bits)} bits")
        for k, pos in enumerate(bits):
            if (v >> (len(bits) - 1 - k)) & 1:
                value |= 1 << (insn.nbits - 1 - pos)
    return _to_bytes(value, len(insn.words))


def operand(kind, raw, width):
    """How a raw field value is written in assembly."""
    if kind in ("gpr", "gpr_lo"):
        return f"r{raw}"
    if kind == "gpr_hi":
        return f"r{raw + 8}"
    if kind == "pair":
        return f"r{2 * raw + 1}_r{2 * raw}"
    if kind == "simm" and raw >= 1 << (width - 1):
        return str(raw - (1 << width))
    return str(raw)


def format(insn, values):
    """The assembly text of insn with the given raw field values."""
    def sub(m):
        letter = m.group(1)
        return operand(insn.fields[letter], values[letter], len(insn.field_bits(letter)))
    return PLACEHOLDER.sub(sub, insn.syntax)
