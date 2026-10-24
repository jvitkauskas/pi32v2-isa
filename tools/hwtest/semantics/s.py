# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""FM-1 float/divide models, hw/fm1-2026-10-24.

Exact rational arithmetic avoids host rounding/NaN conventions. Checked against
results.jsonl, followup-s.jsonl and followup-s2.jsonl; see hw/report-s.md
for measured rounding, NaN-classification and flag behavior.
"""
from fractions import Fraction
import math

MASK = 0xFFFFFFFF


def signed(n, width=32):
    return n - (1 << width) if n >> (width - 1) else n


def decode(bits, eb=8, fb=23):
    """Finite binary floating-point value as an exact fraction."""
    exponent = bits >> fb & ((1 << eb) - 1)
    significand = bits & ((1 << fb) - 1)
    if exponent:
        significand |= 1 << fb
    shift = (exponent or 1) - ((1 << (eb - 1)) - 1) - fb
    value = Fraction(significand << max(shift, 0), 1 << max(-shift, 0))
    return -value if bits >> (eb + fb) else value


def kind(bits, eb=8, fb=23):
    if bits >> fb & ((1 << eb) - 1) != (1 << eb) - 1:
        return 'finite'
    return 'nan' if bits & ((1 << fb) - 1) else 'inf'


def encode(value, signzero=0, eb=8, fb=23):
    """Round an exact fraction to nearest, ties to even (binary32/16)."""
    sign = int(value < 0) if value else signzero
    value = abs(value)
    if not value:
        return sign << (eb + fb)
    bias = (1 << (eb - 1)) - 1
    exponent = value.numerator.bit_length() - value.denominator.bit_length()
    power = Fraction(2) ** exponent
    if value < power:
        exponent -= 1
    shift = max(exponent, 1 - bias) - fb
    scaled = value / (Fraction(2) ** shift)
    n, rem = divmod(scaled.numerator, scaled.denominator)
    if 2 * rem > scaled.denominator or (2 * rem == scaled.denominator and n & 1):
        n += 1
    if n >= 1 << (fb + 1):
        n >>= 1
        exponent += 1
    expbits = max(1, exponent + bias) if n >= 1 << fb else 0
    if expbits >= (1 << eb) - 1:
        return (sign << (eb + fb)) | (((1 << eb) - 1) << fb)
    return (sign << (eb + fb)) | (expbits << fb) | (n & ((1 << fb) - 1))


def compare(a, b):
    if kind(a) == 'nan' or kind(b) == 'nan':
        return 3
    # Monotonic integer keys, with both signed zeros equal.
    def key(x):
        return -(x & 0x7FFFFFFF) if x >> 31 else x
    return 8 if key(a) < key(b) else 2 if key(a) > key(b) else 6


def arithmetic(a, b, operation, accumulator=None):
    """Nearest-even finite arithmetic; either NaN class gives 0x7f800001."""
    inputs = (a, b) if accumulator is None else (a, b, accumulator)
    if any(kind(x) == 'nan' for x in inputs):
        return 0x7F800001
    if accumulator is not None:
        # The product rounds to binary32 before accumulation: both cancellation
        # and intermediate-overflow/underflow witnesses distinguish this from FMA.
        product = arithmetic(a, b, 'mul')
        return arithmetic(accumulator, product, 'sub' if operation == 'msub' else 'add')
    if operation == 'sub':
        b ^= 0x80000000
        operation = 'add'
    ka, kb = kind(a), kind(b)
    sign = (a ^ b) >> 31
    inf = 0x7F800000 | (sign << 31)
    if operation == 'mul':
        if (ka == 'inf' and not (b & 0x7FFFFFFF)) or (kb == 'inf' and not (a & 0x7FFFFFFF)):
            return 0x7F800001
        if ka == 'inf' or kb == 'inf':
            return inf
        return encode(decode(a) * decode(b), sign)
    if operation == 'div':
        if (ka == 'inf' and kb == 'inf') or (not (a & 0x7FFFFFFF) and not (b & 0x7FFFFFFF)):
            return 0x7F800001
        if ka == 'inf' or not (b & 0x7FFFFFFF):
            return inf
        if kb == 'inf':
            return sign << 31
        return encode(decode(a) / decode(b), sign)
    if ka == 'inf' and kb == 'inf' and (a ^ b) >> 31:
        return 0x7F800001
    if ka == 'inf':
        return a
    if kb == 'inf':
        return b
    return encode(decode(a) + decode(b), (a & b) >> 31)


def fp_operation(operation):
    def model(R, f, o):
        acc = R[o['r']] if operation in ('madd', 'msub') else None
        return {o['r']: arithmetic(R[o['s']], R[o['t']], operation, acc)}, f
    return model


def minmax(maximum):
    def model(R, f, o):
        a, b = R[o['s']], R[o['t']]
        flags = compare(a, b)
        if kind(a) == 'nan':
            # One NaN loses to the number; two NaNs select t unchanged.
            return {o['r']: b}, flags
        if kind(b) == 'nan':
            return {o['r']: a}, flags
        if not (a & 0x7FFFFFFF) and not (b & 0x7FFFFFFF):
            return {o['r']: (a & b) if maximum else (a | b)}, flags
        choose_a = flags == (2 if maximum else 8)
        return {o['r']: a if choose_a else b}, flags
    return model


ROUND = {'even': round, 'trunc': math.trunc, 'ceil': math.ceil, 'floor': math.floor}


def convert(operation, rounding='even'):
    def model(R, f, o):
        bits = R[o['s']]
        k = kind(bits)
        if operation in ('itof', 'utof'):
            result = encode(Fraction(signed(bits) if operation == 'itof' else bits))
        elif operation == 'half':
            sign = bits >> 31
            if k == 'finite':
                result = encode(decode(bits), sign, 5, 10)
            else:
                # Both NaN signs/classes measured: retain sign/class, discard payload.
                result = (sign << 15) | (0x7C00 if k == 'inf' else
                                         0x7E00 if bits & 0x400000 else 0x7C01)
            result |= R[o['r']] & 0xFFFF0000
        elif operation == 'full':
            bits &= 0xFFFF
            k = kind(bits, 5, 10)
            if k == 'finite':
                result = encode(decode(bits, 5, 10), bits >> 15)
            else:
                # As above, retain NaN sign/class and discard payload.
                result = ((bits >> 15) << 31) | (0x7F800000 if k == 'inf' else
                                                0x7FC00000 if bits & 0x200 else 0x7F800001)
        elif operation == 'ftof':
            if k == 'nan':
                result = (bits & 0x80000000) | 0x7FC00000
            elif k == 'inf':
                result = bits
            else:
                result = encode(Fraction(ROUND[rounding](decode(bits))), bits >> 31)
        else:
            lo, hi = (-(1 << 31), (1 << 31) - 1) if operation == 'ftoi' else (0, MASK)
            result = lo if bits >> 31 else hi
            if k == 'finite':
                result = min(hi, max(lo, ROUND[rounding](decode(bits))))
        return {o['r']: result}, f
    return model


def divide(pair, is_signed):
    def model(R, f, o):
        numerator = R[o['s']]
        if pair:
            numerator |= R[o['s'] + 1] << 32
        denominator = R[o['t']]
        if is_signed:
            numerator = signed(numerator, 64 if pair else 32)
            denominator = signed(denominator)
        # All four forms return zero for zero divisors, including nonzero/0.
        quotient = abs(numerator) // abs(denominator) if denominator else 0
        if (numerator < 0) != (denominator < 0):
            quotient = -quotient
        writes = {o['r']: quotient & MASK}
        if pair:
            writes[o['r'] + 1] = quotient >> 32 & MASK
            return writes, f
        value = quotient & MASK
        return writes, (f & 3) | (4 if not value else 0) | (8 if value >> 31 else 0)
    return model


MODELS = {f'{op}.f.rrr': fp_operation(op) for op in ('add', 'sub', 'mul', 'div', 'madd', 'msub')}
MODELS.update({'fcmp.rr': lambda R, f, o: ({}, compare(R[o['r']], R[o['s']])),
               'fmin.rrr': minmax(False), 'fmax.rrr': minmax(True)})
MODELS.update({f'{op}.{mode}.rr': convert(op, mode) for op in ('ftoi', 'ftou', 'ftof') for mode in ROUND})
MODELS.update({f'{op}.rr': convert(op) for op in ('itof', 'utof')})
MODELS.update({f'ftof.{op}.rr': convert(op) for op in ('half', 'full')})
MODELS.update({f'div.{sign}.{shape}': divide(shape == 'ppr', sign == 's')
               for sign in ('s', 'u') for shape in ('rrr', 'ppr')})
