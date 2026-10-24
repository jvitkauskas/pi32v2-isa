# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Run-5 controlled return targets and AND-nonzero block aliases; no hidden-mode claims."""
from copy import copy
from semantics.v3 import block
from semantics.v4 import TAB, trace


def callns_targets(R, f, o, st):
    # All four return registers are seeded with distinct valid RAM markers in these programs.
    # Substitution preserves instruction length and the complete setup/readback trace.
    context = copy(st)
    context.rec = dict(st.rec, id=('rtss', 'rti', 'rtx', 'rte')[o['raw']['x'] & 3], values={})
    return trace(R, f, {}, context)


MODELS = {f'iff.ne.rr.{n}': block('ne', masked=True) for n in range(1, 7)}
MODELS['v5.callns-targets'] = callns_targets


def handler_context(R, f, o, st):
    """RAM hook programs, including the handler's saved stack, not interrupt-controller semantics.

    Vector 2's initial baseline comes from the independent RAM inspection; the post-power-cycle values
    below are measured setup/readback context, not independently validated pointers. The debug RETI values
    are measured ROM entry context, just as in v4.py; matching them is not independent validation.
    Unobserved vector contents are placeholders: they are restored and never escape into the result.
    """
    from pi32v2isa import codec
    tab = TAB
    original = list(R)
    # These ROM/RAM values are measured context, not an instruction's numerical prediction.
    reti = {
        'batch-handler-owned-008': 0x1e016d6,
        'batch-handler-routes-b-000': 0x1e00388,
        'batch-handler-routes-rest-002': 0x1e016d6,
        'batch-handler-rte-000': 0x1e00398,
        'batch-handler-rte-006': 0x1e00e6a,
        'batch-handler-slot-a-001': 0x1e01664,
        'batch-handler-slot-a-003': 0x1e00382,
    }.get(st.batch, 0x1e003ac)
    sr = dict(enumerate([reti, 0, 0, st.rets, 0, f, 0, 0, 0, 0, 0,
                         0x01090700, 0x1c01180, 0x1c00e00, st.sp, st.stub]))
    if st.batch in ('batch-handler-owned-004', 'batch-handler-owned-005'):
        vector2 = 0xf0a7356d
    elif st.batch.startswith(('batch-handler-rte-', 'batch-handler-slot-a-')) or st.batch in (
            'batch-handler-routes-b-000', 'batch-handler-routes-rest-000', 'batch-handler-routes-rest-002'):
        vector2 = 0xf0a73d6d
    else:
        vector2 = 0x1c00dd8
    mem = {st.sp - 4: st.rec.get('entry', st.stub),
           0x1c7fe00: 0, 0x1c7fe04: 0x1e0024e, 0x1c7fe08: vector2, 0x1c7ffe0: 0}
    seen, resume, context = R[5], R[4], R[7]
    for a in range(context, context + 80, 4):
        mem[a] = 0
    mem[seen] = mem[resume] = 0

    def load(a):
        return mem[a] if a in mem else st.load(a)

    def offset(id_, v):
        i = tab.by_id(id_)
        return codec.value(i.fields['n'], v['n'], len(i.field_bits('n')))

    def part(p):
        id_, v = p['id'], p['values']
        if id_ == 'mov.r_sr':
            R[v['r']] = sr[v['s']]
        elif id_ == 'mov.sr_r':
            s, value = v['s'], R[v['r']]
            sr[s] = value & (0x07fffffe if s < 4 else 15 if s == 5 else 0xffffffff)
        elif id_ in ('li.u32', 'li.s16'):
            n = v['n']
            R[v['r']] = (n - 65536 if id_ == 'li.s16' and n & 0x8000 else n) & 0xffffffff
        elif id_ == 'mov.rr':
            R[v['x']] = R[v['y']]
        elif id_ in ('ld.w', 'ld.w.l'):
            d, b = (v['d'], v['b']) if id_ == 'ld.w' else (v['r'], v['s'])
            R[d] = load(R[b] + offset(id_, v))
        elif id_ == 'st.w':
            mem[R[v['b']] + offset(id_, v)] = R[v['d']]
        elif id_ == 'st.w.sp':
            mem[sr[14] + offset(id_, v)] = R[v['r']]
        elif id_ not in ('csync', 'sevl'):
            raise ValueError(f'unsupported handler setup: {id_}')

    for p in st.rec['before']:
        part(p)
    id_ = st.rec['id']
    if id_ in ('syscall', 'bkpt', 'hbkpt'):
        if id_ == 'syscall':
            sr[14] = sr[13]
        bank = 0 if id_ == 'syscall' else 1
        sr[bank] = st.stub if id_ == 'hbkpt' else st.end
        if id_ == 'syscall':
            sr[11] = 0x01090200
        # Own handler: push rets and all GPRs, then flags; restore them before the selected return.
        sp = sr[14]
        for k, value in enumerate(R + [sr[3]]):
            mem[sp - 68 + 4 * k] = value
        mem[sp - 72] = sr[5]
        if st.rec.get('model') in ('v5.handler-routes', 'v5.handler-rte'):
            mem[context + 72] = 2 if id_ == 'syscall' else 0
        mem[seen] += 1
        for k, value in enumerate((sr[11], sr[0], sr[2], sr[1], sp)):
            mem[context + 52 + 4 * k] = value
        if st.rec.get('model') == 'v5.handler-rte' and id_ in ('bkpt', 'hbkpt'):
            mem[context + 76] = 1
            sr[1] = mem[resume]
        else:
            sr[0] = mem[resume]
        sr[14] = load(context + 32)  # observed return to the prior sp in these programs
    elif id_ == 'swi' and o['raw']['n'] != 0:
        raise ValueError('software-interrupt numbers other than zero are untested')
    elif id_ not in ('csync', 'sevg', 'wfe', 'swi'):
        raise ValueError(f'no handler-route model established for {id_}')
    for p in st.rec['after']:
        part(p)
    changed = {a: v for a, v in mem.items() if st.scratch <= a < st.scratch + len(st.words) * 4
               and v != st.load(a)}
    return {'regs': {r: v for r, v in enumerate(R) if v != original[r]}, 'flags': sr[5],
            'sp': sr[14], 'rets': sr[3], 'mem': changed}


MODELS['v5.handler'] = handler_context

MODELS['v5.handler-routes'] = handler_context
MODELS['v5.handler-rte'] = handler_context
