# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Deterministic outputs of the app3 nested software-IRQ programs.

The independent depth/entry/exit journal is checked by appverify.py. WFE timing and copex numerical
outputs remain unmodeled; no ordinary opcode model is overridden by these context programs.
"""
from pi32v2isa import codec, table

TAB = table.load()


def nesting(R, f, o, st):
    initial = list(R)
    stores = {}
    for p in st.rec['before']:
        id_, v = p['id'], p['values']
        if id_ in ('li.u8', 'li.s16', 'li.u32'):
            R[v['r']] = (v['n'] - (0x10000 if id_ == 'li.s16' and v['n'] & 0x8000 else 0)) & 0xffffffff
        elif id_ in ('st.w','st.w.l'):
            i = TAB.by_id(id_)
            off = codec.value(i.fields['n'],v['n'],len(i.field_bits('n')))
            stores[R[v['b' if id_=='st.w' else 'r']]+off] = R[v['d' if id_=='st.w' else 's']]
        elif id_ == 'ld.w.l':
            # Only the fresh retained handler count is read by these setup programs.
            if R[v['s']] != R[7] or v['n'] != 1:
                raise ValueError('unsupported nesting setup read')
            R[v['r']] = 0
        elif id_ not in ('cli', 'mov.sr_r'):
            raise ValueError('unsupported nesting setup: '+id_)
    gate = stores[R[7]+112]
    sources = stores[0x1eef13c]
    outer, child = (sources >> 1) & 7, (sources >> 5) & 7
    depth = 2 if gate == 1 and child > outer else 1
    # One outer request and one child request; the bounded main delay then samples both completed handlers.
    R[0], R[9], R[10], R[11] = 0, 2, depth, 4
    return {'regs':{r:v for r,v in enumerate(R) if v != initial[r]}, 'flags':6}


MODELS = {'app3.nesting':nesting}
