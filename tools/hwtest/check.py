#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Compare hardware results with executable models of what the forms do.

    python3 tools/hwtest/check.py hw/fm1-2026-10-24/results.jsonl [--id ID]... [--show N] [--missing]

The models live in tools/hwtest/semantics/*.py. Each module has MODELS = {entry id: function}; a function
is called as f(R, flags, op) with
  R      the sixteen input registers (r0..r15, unsigned 32-bit),
  flags  the low four psr bits set before the instruction,
  op     the operands by field name: a register field gives its register number (gpr_hi already + 8, a pair
         its low register, pair_regs a (first, second) tuple), bit/invbit/modimm the 32-bit constant, enum its
         text, uimm/simm the number (scale, add and zero_as applied); op["raw"] has the raw field values,
and returns (writes, flags_out): {register number: value} for every register the form writes, and the low four
psr bits afterwards, or None for "not modelled". A case matches when the written registers have those values,
every other register is unchanged and (unless None) the flags agree.
"""
import argparse
import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from pi32v2isa import codec, table  # noqa: E402


def operands(insn, raw):
    op = {"raw": dict(raw)}
    for name, f in insn.fields.items():
        r, width = raw[name], len(insn.field_bits(name))
        if f.kind in ("gpr", "gpr_lo"):
            op[name] = r
        elif f.kind == "gpr_hi":
            op[name] = r + 8
        elif f.kind == "pair":
            op[name] = 2 * r
        elif f.kind == "pair_regs":
            op[name] = (2 * (r >> 2) + (r >> 1 & 1), 2 * (r >> 2) + (r & 1))
        elif f.kind == "bit":
            op[name] = 1 << r
        elif f.kind == "invbit":
            op[name] = 0xFFFFFFFF ^ (1 << r)
        elif f.kind == "modimm":
            op[name] = codec.modimm(r) ^ (0xFFFFFFFF if f.invert else 0)
        elif f.kind == "enum":
            op[name] = f.values[r]
        else:
            op[name] = codec.value(f, r, width)
    return op


def load_models():
    models = {}
    for p in sorted((HERE / "semantics").glob("*.py")):
        if p.name.startswith("_"):
            continue
        mod = importlib.import_module(f"semantics.{p.stem}")
        for k, fn in mod.MODELS.items():
            if k in models:
                raise SystemExit(f"{k} modelled twice ({p.name})")
            models[k] = fn
    return models


def check(records, tab, models, ids=None):
    """{id: {"cases": n, "ok": n, "bad": [(record, why), ...]}} for the modelled ids."""
    out = defaultdict(lambda: {"cases": 0, "ok": 0, "bad": []})
    for rec in records:
        i = rec["id"]
        if i not in models or (ids and i not in ids):
            continue
        insn = tab.by_id(i)
        writes, flags = models[i](list(rec["in"]), rec["flags_in"], operands(insn, rec["values"]))
        want = list(rec["in"])
        for r, v in writes.items():
            want[r] = v & 0xFFFFFFFF
        why = []
        diff = [r for r in range(16) if want[r] != rec["out"][r]]
        if diff:
            why.append("registers " + ", ".join(f"r{r}: got {rec['out'][r]:#010x}, model {want[r]:#010x}"
                                                for r in diff))
        if flags is not None and (rec["psr_out"] & 0xF) != (flags & 0xF):
            why.append(f"flags: got {rec['psr_out'] & 0xF:04b}, model {flags & 0xF:04b}")
        s = out[i]
        s["cases"] += 1
        if why:
            s["bad"].append((rec, "; ".join(why)))
        else:
            s["ok"] += 1
    return out


def main():
    sys.path.insert(0, str(HERE))
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("results", type=Path)
    p.add_argument("--id", action="append", help="only these entries")
    p.add_argument("--show", type=int, default=2, help="failing cases to show per entry")
    p.add_argument("--missing", action="store_true", help="list the tested entries that have no model")
    a = p.parse_args()
    tab = table.load()
    records = [json.loads(line) for line in a.results.read_text().splitlines() if line.strip()]
    models = load_models()
    res = check(records, tab, models, set(a.id) if a.id else None)
    good = 0
    for i in sorted(res):
        s = res[i]
        if not s["bad"]:
            good += 1
            continue
        print(f"{i}: {s['ok']}/{s['cases']} match")
        for rec, why in s["bad"][:a.show]:
            print(f"    {rec['text']}  in {[hex(v) for v in rec['in']]} flags {rec['flags_in']:04b}: {why}")
    tested = {r["id"] for r in records}
    print(f"{good}/{len(res)} modelled entries match on every case; "
          f"{len(tested - set(models))} of {len(tested)} tested entries have no model")
    if a.missing:
        print("no model:", " ".join(sorted(tested - set(models))))
    return 0 if good == len(res) else 1


if __name__ == "__main__":
    sys.exit(main())
