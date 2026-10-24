#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Generate hardware test batches: RAM images for tools/hwtest/runner.S with test cases from the table.

    python3 tools/hwtest/gen.py OUTDIR [--wave selftest|1|fpu|2|3] [--per-entry 12] [--batch 180] [--seed 1]
                                 [--first-slot 0x01C28000]

Each case runs one instruction (its exact encoding, as raw bytes) with all sixteen registers and the low four
psr bits set from known inputs, and records all registers and psr afterwards. OUTDIR gets batch-W-NNN.bin (the
image, for one of the two RAM slots), batch-W-NNN.json (the manifest) and run-W.sh (the M-Flasher commands). See README.md.
"""
import argparse
import json
import random
import re
import struct
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
from pi32v2isa import asm, codec, ld, table  # noqa: E402
from pi32v2isa.oracle import read_exec  # noqa: E402

SLOTS = (0x01C20000, 0x01C28000)   # the flash loader's two 32 KiB slots (m-bootloader SPEC §1)
SLOT_SIZE = 0x8000
BASE = SLOTS[1]                     # where a single batch goes; consecutive batches alternate between the slots
SLOT_END = BASE + SLOT_SIZE
CASE_WORDS = 18             # stub address, r0..r15, psr flags
OUT_WORDS = 17              # the 16 pushed registers (stack order), psr

EDGES = [0x00000000, 0x00000001, 0x00000002, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, 0x0000007F, 0x00000080,
         0x000000FF, 0x00007FFF, 0x00008000, 0x0000FFFF, 0x0000001F, 0x00000020, 0x55555555, 0xAAAAAAAA,
         0x3F800000, 0xBF800000, 0x7F800000, 0x7FC00000, 0x00800000, 0x40490FDB, 0x40000000, 0xC0000000]

SAFE_GROUPS = {"arithmetic", "logic", "shifts", "multiply", "dsp", "fpu", "bitops", "constants", "moves"}
SAFE_KINDS = {"gpr", "gpr_lo", "gpr_hi", "pair", "pair_regs", "uimm", "simm", "bit", "invbit", "modimm", "enum"}
# words and characters of the printed form that mean memory, the stack, control flow or special registers
UNSAFE = re.compile(r"[\[{]|\b(goto|call|rep|if|iff|ifs|sp|psr|pc|rets|reti|retx|rete|usp|ssp|uspn|sspn|icfg|icfgn|"
                    r"icfgs|cnum|sr\d+)\b")


def literal(syntax):
    """The fixed text of a syntax string: placeholders blanked, escaped braces kept."""
    return table.SYNTAX_TOKEN.sub(lambda m: m.group(0)[0] if m.group(0) in ("{{", "}}") else " ", syntax)


def risky(i):
    """Forms that might trap or that this chip might not have: run them after the safe ones."""
    return i.id.startswith("div.") or "instrev3" in i.requires or "instrev3" in i.decode_requires


def runnable(i, no_syntax=False):
    """Register-only forms the runner can execute blind: no memory, stack, sp, special registers or control flow.
    Forms JieLi's assembler cannot write (asm_no_syntax) only with no_syntax (wave 3)."""
    if i.status != "confirmed" or i.group not in SAFE_GROUPS or i.id.endswith(".p") or i.asm_no_syntax != no_syntax:
        return False
    if i.body or i.block or any(f.kind not in SAFE_KINDS for f in i.fields.values()):
        return False
    return not UNSAFE.search(literal(i.syntax))


def select(tab, wave):
    """selftest: the runner's own check; 1: integer and DSP forms; fpu: the floating-point forms (the FPU may need
    enabling first); 2: forms that may trap or be missing (division, instruction revision 3); 3: register-only
    forms objdump prints but the assembler cannot write (unnamed `??` conditions)."""
    if wave == "selftest":
        return [tab.by_id(x) for x in ("nop", "mov.rr", "add.rrr", "li.u8", "lsl.rri", "sub.rrr")]
    if wave == "3":
        return [i for i in tab.insns if runnable(i, no_syntax=True)]
    pool = [i for i in tab.insns if runnable(i)]
    if wave == "2":
        return [i for i in pool if risky(i)]
    fpu = [i for i in pool if not risky(i) and (i.group == "fpu" or "fprev1" in i.decode_requires)]
    return fpu if wave == "fpu" else [i for i in pool if not risky(i) and i not in fpu]


