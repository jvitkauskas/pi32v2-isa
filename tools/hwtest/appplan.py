#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Write experiment plan/vector stubs beside gen.py --app batches. No device access.

appplan.py DIR --run-id N [--modes 1,0,...] [--priority 3]
Build with fm1app.py DIR/app.fwsc app/experiment.S DIR/app.S DIR/plan.S.
Mode 3 requires app/advanced.S and starts CPU1 once for that batch; repeated core restarts are experimental.
Retained header/journal layout is documented in app/platform.S and APP.md.
"""
import argparse
import json
from pathlib import Path


def plan(directory, run_id, modes, priority):
    manifests = sorted(directory.glob('batch-*.json'))
    if len(modes) != len(manifests):
        raise ValueError('one mode per batch is required')
    priorities = [priority]*len(modes) if isinstance(priority,int) else priority
    if len(priorities)!=len(modes) or any(not 0 <= p <= 7 for p in priorities) or any(m not in (0,1,2,3) for m in modes):
        raise ValueError('priority must be 0..7 and modes 0, 1, 2 or 3')
    lines = ['/* Own generated vector stubs; no vendor assembly. */', '.section .rodata', '.p2align 2',
             '.globl app_plan, app_vectors', f'app_plan: .4byte {run_id}']
    for p, mode, priority in zip(manifests, modes, priorities):
        m = json.loads(p.read_text())
        if len(m['cases']) != 3:
            raise ValueError('experiments require two calibrations and one probe per batch')
        c = m['cases'][2]
        lines += [f'.4byte {c["stub"] + len(bytes.fromhex(c["bytes"])):#x}, {mode}, {priority}']
    lines += ['app_vectors:'] + [f'.4byte app_vec_{n}' for n in range(128)]
    lines += ['.text']
    for n in range(128):
        lines += [f'app_vec_{n}:', '[--sp] = {rets, r15-r0}', 'r0 = psr', '[--sp] = {r0}',
                  f'r0 = {n}', 'goto app_trap']
    return '\n'.join(lines) + '\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path)
    p.add_argument('--run-id', required=True, type=lambda x: int(x, 0))
    p.add_argument('--modes', required=True, help='one comma-separated mode per batch')
    p.add_argument('--priority', type=int, default=3)
    p.add_argument('--priorities', help='optional comma-separated priority per batch')
    a = p.parse_args()
    (a.directory / 'plan.S').write_text(plan(a.directory, a.run_id, [int(x) for x in a.modes.split(',')], [int(x) for x in a.priorities.split(',')] if a.priorities else a.priority))


if __name__ == '__main__':
    main()
