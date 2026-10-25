#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Check an LLVM build with the PI32V2 target against the instruction table, through llvm-mc.

    python3 tools/llvm/check_mc.py LLVM_BIN_DIR [--show N]

1. disassembly: every example's bytes print as the example's text, and re-encode to the same bytes
   (llvm-mc --disassemble --show-encoding);
2. assembly: every example's text (in its assembler form) assembles to the bytes this repo's assembler gives
   (pi32v2isa.asm), which equal JieLi's for every confirmed entry.
Prints a summary and the first failures of each kind; exit status 1 if anything fails.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from pi32v2isa import asm, elf, table  # noqa: E402

MATTR = "-mattr=+instrev3,+fprev1"


def run(mc, args, text):
    p = subprocess.run([str(mc), "-triple=pi32v2", MATTR, *args], input=text, capture_output=True, text=True)
    return p.stdout, p.stderr


def disassembly(mc, tab):
    cases = [(i, x) for i in tab.insns for x in i.examples]
    text = "\n".join(" ".join(f"0x{b:02x}" for b in x.bytes) for _, x in cases) + "\n"
    out, err = run(mc, ["--disassemble", "--show-encoding"], text)
    lines = [ln for ln in out.splitlines() if ln.strip() and not ln.strip().startswith(".text")]
    bad = []
    if len(lines) != len(cases):
        # one line per example; find where they part
        bad.append(("count", f"{len(lines)} lines for {len(cases)} examples", err[:2000]))
    for (insn, x), ln in zip(cases, lines):
        m = re.match(r"\s*(.*?)\s*; encoding: \[(.*)\]\s*$", ln)
        if not m:
            bad.append((insn.id, x.text, ln.strip()))
            continue
        got_text = m.group(1).strip()
        got_bytes = bytes(int(b, 16) for b in m.group(2).split(","))
        if got_text != x.text.strip():
            bad.append((insn.id, x.text, f"printed {got_text!r}"))
        elif got_bytes != x.bytes:
            bad.append((insn.id, x.text, f"re-encoded {got_bytes.hex(' ')}, expected {x.bytes.hex(' ')}"))
    return len(cases), bad


def objects(mc, src, workdir):
    """(LLVM's object, this repo's object, LLVM's errors) for an assembly source."""
    f = Path(workdir) / "in.s"
    f.write_text(src)
    o = Path(workdir) / "llvm.o"
    p = subprocess.run([str(mc), "-triple=pi32v2", MATTR, "-filetype=obj", "-o", str(o), str(f)],
                       capture_output=True, text=True)
    mine = elf.read(asm.assemble_source(src, "in.s"))
    theirs = elf.read(o.read_bytes()) if o.exists() and o.stat().st_size else None
    return theirs, mine, p.stderr


def assembly(mc, tab):
    """Each example's text (in its assembler form), in its own section, assembled by llvm-mc and by
    pi32v2isa.asm: the same bytes."""
    import tempfile
    cases = []
    for insn in tab.insns:
        if insn.asm_no_syntax or insn.body or insn.block:
            continue
        for x in insn.examples:
            text = x.text.strip()
            if text in insn.asm_rejects or text in insn.asm_wrong:
                continue
            if text.endswith("#"):          # a parallel pair's first half: give it a second
                text += "\n\tr0 = [r0+0]"
            try:
                asm.assemble_source(f"\t{text}\n", "x.s")
            except Exception:
                continue                    # the repo's assembler refuses it alone (a parallel pair, ...)
            cases.append((insn, text))
    def source(skip):
        src, line_of = "", {}
        for n, (_, text) in enumerate(cases):
            if n in skip:
                continue
            src += f"\t.section .t{n},\"ax\",@progbits\n"
            for part in text.split("\n"):
                line_of[src.count("\n") + 1] = n
                src += f"\t{part.strip()}\n"
        return src, line_of

    errors = {}
    with tempfile.TemporaryDirectory() as d:
        for _ in range(2):      # llvm-mc writes no object if a line fails: leave those out the second time
            src, line_of = source(errors)
            theirs, mine, err = objects(mc, src, d)
            for m in re.finditer(r"in\.s:(\d+):\d+: error: (.*)", err):
                errors.setdefault(line_of.get(int(m.group(1))), m.group(2))
            if theirs is not None:
                break
    got = {s.name: bytes(s.data) for s in theirs.sections if s.name.startswith(".t")} if theirs else {}
    want = {s.name: bytes(s.data) for s in mine.sections if s.name.startswith(".t")}
    bad = []
    for n, (insn, text) in enumerate(cases):
        if n in errors:
            bad.append((insn.id, text, errors[n]))
        elif got.get(f".t{n}") != want.get(f".t{n}"):
            g, w = got.get(f".t{n}"), want.get(f".t{n}")
            bad.append((insn.id, text, f"llvm {g.hex(' ') if g is not None else None}, "
                                       f"pi32v2isa {w.hex(' ') if w is not None else None}"))
    if not theirs and not errors:
        bad.append(("all", "", err[:2000]))
    return len(cases), bad


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("bin", type=Path)
    p.add_argument("--show", type=int, default=10)
    p.add_argument("--only", choices=["disasm", "asm"])
    a = p.parse_args()
    mc = a.bin / "llvm-mc"
    tab = table.load()
    status = 0
    for name, fn in (("disasm", disassembly), ("asm", assembly)):
        if a.only and a.only != name:
            continue
        n, bad = fn(mc, tab)
        print(f"{name}: {n - len(bad)}/{n} examples agree")
        for b in bad[:a.show]:
            print("   ", *b)
        status |= bool(bad)
    return status


if __name__ == "__main__":
    sys.exit(main())
