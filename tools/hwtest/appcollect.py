#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Extract only completed app experiments from retained RAM; failed cases never become instruction results.

appcollect.py DIR RAM.bin OUTDIR --run-id N
Appends JSONL/patterns and an observations record. RAM dumps and flash images stay outside the repository.
"""
import argparse
import json
import struct
import tempfile
from pathlib import Path
import analyze

BASE = 0x01C30000
RECORD = 0x01C7C000


def collect(directory, data, run_id, journal_words=48):
    header = list(struct.unpack_from('<12I', data, RECORD - BASE))
    if header[0] != 0x32504148 or header[8] != run_id:
        raise ValueError('retained header does not identify this experiment')
    manifests = sorted(directory.glob('batch-*.json'))
    observations, patterns = [], {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for n, p in enumerate(manifests):
            m = json.loads(p.read_text())
            journal = list(struct.unpack_from(f'<{journal_words}I', data, RECORD - BASE + 0x100 + n * 0x100))
            observations.append({'batch':p.stem, 'status':journal[0], 'handler_count':journal[1],
                                 'vector':journal[2], 'emu':journal[3], 'dbg':journal[4],
                                 'reti':journal[5], 'rete':journal[6], 'retx':journal[7],
                                 'rets':journal[8], 'psr':journal[9], 'icfg':journal[10],
                                 'sp':journal[11], 'regs':journal[12:28], 'samples':journal[28:],
                                 'manifest':m})
            if journal[0] != 2:
                continue
            offset = m['results'] - BASE
            if not 0 <= offset <= len(data) - m['length']:
                raise ValueError('result outside dump')
            (tmp/p.name).write_text(json.dumps(m))
            (tmp/p.with_suffix('.out').name).write_bytes(data[offset:offset+m['length']])
            patterns[p.stem] = m['pattern']
        records, problems, _ = analyze.analyse(tmp)
        if problems:
            raise ValueError('\n'.join(problems))
    return header, observations, patterns, records


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    p.add_argument('ram',type=Path)
    p.add_argument('outdir',type=Path)
    p.add_argument('--run-id',required=True,type=lambda x:int(x,0))
    p.add_argument('--journal-words',type=int,choices=(48,64),default=48,help='64 for app4 extended peer snapshots')
    a = p.parse_args()
    h, obs, pats, records = collect(a.directory,a.ram.read_bytes(),a.run_id,a.journal_words)
    a.outdir.mkdir(parents=True,exist_ok=True)
    observations = a.outdir/'observations.json'
    old = json.loads(observations.read_text()) if observations.exists() else []
    if any(o['run_id']==a.run_id for o in old):
        raise SystemExit('run already collected')
    old.append({'run_id':a.run_id,'header':h,'batches':obs})
    observations.write_text(json.dumps(old,indent=2)+'\n')
    patterns = a.outdir/'patterns.json'
    old = json.loads(patterns.read_text()) if patterns.exists() else {}
    old.update(pats)
    patterns.write_text(json.dumps(old,separators=(',',':'))+'\n')
    with (a.outdir/'results.jsonl').open('a') as f:
        f.write(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in records))
    print(f'run {a.run_id:#x}: starts {h[1]}, next batch {h[2]}, active {h[3]}; '
          f'{len(records)} result records; statuses {[o["status"] for o in obs]}')


if __name__=='__main__':
    main()