def make_cases(tab, insns, per_entry, rng):
    cases = []
    for i in insns:
        widths = {f: len(i.field_bits(f)) for f in i.fields}
        for k in range(per_entry):
            values = {f: (0 if k == 0 else (1 << w) - 1 if k == 1 else rng.randrange(1 << w)) for f, w in widths.items()}
            regs = [rng.getrandbits(32) for _ in range(16)]
            for r in range(16):             # mix in edge values, more of them in the early cases
                if rng.random() < (0.6 if k < per_entry // 2 else 0.25):
                    regs[r] = rng.choice(EDGES)
            if i.id == "nop":               # calibration: sixteen distinct values
                regs = [0xA5000000 | (r << 16) | rng.getrandbits(16) for r in range(16)]
            flags = rng.randrange(16)
            cases.append({"id": i.id, "values": values, "bytes": codec.encode(i, values).hex(),
                          "text": codec.format(i, values), "in": regs, "flags": flags})
    return cases


def cases_from_file(tab, path):
    """Cases written by hand: a JSON list of {"id", "values" (raw field values), "in" (16 registers), "flags"},
    optionally "bytes" (hex) to run exactly those bytes, which must decode as the entry with those values."""
    cases = []
    for c in json.loads(Path(path).read_text()):
        i = tab.by_id(c["id"])
        if not (runnable(i) or runnable(i, no_syntax=True)):
            raise SystemExit(f"{i.id}: not a form the runner can execute blind")
        values = {f: c["values"][f] for f in i.fields}
        regs = [int(v, 0) if isinstance(v, str) else v for v in c["in"]]
        if len(regs) != 16:
            raise SystemExit(f"{i.id}: 'in' needs 16 registers")
        data = codec.encode(i, values)
        if "bytes" in c:                # exact bytes, e.g. to set bits the entry ignores ('-')
            data = bytes.fromhex(c["bytes"].replace(" ", ""))
            got = codec.decode(tab, data)
            if not got or got[0].id != i.id or codec.fields_of(i, data) != values:
                raise SystemExit(f"{i.id}: bytes {data.hex()} do not decode as this entry with these values")
        cases.append({"id": i.id, "values": values, "bytes": data.hex(),
                      "text": codec.format(i, values), "in": regs, "flags": c.get("flags", 0) & 0xF})
    return cases


def build_batch(cases, workdir, flag_mask=0xF, base=BASE):
    """Assemble and link one batch with the repo's own assembler and linker; return (image, symbols)."""
    lines = ["\t.text"]
    for n, c in enumerate(cases):
        b = bytes.fromhex(c["bytes"])
        lines += [f"hw_stub_{n}:", "\t.byte " + ", ".join(f"0x{x:02x}" for x in b), "\tgoto hw_exit"]
    lines += ["\t.data", "\t.p2align 2", "\t.globl hw_ncases, hw_cases, hw_flagmask", f"hw_ncases:\t.4byte {len(cases)}",
              f"hw_flagmask:\t.4byte {flag_mask:#x}", "hw_cases:"]
    for n, c in enumerate(cases):
        words = c["in"] + [c["flags"]]
        lines.append(f"\t.4byte hw_stub_{n}, " + ", ".join(f"0x{w:08x}" for w in words))
    lines += ["\t.bss", "\t.p2align 2", "\t.globl hw_results", f"hw_results:\t.space {len(cases) * OUT_WORDS * 4}", ""]
    workdir = Path(workdir)
    (workdir / "cases.s").write_text("\n".join(lines))
    (workdir / "runner.o").write_bytes(asm.assemble_source(
        __import__("subprocess").run(["cpp", "-P", str(HERE / "runner.S")], capture_output=True, text=True,
                                     check=True).stdout, "runner.S"))
    (workdir / "cases.o").write_bytes(asm.assemble_source((workdir / "cases.s").read_text(), "cases.s"))
    (workdir / "hw.ld").write_text(f"""ENTRY(hw_entry)
MEMORY {{ ram (rwx) : ORIGIN = {base:#x}, LENGTH = {SLOT_SIZE:#x} }}
SECTIONS {{
  .entry : {{ KEEP(*(.entry)) }} > ram
  .text : {{ *(.text*) }} > ram
  .data : {{ *(.data*) *(.rodata*) }} > ram
  .bss : {{ *(.bss*) }} > ram
  hw_end = .;
}}
""")
    status = ld.main(__import__("argparse").Namespace(argv=["-T", str(workdir / "hw.ld"), str(workdir / "runner.o"),
                                                             str(workdir / "cases.o"), "-o", str(workdir / "hw.elf")]))
    if status:
        raise SystemExit(f"link failed ({status})")
    exe = read_exec((workdir / "hw.elf").read_bytes())
    image = bytearray()
    for s in exe["sections"]:
        if s["type"] == 1 and s["flags"] & 2 and s["addr"]:          # PROGBITS, SHF_ALLOC
            off = s["addr"] - base
            if off < 0:
                raise SystemExit(f"section {s['name']} below the slot")
            image[len(image):off] = bytes(max(0, off - len(image)))
            image[off:off + len(s["data"])] = s["data"]
    syms = {name: value for name, value, *_ in exe["symbols"] if name}
    if syms["hw_end"] > base + SLOT_SIZE:
        raise SystemExit(f"batch too big: ends at {syms['hw_end']:#x}, past {base + SLOT_SIZE:#x}")
    if syms["hw_entry"] != base:
        raise SystemExit(f"hw_entry at {syms['hw_entry']:#x}, not at the image start")
    return bytes(image), syms


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("outdir", type=Path)
    p.add_argument("--wave", default="1", choices=["selftest", "1", "fpu", "2", "3"])
    p.add_argument("--cases", type=Path, help="run these cases (JSON, see cases_from_file) instead of a wave; "
                                              "the batches are named after the file")
    p.add_argument("--flag-mask", type=lambda v: int(v, 0), default=0xF,
                   help="psr bits the cases set (default 0xF, the condition flags; 0 leaves psr as it is)")
    p.add_argument("--per-entry", type=int, default=12)
    p.add_argument("--batch", type=int, default=180)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--first-slot", type=lambda v: int(v, 0), default=SLOTS[1], choices=SLOTS,
                   help="the slot of the first batch (default 0x01C28000); when running waves one after another "
                        "without a power cycle, start each wave in the other slot from the previous wave's last batch")
    a = p.parse_args()
    tab = table.load()
    rng = random.Random(a.seed)
    if a.cases:
        cases = cases_from_file(tab, a.cases)
        insns = sorted({c["id"] for c in cases})
        a.wave = a.cases.stem
    else:
        insns = select(tab, a.wave)
        cases = make_cases(tab, insns, a.per_entry, rng)
    nop = tab.by_id("nop")
    a.outdir.mkdir(parents=True, exist_ok=True)
    run = ["#!/bin/sh", "# Run each batch on a unit in USB download mode; power-cycle it afterwards.", "set -e"]
    batches = [cases[k:k + a.batch] for k in range(0, len(cases), a.batch)]
    for n, part in enumerate(batches):
        calib = make_cases(tab, [nop], 2, rng)          # every batch starts with two nop calibration cases
        part = calib + part
        with tempfile.TemporaryDirectory() as d:
            # alternate slots: an upload never lands on the runner that is answering the ROM's commands
            base = SLOTS[(n + SLOTS.index(a.first_slot)) % 2]
            image, syms = build_batch(part, d, a.flag_mask, base)
        name = f"batch-{a.wave}-{n:03d}"
        (a.outdir / f"{name}.bin").write_bytes(image)
        length = len(part) * OUT_WORDS * 4
        (a.outdir / f"{name}.json").write_text(json.dumps({
            "wave": a.wave, "seed": a.seed, "flag_mask": a.flag_mask, "base": base, "results": syms["hw_results"], "length": length,
            "out_words": OUT_WORDS, "cases": part}, indent=0))
        run.append(f'm-flasher run-ram "{name}.bin" --addr {base:#x} --call FC60 '
                   f'--read {syms["hw_results"]:#x}:{length} -o "{name}.out"')
        print(f"{name}: {len(part)} cases, image {len(image)} bytes, results at {syms['hw_results']:#x}, {length} bytes")
    (a.outdir / f"run-{a.wave}.sh").write_text("\n".join(run) + "\n")
    (a.outdir / f"run-{a.wave}.sh").chmod(0o755)
    print(f"{len(insns)} entries, {len(cases)} cases, {len(batches)} batches -> {a.outdir}; last batch in slot {base:#x}")


if __name__ == "__main__":
    main()
