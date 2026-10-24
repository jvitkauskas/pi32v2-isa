#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Read hardware test results: batch-NNN.out (from M-Flasher) with batch-NNN.json (from gen.py).

    python3 tools/hwtest/analyze.py OUTDIR [--json RESULTS.jsonl]

For every batch with an .out file: finds the order in which the runner's push stored the registers (from the
nop calibration cases, which must give back their inputs), then lists each case's inputs and outputs. Self-test
cases are checked against the results their text says they must have. Prints a summary; --json writes every
case, one JSON object per line (batch, entry id, encoding, text, field values, inputs, outputs, psr flags in
and out), for the records.
"""
import argparse
import json
import re
import struct
import sys
from pathlib import Path

M32 = 0xFFFFFFFF


def calibrate(cases, words):
    """The stack slot each register landed in, from the nop cases: slot -> register."""
    order = None
    for c, w in zip(cases, words):
        if c["id"] != "nop":
            continue
        m = {}
        for slot in range(16):
            regs = [r for r in range(16) if c["in"][r] == w[slot]]
            if len(regs) != 1:
                raise ValueError(f"nop case: stack slot {slot} holds {w[slot]:#010x}, which is no single input")
            m[slot] = regs[0]
        if sorted(m.values()) != list(range(16)):
            raise ValueError("nop case: the slots do not hold every register once")
        if order is not None and m != order:
            raise ValueError("the nop cases disagree on the register order")
        order = m
    if order is None:
        raise ValueError("no nop calibration case in the batch")
    return order


def expected(text, regs):
    """What a self-test case's text says it does, or None if the evaluator does not know the form."""
    def r(name):
        return regs[int(name[1:])]
    pats = [
        (r"^r(\d+) = (r\d+) \+ (r\d+)$", lambda d, a, b: (int(d), (r(a) + r(b)) & M32)),
        (r"^r(\d+) = (r\d+) - (r\d+)$", lambda d, a, b: (int(d), (r(a) - r(b)) & M32)),
        (r"^r(\d+) = (r\d+) << (\d+)$", lambda d, a, n: (int(d), (r(a) << int(n)) & M32 if int(n) < 32 else 0)),
        (r"^r(\d+) = (r\d+)$", lambda d, a: (int(d), r(a))),
        (r"^r(\d+) = (-?\d+)$", lambda d, n: (int(d), int(n) & M32)),
        (r"^nop$", lambda: None),
    ]
    for pat, f in pats:
        m = re.match(pat, text)
        if m:
            return f(*m.groups()) if m.groups() else ("nop",)
    return None


def read_batch(manifest_path):
    m = json.loads(Path(manifest_path).read_text())
    out = Path(manifest_path).with_suffix(".out")
    if not out.exists():
        return m, None
    data = out.read_bytes()
    n = m["out_words"]
    if len(data) != len(m["cases"]) * n * 4:
        raise ValueError(f"{out}: {len(data)} bytes, expected {len(m['cases']) * n * 4}")
    words = [struct.unpack_from(f"<{n}I", data, k * n * 4) for k in range(len(m["cases"]))]
    return m, words


def analyse(outdir):
    records, problems, summary = [], [], []
    for mp in sorted(Path(outdir).glob("batch-*.json")):
        m, words = read_batch(mp)
        if words is None:
            summary.append(f"{mp.stem}: no results yet")
            continue
        order = calibrate(m["cases"], words)
        checked = failed = 0
        for c, w in zip(m["cases"], words):
            out = [0] * 16
            for slot, reg in order.items():
                out[reg] = w[slot]
            rec = {"batch": mp.stem, "id": c["id"], "bytes": c["bytes"], "text": c["text"], "values": c["values"],
                   "in": c["in"], "flags_in": c["flags"],
                   "out": out, "psr_out": w[16], "changed": [r for r in range(16) if out[r] != c["in"][r]]}
            records.append(rec)
            if m["wave"] == "selftest":
                e = expected(c["text"], c["in"])
                if e is None:
                    continue
                checked += 1
                want = list(c["in"])
                if e != ("nop",):
                    want[e[0]] = e[1]
                if out != want:
                    failed += 1
                    problems.append(f"{mp.stem}: {c['text']}: registers {[r for r in range(16) if out[r] != want[r]]} "
                                    f"differ from what the text says")
        line = f"{mp.stem}: {len(m['cases'])} cases; stack order slot->reg {[order[s] for s in range(16)]}"
        if m["wave"] == "selftest":
            line += f"; self-test {checked - failed}/{checked} as expected"
        summary.append(line)
    return records, problems, summary


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("outdir", type=Path)
    p.add_argument("--json", type=Path)
    a = p.parse_args()
    records, problems, summary = analyse(a.outdir)
    print("\n".join(summary))
    for x in problems:
        print("PROBLEM", x)
    if a.json:
        a.json.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in records))
        print(f"{len(records)} cases written to {a.json}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
