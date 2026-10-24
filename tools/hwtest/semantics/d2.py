# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Format-2 models for memory DSP multiplies and visible cache state (analyst D).

All original run-2 cases agree. Followup5-d probes overlap combinations and arithmetic
boundaries missing for individual forms; cache contents/timing are not modelled.
"""
from semantics._r_util import sext

M32 = (1 << 32) - 1
M64 = (1 << 64) - 1
MODELS = {}


def _multiply(kind, widths, addressing, signed, accumulate):
    def model(R, flags, op, st):
        a = st.load(R[op['s']], widths[0] // 8)
        writes = {}
        if kind == 'mem1':
            if addressing == 'i':
                b = R[op['t']]
                inc = op['n']
            else:
                b = R[op['u']]
                inc = R[op['t']]
            writes[op['s']] = R[op['s']] + inc
        else:
            if addressing == 'i':
                second, inc_a, inc_b = op['t'], op['n'], op['m']
            else:
                second = op['u']
                inc_a = sext(R[op['t']] >> 16, 16)
                inc_b = sext(R[op['t']], 16)
            b = st.load(R[second], widths[1] // 8)
            # Shared bases retain the first operand's increment.
            writes[second] = R[second] + inc_b
            writes[op['s']] = R[op['s']] + inc_a
        if signed:
            a, b = sext(a, widths[0]), sext(b, widths[1])
        product = (a * b) & M64
        d = op['r']
        result = product
        if accumulate:
            old = R[d] | R[d + 1] << 32
            if accumulate > 0:
                result = old + product
                carry = result >> 64
            else:
                result = old - product
                carry = int(old >= product)
            flags = flags & ~2 | carry << 1
        result &= M64
        # Pair results take precedence over coincident pointer updates.
        writes.update({d: result & M32, d + 1: result >> 32})
        return {'regs': writes, 'flags': flags}
    return model


for _operation, _acc in (('mul', 0), ('madd', 1), ('msub', -1)):
    for _sign in ('u', 's'):
        for _size, _bits in (('h', 16), ('w', 32)):
            for _addr in ('i', 'r'):
                MODELS[f'{_operation}.mem1.{_size}.{_addr}.{_sign}'] = _multiply(
                    'mem1', (_bits, 32), _addr, _sign == 's', _acc)
        # The .hh.rh encoding executes like .hw.rh: its second load is 32 bits.
        for _size, _bits in (('hh', (16, 32)), ('hw', (16, 32)), ('ww', (32, 32))):
            for _addr in ('i', 'rh'):
                if _size == 'hh' and _addr == 'i':
                    continue  # These six encodings reset the FM-1; no returned state to model.
                MODELS[f'{_operation}.mem2.{_size}.{_addr}.{_sign}'] = _multiply(
                    'mem2', _bits, _addr, _sign == 's', _acc)


def _cache(R, flags, op, st):
    # Only architecturally visible state was recorded; cache effects are not measured.
    return {'flags': flags}


for _id in ('flush', 'flushinv', 'iflush', 'pfetch'):
    MODELS[_id] = _cache
