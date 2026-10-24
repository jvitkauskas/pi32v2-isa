#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Check timer-count and trap-journal assertions recorded beside app2 results.

appverify.py OUTDIR: expectations.json names completed batches and comparisons over captured registers.
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
        r=records[name]['out']
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
