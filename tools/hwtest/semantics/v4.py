# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Run-4 models, including the recorded setup and readback instructions.

These describe the visible state in the tested ROM download context, not mode transitions,
interrupt delivery, event routing, or barrier ordering. ROM entry values of reti and usp
are measured context (as in k2.py); checking them is not independent evidence of their value.
"""
from pi32v2isa import codec, table

M = 0xFFFFFFFF
RETURN_MASK = 0x07FFFFFE
TAB = table.load()
ROM = {
    'batch-writes-001': {0: 0x1e01666},
    'batch-writes-021': {0: 0x1e00e7c},
    'batch-writes-022': {0: 0x1e0037e},
    'batch-writes-039': {12: 0x1c011a0},
    'batch-writes-044': {12: 0x1c011a0},
    'batch-writes-052': {0: 0x1e016d6},
    'batch-followup-002': {12: 0x1c011a0},
    'batch-writes-rest-005': {0: 0x1e00e6e},
    'batch-returns-003': {0: 0x1e016f6},
    'batch-returns-005': {0: 0x1e00386},
    'batch-retry-hangs-002': {0: 0x1e003ac},
}


def trace(R, f, o, st):
    """Evaluate the tested form and its recorded setup/readback; keep RAM entry and restore effects visible."""
    original = list(R)
    sr = dict(enumerate([0x1e0168e, 0, 0, st.rets & RETURN_MASK, 0, f, 0, 0, 0, 0, 0,
                         0x01090700, 0x1c01180, 0x1c00e00, st.sp, st.stub]))
    sr.update(ROM.get(st.batch, {}))
    entry = st.rec.get('entry', st.stub)
    mem = {st.sp - 4: entry}

    def read(s, pc):
        return pc if s == 15 else sr[s]

    def write(s, value):
        value &= M
        if s < 4:
            sr[s] = value & RETURN_MASK
        elif s == 5:
            sr[s] = value & 15
        elif s in (11, 12, 13, 14):
            sr[s] = value
        # In these probes sr4, cnum and the n/s bank registers read zero after writes;
        # mov.sr_r to pc fell through. No hidden state is modelled.

    parts = st.rec.get('before', []) + [{'id': st.rec['id'], 'values': st.rec['values']}] + st.rec.get('after', [])
    pc, layout = entry, []
    for part in parts:
        layout.append((pc, part))
        pc += len(codec.encode(TAB.by_id(part['id']), part['values']))
    next_pc, exit_ = entry, 0
    for pc, part in layout:
        if pc < next_pc:
            continue
        if pc != next_pc:
            raise ValueError('run-4 jump did not land on a context instruction')
        id_, v = part['id'], part['values']
        next_pc = pc + len(codec.encode(TAB.by_id(id_), v))
        if id_ == 'mov.r_sr':
            R[v['r']] = read(v['s'], pc)
        elif id_ == 'mov.sr_r':
            write(v['s'], R[v['r']])
        elif id_ == 'li.sr_u32':
            write(v['s'], v['n'])
        elif id_ == 'mov.rr':
            R[v['x']] = R[v['y']]
        elif id_ in ('li.s16', 'li.u32'):
            n = v['n']
            R[v['r']] = (n - 0x10000 if id_ == 'li.s16' and n & 0x8000 else n) & M
        elif id_ == 'st.w':
            addr = R[v['b']] + codec.value(TAB.by_id(id_).fields['n'], v['n'], len(TAB.by_id(id_).field_bits('n')))
            mem[addr & M] = R[v['d']]
        elif id_ == 'st.w.sp':
            addr = sr[14] + codec.value(TAB.by_id(id_).fields['n'], v['n'], len(TAB.by_id(id_).field_bits('n')))
            mem[addr & M] = R[v['r']]
        elif id_ == 'push.rmask':
            regs = [r for r in range(16) if v['m'] >> r & 1]
            sr[14] -= 4 * len(regs)
            for k, r in enumerate(regs):
                mem[sr[14] + 4 * k] = R[r]
        elif id_ == 'pop.rmask':
            for r in range(16):
                if v['n'] >> r & 1:
                    addr = sr[14]
                    R[r] = mem[addr] if addr in mem else st.load(addr)
                    sr[14] += 4
        elif id_ in ('pop.srl', 'pop.srmask'):
            mask = v.get('m', v.get('n'))
            addr = sr[14]
            sr[14] = addr + 4 * mask.bit_count()
            for s in range(16):
                if mask >> s & 1:
                    value = mem.get(addr, st.load(addr))
                    write(s, value)
                    if s == 15:
                        next_pc = value & RETURN_MASK
                    addr += 4
            if mask & 0x8000 and next_pc == st.taken:
                exit_ = 1
                break
        elif id_.startswith('mov.sp_'):
            # Dedicated sp=uspn/sspn yielded the normal usp/ssp values in this context.
            sr[14] = sr[12 if id_.endswith(('usp', 'uspn')) else 13]
        elif id_ in ('mov.usp_sp', 'mov.ssp_sp', 'mov.uspn_sp', 'mov.sspn_sp'):
            sr[12 if id_ in ('mov.usp_sp', 'mov.uspn_sp') else 13] = sr[14]
        elif id_ in ('cli', 'cli.r'):
            old = sr[11]
            sr[11] &= ~0x200
            if id_ == 'cli.r':
                R[v['x']] = old
        elif id_ == 'sti':
            sr[11] |= 0x200
        elif id_ == 'sti.r':
            sr[11] = (sr[11] & ~0x200) | (R[v['x']] & 0x200)
        elif id_ in ('rti', 'rtns', 'rtx', 'rthw', 'rte', 'rtss', 'callns.r'):
            bank = {'rti': 0, 'rtns': 0, 'rtx': 2, 'rthw': 2, 'rte': 1, 'rtss': 3, 'callns.r': 3}[id_]
            next_pc = sr[bank]
            if next_pc == st.taken:
                exit_ = 1
                break
        elif id_ == 'gotoss.xl':
            sr[3] = next_pc
            if next_pc + o['n'] != st.tgt:
                raise ValueError('untested gotoss target')
            exit_ = 1
            break
        elif id_ == 'bkpt':
            next_pc = mem.get(sr[14], st.load(sr[14]))
            sr[14] += 4
            if next_pc == st.taken:
                exit_ = 1
                break
        elif id_ not in ('ssync', 'lockclr', 'lockset', 'sevl', 'sevg', 'swi', 'wfe', 'trigger'):
            raise ValueError(f'{id_}: unsupported run-4 context instruction')
    mem = {a: value for a, value in mem.items()
           if a == st.sp - 4 or value != st.load(a)}
    return {'regs': {r: value for r, value in enumerate(R) if value != original[r]}, 'flags': sr[5],
            'sp': sr[14], 'rets': sr[3], 'mem': mem, 'exit': exit_}


MODELS = {id_: trace for id_ in (
    'ssync', 'lockclr', 'lockset', 'sevl', 'sevg', 'cli', 'sti', 'cli.r', 'sti.r',
    'mov.sr_r', 'li.sr_u32', 'pop.srl', 'pop.srmask',
    'mov.sp_usp', 'mov.sp_ssp', 'mov.usp_sp', 'mov.ssp_sp',
    'mov.sp_uspn', 'mov.sp_sspn', 'mov.uspn_sp', 'mov.sspn_sp',
    'rti', 'rtx', 'rte', 'rtns', 'rtss', 'rthw', 'gotoss.xl',
    'swi', 'bkpt', 'wfe', 'trigger',
)}


def and_block(R, f, o, st):
    # Seven unnamed encodings matched the AND-zero block in run 4's operand grid.
    yes = not (R[o['r']] & R[o['s']])
    regs = {8 + k: 0x100 + k for k in range(o['t'])} if yes else {12 + k: 0x200 + k for k in range(o['e'])}
    return {'regs': regs, 'flags': f}


for _n in range(1, 8):
    MODELS[f'if.unknown.rr.{_n}'] = and_block
