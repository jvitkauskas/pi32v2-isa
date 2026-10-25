#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Check app4 startup, live-worker and stop evidence, plus the explicit application assertions.

This verifies a finite experiment protocol, not a universal event or memory model.
"""
import argparse
import json
from pathlib import Path
import appverify


def verify(directory):
    n, errors = appverify.verify(directory)
    attempts = {a['run_id']: a for a in json.loads((directory/'attempts.json').read_text())}
    records = [json.loads(s) for s in (directory/'results.jsonl').read_text().splitlines()]
    batches = {r['batch'] for r in records}
    completed = set()
    for wave in json.loads((directory/'observations.json').read_text()):
        a = attempts[wave['run_id']]
        persistent = a.get('profile','').strip() == 'dual-persist'
        for k, j in enumerate(wave['batches']):
            name, s = j['batch'], j['samples']
            def require(ok, message):
                if not ok: errors.append(f'{name}: {message}')
            # The first eight boot-starts journals were invalidated by an intentional-reset harness bug.
            # Their samples remain evidence of startup, but they must never have instruction results.
            startup = j['status']==2 or a['wave']=='boot-starts'
            if startup:
                nonce = wave['run_id'] ^ ((1 if persistent else k+1)<<16)
                require(s[0] == (3 if persistent and k else 1), 'wrong initial/live startup mode')
                require(s[4] == nonce and s[20] == nonce, 'missing matching ready nonce')
                require(s[5:9] == [1,0x1c12000,0x1c14000,0x1c12000], 'wrong core/stack identity')
                require(s[22:26] == [1,0x1c12000,0x1c14000,0x1c12000], 'wrong peer identity snapshot')
                live = persistent and k < len(wave['batches'])-1
                require(s[13] > s[12] if live else s[13] == s[12], 'heartbeat did not match live/held state')
                if persistent and k: require(s[15] > s[14], 'live reuse lacks heartbeat progress')
            else:
                require(s[0] == 0, 'startup failure not recorded')
                if a['wave']=='hold-diagnostic':
                    require(s[1] >= 480000 and s[9]==0x1e0005a, 'timeout/ROM-PC diagnostic differs')
                require(s[20] == 0 and s[11] == 0, 'timeout has an unexpected peer reply')
            if j['status']==2:
                completed.add(name)
                require(sum(r['batch']==name for r in records)==3, 'missing probe/calibration records')
            else: require(name not in batches, 'unfinished batch acquired instruction outputs')
        require_header = wave['header']
        if require_header[2] != len(wave['batches']): errors.append('incomplete handover')
    if batches != completed: errors.append('results contain unknown batches')
    for a in attempts.values():
        if a['status']=='failed handover' and a['ram_sha256'] is not None:
            errors.append('failed handover incorrectly has captured RAM')
        if a['fault_records'] and any(any(f) for f in a['fault_records']):
            errors.append(f"{a['wave']}: unexpected core fault record")
    return n, errors


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    n, errors=verify(p.parse_args().directory)
    for e in errors: print(e)
    print(f'{n} batch assertions and CPU1 protocol checked; {len(errors)} problems')
    return bool(errors)


if __name__=='__main__':
    raise SystemExit(main())
