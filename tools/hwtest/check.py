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

Results of record format 2 (hw/fm1-2026-10-24-v2: memory, stack, branches) also have sp, rets, the exit taken
and the scratch words that changed. A model with a fourth parameter is called f(R, flags, op, st), where st is a
State (sp, rets, stub, batch, end = the address after the instruction, tgt = the stub's taken label, taken = hw_taken,
scratch, and load(address, size) for the scratch as it was before the case), and returns a dict with any of
"regs" ({register: value}), "flags", "sp", "rets", "exit" (0 fell through, 1 taken) and "mem" ({word address:
value} for every scratch word it changes). Keys it leaves out must be unchanged (exit: 0); "flags": None means not
modelled. A word stored over the 16 words below the final sp (where the runner's exit pushes) is not seen.
"""
import argparse
import importlib
import inspect
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


class State:
    """What a format-2 case started with, for models of memory, stack and branch forms."""

    def __init__(self, rec, pattern):
        self.sp, self.rets, self.stub, self.tgt = rec["sp_in"], rec["rets_in"], rec["stub"], rec.get("tgt")
        self.end = rec["stub"] + len(rec["bytes"]) // 2
        self.taken, self.scratch = rec["hw_taken"], rec["scratch"]
        self.batch = rec["batch"]
        self.words = list(pattern)
        k = (self.sp - 4 - self.scratch) // 4
        if 0 <= k < len(self.words):
            self.words[k] = self.stub          # the runner enters the stub by popping its address from [sp - 4]

    def load(self, address, size=4):
        """Little-endian load of `size` bytes from the scratch (as it was before the case)."""
        off = address - self.scratch
        if not 0 <= off <= len(self.words) * 4 - size:
            raise ValueError(f"{address:#x} is outside the scratch")
        data = b"".join(w.to_bytes(4, "little") for w in self.words)
        return int.from_bytes(data[off:off + size], "little")


def takes_state(fn):
    """A model with four required parameters (R, flags, op, st) is a format-2 model."""
    return sum(p.default is p.empty for p in inspect.signature(fn).parameters.values()) >= 4


def patterns(results_path):
    """{batch: pattern}: patterns.json next to a results file (format 2), or the batch manifests there."""
    d = Path(results_path).parent
    if (d / "patterns.json").exists():
        out = json.loads((d / "patterns.json").read_text())
        for extra in sorted(d.glob("*.patterns.json")):      # follow-up runs keep their own
            out.update(json.loads(extra.read_text()))
        return out
    out = {}
    for mp in Path(results_path).parent.glob("batch-*.json"):
        m = json.loads(mp.read_text())
        if "pattern" in m:
            out[mp.stem] = m["pattern"]
    return out


def check(records, tab, models, ids=None, pats=None):
    """{id: {"cases": n, "ok": n, "bad": [(record, why), ...]}} for the modelled ids."""
    out = defaultdict(lambda: {"cases": 0, "ok": 0, "bad": []})
    for rec in records:
        i = rec["id"]
        if i not in models or (ids and i not in ids):
            continue
        insn = tab.by_id(i)
        fn = models[i]
        op = operands(insn, rec["values"])
        v2 = "exit" in rec
        if takes_state(fn):
            if not v2 or pats is None or rec["batch"] not in pats:
                continue
            res = fn(list(rec["in"]), rec["flags_in"], op, State(rec, pats[rec["batch"]]))
        else:
            writes, flags = fn(list(rec["in"]), rec["flags_in"], op)
            res = {"regs": writes, "flags": flags}
        want = list(rec["in"])
        for r, v in res.get("regs", {}).items():
            want[r] = v & 0xFFFFFFFF
        why = []
        diff = [r for r in range(16) if want[r] != rec["out"][r]]
        if diff:
            why.append("registers " + ", ".join(f"r{r}: got {rec['out'][r]:#010x}, model {want[r]:#010x}"
                                                for r in diff))
        flags = res.get("flags")
        if flags is not None and (rec["psr_out"] & 0xF) != (flags & 0xF):
            why.append(f"flags: got {rec['psr_out'] & 0xF:04b}, model {flags & 0xF:04b}")
        if v2:
            for key, rkey, default in (("sp", "sp_out", rec["sp_in"]), ("rets", "rets_out", rec["rets_in"]),
                                       ("exit", "exit", 0)):
                w = res.get(key, default) & 0xFFFFFFFF
                if rec[rkey] != w:
                    why.append(f"{key}: got {rec[rkey]:#x}, model {w:#x}")
            lo = rec["sp_out"] - 64
            mem = {int(a, 16): v & 0xFFFFFFFF for a, v in res.get("mem", {}).items()} \
                if any(isinstance(a, str) for a in res.get("mem", {})) else \
                {a: v & 0xFFFFFFFF for a, v in res.get("mem", {}).items()}
            mem = {a: v for a, v in mem.items() if not lo <= a < rec["sp_out"]}
            got = {int(a, 16): v for a, v in rec["mem"].items()}
            if rec["mem_count"] > len(got):
                # the record keeps only the first 16 changed words: those must agree and the count must be right
                if rec["mem_count"] != len(mem) or any(mem.get(a) != v for a, v in got.items()):
                    why.append(f"{rec['mem_count']} scratch words changed (only {len(got)} recorded), "
                               f"model changes {len(mem)}")
            elif got != mem:
                bad = sorted(set(got) | set(mem))
                why.append("scratch " + ", ".join(f"{a:#x}: got {got.get(a, 'unchanged') if a not in got else hex(got[a])}, "
                                                  f"model {hex(mem[a]) if a in mem else 'unchanged'}"
                                                  for a in bad if got.get(a) != mem.get(a)))
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
    res = check(records, tab, models, set(a.id) if a.id else None, patterns(a.results))
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
