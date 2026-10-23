# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Command line: python3 -m pi32v2isa check | disasm HEX... | stats"""

import argparse
import sys
from collections import Counter

from . import codec, table


def cmd_check(args):
    t = table.load(args.table)
    errors = table.check(t)
    for e in errors:
        print(e, file=sys.stderr)
    print(f"{len(t.insns)} entries, {len(errors)} problems")
    return 1 if errors else 0


def cmd_disasm(args):
    t = table.load(args.table)
    data = bytes(int(b, 16) for b in " ".join(args.hex).split())
    offset = 0
    while offset < len(data):
        got = codec.decode(t, data, offset)
        if got is None:
            n = min(2, len(data) - offset)
            text = ".short 0x" + data[offset:offset + n][::-1].hex()
        else:
            insn, values, n = got
            text = codec.format(insn, values)
        print(f"{args.base + offset:8x}:  {data[offset:offset + n].hex(' '):<18} {text}")
        offset += n
    return 0


def cmd_stats(args):
    t = table.load(args.table)
    by_status = Counter(i.status for i in t.insns)
    print(f"{len(t.insns)} entries: " + ", ".join(f"{by_status[s]} {s}" for s in table.STATUSES))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="pi32v2isa")
    p.add_argument("--table", default=table.TABLE, help="instruction table (default: isa/pi32v2.toml)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="validate the table").set_defaults(func=cmd_check)
    d = sub.add_parser("disasm", help="decode hex bytes")
    d.add_argument("hex", nargs="+", help="bytes in hex, e.g. 80 00 01 00")
    d.add_argument("--base", type=lambda s: int(s, 0), default=0, help="address of the first byte")
    d.set_defaults(func=cmd_disasm)
    sub.add_parser("stats", help="count entries by status").set_defaults(func=cmd_stats)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
