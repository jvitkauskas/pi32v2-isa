#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Compare two linked ELF files of one SDK application (a build with JieLi's toolchain and one with the drop-in):
the sections, and the functions and objects by name.

    compare_builds.py REF.elf OURS.elf [--names]

Names that differ only by the numeric suffix the compilers add to local symbols (head.1093) are taken as one;
.L_MergedGlobals.* are left out. --names lists the global symbols only one of the two has."""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jlwrap import Elf  # noqa: E402


def load(path):
    with open(path, "rb") as f:
        e = Elf(f.read())
    secs = {}
    for k, s in enumerate(e.sections):
        if s["name"] and s["addr"] or s["name"] in (".data", ".bss"):
            secs.setdefault(s["name"], 0)
            secs[s["name"]] += s["size"]
    syms = {}
    for s in e.symbols():
        if s["type"] in (1, 2) and s["size"] and 0 < s["shndx"] < 0xFF00:
            name = re.sub(r"\.[0-9]+$", "", s["name"])
            if name.startswith(".L_MergedGlobals"):
                continue
            syms.setdefault(name, []).append((s["size"], s["bind"] != 0, e.sections[s["shndx"]]["name"]))
    return secs, syms


def main(argv):
    names = "--names" in argv
    files = [a for a in argv if not a.startswith("--")]
    if len(files) != 2:
        print(__doc__)
        return 2
    (rs, rsym), (os_, osym) = load(files[0]), load(files[1])
    print("%-22s %10s %10s %9s %7s" % ("section", "reference", "ours", "delta", "%"))
    # the output sections of the linker script, in address order are the interesting ones; debug sections follow
    for n in sorted(set(rs) | set(os_), key=lambda n: (n.startswith(".debug"), n)):
        a, b = rs.get(n, 0), os_.get(n, 0)
        pct = "%+.1f" % (100.0 * (b - a) / a) if a else ""
        print("%-22s %10d %10d %+9d %7s" % (n, a, b, b - a, pct))
    both = sorted(set(rsym) & set(osym))
    only_r = sorted(set(rsym) - set(osym))
    only_o = sorted(set(osym) - set(rsym))
    print()
    print("functions and objects with a size: reference %d, ours %d, both %d" % (len(rsym), len(osym), len(both)))
    gr = {n for n, v in rsym.items() if any(x[1] for x in v)}
    go = {n for n, v in osym.items() if any(x[1] for x in v)}
    print("global: reference %d, ours %d, only reference %d, only ours %d" % (
        len(gr), len(go), len(gr - go), len(go - gr)))
    moved = [n for n in both if {x[2] for x in rsym[n]} != {x[2] for x in osym[n]}]
    print("in another section than the reference: %d%s" % (len(moved), (": " + " ".join(moved[:20])) if moved else ""))
    print("only in the reference (inlined or removed by ours): %d; only in ours: %d" % (len(only_r), len(only_o)))
    if names:
        print("global only in the reference:", " ".join(sorted(gr - go)))
        print("global only in ours:", " ".join(sorted(go - gr)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
