#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Compare all firmware products and intermediate objects in two saved build trees."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

SUFFIXES = {'.o', '.elf', '.bin', '.fwsc', '.boot'}


def compare(stock, overlay):
    def files(root):
        return {str(p.relative_to(root)): p for p in root.rglob('*')
                if p.is_file() and p.suffix in SUFFIXES}
    left, right = files(stock), files(overlay)
    rows, counts = [], Counter()
    for name in sorted(left.keys() | right.keys()):
        a, b = left.get(name), right.get(name)
        before, after = a.read_bytes() if a else None, b.read_bytes() if b else None
        state = 'identical' if before == after else 'different' if a and b else 'stock-only' if a else 'overlay-only'
        counts[state] += 1
        row = {'path': name, 'state': state}
        for label, data in (('stock', before), ('overlay', after)):
            if data is not None:
                row[label] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        if a and b and before != after:
            row['first_difference'] = next((i for i, (x, y) in enumerate(zip(before, after)) if x != y), min(len(before), len(after)))
            row['unequal_bytes_at_same_offset'] = sum(x != y for x, y in zip(before, after)) + abs(len(before) - len(after))
        rows.append(row)
    return {'counts': dict(counts), 'files': rows}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stock', type=Path)
    p.add_argument('overlay', type=Path)
    p.add_argument('--json', action='store_true', help='full paths, sizes and SHA-256 values')
    args = p.parse_args()
    for root in (args.stock, args.overlay):
        if not root.is_dir():
            p.error(f'not a build directory: {root}')
    result = compare(args.stock, args.overlay)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for row in result['files']:
            sizes = ', '.join(f"{side} {row[side]['bytes']} B" for side in ('stock', 'overlay') if side in row)
            print(f"{row['state']:12} {row['path']} ({sizes})")
        print(', '.join(f'{value} {key}' for key, value in result['counts'].items()))
    return int(not result['files'] or any(r['state'] != 'identical' for r in result['files']))


if __name__ == '__main__':
    sys.exit(main())
