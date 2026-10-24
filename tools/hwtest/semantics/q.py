# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""DSP models inferred from hw/fm1-2026-10-24; see hw/report-q.md.

Inputs are read before writes, including overlapping register pairs. Unprobed
minimum-integer abs/negs and overflowing sad4 cases remain hypotheses pending
followup-q.json.
"""
import operator

MASK = 0xFFFFFFFF


def signed(x, bits):
    x &= (1 << bits) - 1
    return x - (1 << bits) if x >> (bits - 1) else x


def lanes(x, bits, total=32):
    return [(x >> p) & ((1 << bits) - 1) for p in range(0, total, bits)]


def join(xs, bits):
    return sum((x & ((1 << bits) - 1)) << (i * bits) for i, x in enumerate(xs))


def pair(R, r):
    return R[r] | R[r + 1] << 32


def writes_pair(r, x):
    return {r: x & MASK, r + 1: (x >> 32) & MASK}


def half(R, r, part):
    return (R[r] >> (16 if part == '.h' else 0)) & 0xFFFF


def write_half(R, r, part, x):
    shift = 16 if part == '.h' else 0
    return {r: (R[r] & ~(0xFFFF << shift)) | ((x & 0xFFFF) << shift)}


def clip(x, bits, is_signed):
    return max(-(1 << (bits - 1)), min((1 << (bits - 1)) - 1, x)) if is_signed else max(0, min((1 << bits) - 1, x))


def nz(f, x, bits=32):
    x &= (1 << bits) - 1
    return (f & 3) | (4 if x == 0 else 0) | (8 if x >> (bits - 1) else 0)


def unary(kind, shape):
    def model(R, f, o):
        bits = 32 if shape == 'rr' else 16
        x = half(R, o['s'], o['m']) if shape == 'rhrh' else R[o['s']]
        xs = lanes(x, bits)
        ys = [abs(signed(v, bits)) if kind == 'abs' else -signed(v, bits) for v in xs]
        y = join(ys, bits)
        return (write_half(R, o['r'], o['n'], y) if shape == 'rhrh' else {o['r']: y}), f
    return model


def minmax(kind, shape):
    def model(R, f, o):
        bits = 32 if shape == 'rrr' else 16
        a = half(R, o['s'], o['m']) if shape == 'rhrhrh' else R[o['s']]
        b = half(R, o['t'], o['p']) if shape == 'rhrhrh' else R[o['t']]
        choose = max if kind.endswith('max') else min
        conv = (lambda x: signed(x, bits)) if kind.startswith('s') else (lambda x: x)
        y = join([choose(conv(x), conv(z)) for x, z in zip(lanes(a, bits), lanes(b, bits))], bits)
        return (write_half(R, o['r'], o['n'], y) if shape == 'rhrhrh' else {o['r']: y}), f
    return model


def compare(family, condition, is_pair):
    def model(R, f, o):
        bits, total = (16, 64) if is_pair else (8, 32)
        a = pair(R, o['s']) if is_pair else R[o['s']]
        b = pair(R, o['t']) if is_pair else R[o['t']]
        conv = (lambda x: signed(x, bits)) if family.endswith('s') else (lambda x: x)
        pred = getattr(operator, condition)
        matches = [pred(conv(x), conv(y)) for x, y in zip(lanes(a, bits, total), lanes(b, bits, total))]
        if family.startswith('all'):
            y = ((1 << total) - 1) if all(matches) else 0
        elif family.startswith('any'):
            y = ((1 << total) - 1) if any(matches) else 0
        else:
            y = join([-int(v) for v in matches], bits)
        return (writes_pair(o['r'], y) if is_pair else {o['r']: y}), f
    return model


def saturate(bits, is_signed, is_half=False):
    def model(R, f, o):
        x = half(R, o['s'], o['m']) if is_half else R[o['s']]
        if is_signed:
            x = signed(x, 16 if is_half else 32)
        y = clip(x, bits, is_signed)
        return (write_half(R, o['r'], o['n'], y) if is_half else {o['r']: y}), nz(f, y, 16 if is_half else 32)
    return model


def pack_bytes(mode, source='s'):
    def model(R, f, o):
        xs = lanes(pair(R, o[source]), 16, 64)
        actual = o['n'] if mode == 'enum' else mode
        if actual == '(usat)':
            xs = [clip(x, 8, False) for x in xs]
        elif actual == '(ssat)':
            xs = [clip(signed(x, 16), 8, True) for x in xs]
        elif actual == 'stou':
            xs = [clip(signed(x, 16), 8, False) for x in xs]
        return {o['r']: join(xs, 8)}, f
    return model


def unpack(is_signed, dest='r'):
    def model(R, f, o):
        xs = lanes(R[o['s']], 8)
        if is_signed:
            xs = [signed(x, 8) for x in xs]
        return writes_pair(o[dest], join(xs, 16)), f
    return model


def mts(bits):
    def model(R, f, o):
        # Low lane first: t0, s0, t1, s1, ...
        xs = [v for a, b in zip(lanes(R[o['s']], bits), lanes(R[o['t']], bits)) for v in (b, a)]
        return writes_pair(o['r'], join(xs, bits)), f
    return model


def sad(R, f, o):
    # usat suggests clipping; no original case overflowed a lane.
    acc = lanes(pair(R, o['r']), 16, 64)
    xs = [min(65535, c + abs(a - b)) for c, a, b in zip(acc, lanes(R[o['s']], 8), lanes(R[o['t']], 8))]
    return writes_pair(o['r'], join(xs, 16)), f


def shift(shape, saturating=False):
    def model(R, f, o):
        bits = 64 if shape == 'pr' else 16 if shape in ('rhrhr', 'v') else 32
        count_reg = o['s'] if shape == 'pr' else o['t']
        n = signed(R[count_reg], {16: 5, 32: 6, 64: 7}[bits])
        x = pair(R, o['r']) if shape == 'pr' else half(R, o['s'], o['m']) if shape == 'rhrhr' else R[o['s']]
        def one(v):
            value = signed(v, bits) if saturating else v
            value = value << n if n >= 0 else value >> -n
            return clip(value, bits, True) if saturating else value
        y = join([one(v) for v in lanes(x, bits, 64 if shape == 'pr' else bits if shape != 'v' else 32)], bits)
        carry = ((x >> (bits - n if n > 0 else -n - 1)) & 1) if n else ((f >> 1) & 1)
        shifted_flags = (f & ~2) | (carry << 1)
        if shape == 'pr':
            return writes_pair(o['r'], y), shifted_flags
        if shape == 'rhrhr':
            return write_half(R, o['r'], o['n'], y), f
        return {o['r']: y}, f if shape == 'v' else nz(shifted_flags, y)
    return model


MODELS = {}
for _shape in ('rr', 'rhrh', 'v.rr'):
    for _kind in ('abs', 'negs'):
        MODELS[f'{_kind}.{_shape}'] = unary(_kind, _shape)
for _shape in ('rrr', 'rhrhrh', 'v.rrr'):
    for _kind in ('smin', 'smax', 'umin', 'umax'):
        MODELS[f'{_kind}.{_shape}'] = minmax(_kind, _shape)
for _family in ('all', 'alls', 'any', 'anys', 'cmp', 'cmps'):
    for _cond in (('ge', 'gt', 'le', 'lt') if _family.endswith('s') else ('eq', 'ne', 'ge', 'gt', 'le', 'lt')):
        for _shape in ('rrr', 'ppp'):
            MODELS[f'{_family}.{_cond}.{_shape}.v'] = compare(_family, _cond, _shape == 'ppp')
for _sign in ('s', 'u'):
    MODELS[f'sat8.{_sign}.rhrh'] = saturate(8, _sign == 's', True)
    MODELS[f'sat16.{_sign}.rr'] = saturate(16, _sign == 's')
    # Revision-3 spellings execute like sat16 and packb on this AC791N.
    MODELS[f'sat8.{_sign}.rr'] = saturate(16, _sign == 's')
    MODELS[f'vsat16.{_sign}.rp'] = pack_bytes('(ssat)' if _sign == 's' else '(usat)', 'p')
    MODELS[f'unpackb.{_sign}.pr'] = unpack(_sign == 's')
    MODELS[f'unpack4.{_sign}.pr'] = unpack(_sign == 's', 'p')
for _bits in (8, 16, 24):
    MODELS[f'align{_bits}.rrr'] = lambda R, f, o, n=_bits: ({o['r']: ((R[o['s']] << 32) | R[o['t']]) >> n}, f)
MODELS.update({
    'pack.rrhrh': lambda R, f, o: ({o['r']: half(R, o['s'], o['n']) << 16 | half(R, o['t'], o['m'])}, f),
    'packb.rp': pack_bytes('truncate'),
    'packb.rpe': pack_bytes('enum'),
    'packb.rp.stou': pack_bytes('stou'),
    'mts0.prr': mts(8),
    'mts1.prr': mts(16),
    'sad4.acc.prr': sad,
    'xchg.pr': shift('pr'),
    'xchg.pr.sat': shift('pr', True),
    'xchg.rhrhr': shift('rhrhr'),
    'xchg.rhrhr.sat': shift('rhrhr', True),
    'xchg.rrr.sat': shift('rrr', True),
    'xchg.v.rrr': shift('v'),
    'xchg.rrr.sat.v': shift('v', True),
})
