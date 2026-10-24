#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Check timer-count and trap-journal assertions recorded beside application results.

appverify.py OUTDIR: expectations.json names attempted batches and comparisons over captured registers.
This supplements numerical single-instruction models: counts depend on interrupt timing.
"""
import argparse
import json
from pathlib import Path


def verify(directory):
    records = {r['batch']:r for r in map(json.loads,(directory/'results.jsonl').read_text().splitlines())
               if r['id']!='nop'}
    journals = {b['batch']:b for w in json.loads((directory/'observations.json').read_text()) for b in w['batches']}
    errors=[]
    for wave in json.loads((directory/'observations.json').read_text()):
        h=wave['header']
        if h[3] or h[2]!=len(wave['batches']):errors.append(f"run {wave['run_id']}: handover before completion")
        if h[11]:errors.append(f"run {wave['run_id']}: P33 transaction timed out")
    expectations=json.loads((directory/'expectations.json').read_text())
    for name,e in expectations.items():
        j=journals[name]
        if j['status']!=e.get('status',2):errors.append(f'{name}: unexpected completion status')
        for k in ('vector','emu','handler_count'):
            if k in e and j[k]!=e[k]:errors.append(f'{name}: {k}: {j[k]} != {e[k]}')
        if 'min_handlers' in e and j['handler_count']<e['min_handlers']:errors.append(f'{name}: no interrupt delivered')
        if j['status']!=2:continue
        record=records[name]
        r=record['out']
        if 'same_as' in e:
            other=records[e['same_as']]
            fields=('bytes','values','in','flags_in','stub','sp_in','rets_in','before','after',
                    'out','psr_out','sp_out','rets_out','exit','mem','mem_count')
            if any(record.get(k)!=other.get(k) for k in fields):errors.append(f'{name}: repeated probe differs')
        for a,want in e.get('out_values',[]):
            if r[a]!=want:errors.append(f'{name}: r{a}: {r[a]} != {want}')
        for a,want in e.get('samples',[]):
            if j['samples'][a]!=want:errors.append(f'{name}: journal sample {a} differs')
        if 'trace' in e:
            n=j['samples'][3]
            if j['samples'][4:4+n]!=e['trace']:errors.append(f'{name}: entry/exit order differs')
        for start,end,lo,hi in e.get('delta',[]):
            diff=(r[end]-r[start])&0xffffffff
            if not lo<=diff<=hi:errors.append(f'{name}: counter delta {diff} outside [{lo},{hi}]')
        for a in e.get('preserved',[]):
            if r[a]!=record['in'][a]:errors.append(f'{name}: r{a} was not preserved')
        if 'flags' in e and record['psr_out']&15!=e['flags']:errors.append(f'{name}: flags differ')
        if e.get('unchanged_frame') and (record['sp_out']!=record['sp_in'] or record['rets_out']!=record['rets_in'] or record['exit'] or record['mem_count']):
            errors.append(f'{name}: stack/return/scratch/exit changed')
        for a,b in e.get('equal',[]):
            if r[a]!=r[b]:errors.append(f'{name}: r{a} != r{b}')
        for a,b in e.get('greater',[]):
            if r[a]<=r[b]:errors.append(f'{name}: r{a} did not advance above r{b}')
        for a,b in e.get('one_more',[]):
            if r[a]!=r[b]+1:errors.append(f'{name}: r{a} != r{b}+1')
        for a,mask in e.get('set',[]):
            if r[a]&mask!=mask:errors.append(f'{name}: r{a} lacks bits {mask:#x}')
        for a,mask in e.get('clear',[]):
            if r[a]&mask:errors.append(f'{name}: r{a} retains bits {mask:#x}')
    return len(expectations),errors


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    a=p.parse_args()
    n,errors=verify(a.directory)
    for e in errors:print(e)
    print(f'{n} application assertions checked; {len(errors)} problems')
    return bool(errors)


if __name__=='__main__':
    raise SystemExit(main())
