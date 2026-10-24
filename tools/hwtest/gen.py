#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Generate hardware test batches: RAM images for tools/hwtest/runner.S with test cases from the table.

    python3 tools/hwtest/gen.py OUTDIR [--wave selftest|1|fpu|2|3|mem|stack|branch|misc|block|pair] [--per-entry 12]
                                 [--batch 60] [--seed 1] [--first-slot 0x01C28000]

Each case runs one instruction (its exact encoding, as raw bytes) with all sixteen registers, the low four psr
bits, sp and rets set from known inputs and a 1 KiB scratch area reset to a known pattern, and records all
registers, psr, sp, rets, which exit the stub took and the scratch words that changed. OUTDIR gets
batch-W-NNN.bin (the image, for one of the two RAM slots), batch-W-NNN.json (the manifest) and run-W.sh (the
M-Flasher commands). See README.md.
"""
import argparse
import json
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
from pi32v2isa import asm, codec, ld, table  # noqa: E402
from pi32v2isa.oracle import read_exec  # noqa: E402

APP_BASES = tuple(0x01C30000 + 0x8000 * k for k in range(9))  # --app: RAM the test application leaves alone
SLOTS = (0x01C20000, 0x01C28000)   # the flash loader's two 32 KiB slots (m-bootloader SPEC §1)
SLOT_SIZE = 0x8000
BASE = SLOTS[1]                     # where a single batch goes; consecutive batches alternate between the slots
SLOT_END = BASE + SLOT_SIZE
FORMAT = 2
CASE_WORDS = 20             # stub address, r0..r15, psr flags, sp, rets
OUT_WORDS = 53              # 16 pushed registers (stack order), psr, sp, exit, rets, changed count, 16 pairs
MAX_PAIRS = 16
SCRATCH_WORDS = 256         # hw_scratch, 1 KiB
SP_IN = 0x380               # each case's sp, as an offset into the scratch
STACK_TAKEN = range(SP_IN // 4, SP_IN // 4 + 17)   # pattern words above sp that hold hw_taken (popped pc)
DATA_BASES = (0x100, 0x200)  # address registers of a memory form: one region per bracket
EXIT_GOTO = 4                # `goto hw_exit0` to an external symbol is always the 4-byte long form

EDGES = [0x00000000, 0x00000001, 0x00000002, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, 0x0000007F, 0x00000080,
         0x000000FF, 0x00007FFF, 0x00008000, 0x0000FFFF, 0x0000001F, 0x00000020, 0x55555555, 0xAAAAAAAA,
         0x3F800000, 0xBF800000, 0x7F800000, 0x7FC00000, 0x00800000, 0x40490FDB, 0x40000000, 0xC0000000]

SAFE_GROUPS = {"arithmetic", "logic", "shifts", "multiply", "dsp", "fpu", "bitops", "constants", "moves"}
SAFE_KINDS = {"gpr", "gpr_lo", "gpr_hi", "pair", "pair_regs", "uimm", "simm", "bit", "invbit", "modimm", "enum"}
REG_KINDS = {"gpr", "gpr_lo", "gpr_hi", "pair", "pair_regs"}
# words and characters of the printed form that mean memory, the stack, control flow or special registers
# (a `[` only when it opens an address: `{t}[12:8]` is a bit range)
UNSAFE = re.compile(r"[{](?![a-z+]})|\[(?!\d)|\b(goto|call|rep|if|iff|ifs|sp|psr|pc|rets|reti|retx|rete|usp|ssp|uspn|"
                    r"sspn|icfg|icfgn|icfgs|cnum|sr\d+)\b")
BRACKET = re.compile(r"\[(?!\d)([^\]]*)\]")


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


# ---------------------------------------------------------------- forms that need memory, sp or an exit ---

def address_fields(i):
    """[(base field or None, [index register fields], [offset fields], uses sp, uses npc)] for each address."""
    out = []
    for m in BRACKET.finditer(i.syntax):
        inner = m.group(1)
        names = [t.group(2) for t in table.SYNTAX_TOKEN.finditer(inner) if t.group(2)]
        regs = [n for n in names if i.fields[n].kind in REG_KINDS]
        imms = [n for n in names if i.fields[n].kind not in REG_KINDS]
        sp, npc = bool(re.search(r"\bsp\b", inner)), bool(re.search(r"\bnpc\b", inner))
        base = None if (sp or npc) else (regs[0] if regs else None)
        out.append((base, [r for r in regs if r != base], imms, sp, npc))
    return out


def target_field(i):
    """The pc-relative offset field of a branch or call (`goto {n}`, `call {n}`), or None."""
    m = re.search(r"\b(goto|call)\s+\{\+?([a-z])\}", i.syntax)
    if m and i.fields[m.group(2)].kind == "simm":
        return m.group(2)
    return None


# forms that reset the FM-1 whatever their operands (hw/fm1-2026-10-24): the waves leave them out
RESETS = {f"{op}.mem2.hh.i.{s}" for op in ("mul", "madd", "msub") for s in ("u", "s")}


def kind_of(i):
    """Which special wave a form belongs to, or None if the runner cannot run it yet."""
    if i.status != "confirmed" or i.id.endswith(".p") or i.asm_no_syntax or i.body or i.block or i.id in RESETS:
        return None
    lit = literal(i.syntax)
    if i.group in ("memory", "multiply", "dsp", "cache") and BRACKET.search(i.syntax):
        for base, idx, imms, sp, npc in address_fields(i):
            if base is None and not (sp or npc):
                return None                      # an absolute address
        if any(f.kind in ("srmask",) for f in i.fields.values()):
            return None
        return "mem"
    if i.group == "stack":
        if i.id.startswith("pop.") and any(f.kind == "srmask" for f in i.fields.values()):
            return None                          # pops into special registers
        return "stack"
    if i.id in ("add.r_sp_i", "add.r_sp_i.l", "add.sp_i", "add.sp_i.l"):
        return "stack"
    if i.group == "branches":
        return "branch" if target_field(i) else None
    if i.id in ("goto.r", "call.r", "rts"):
        return "branch"
    if i.id in ("mov.r_sr", "push.rets", "csync") or i.id.startswith(("insert.rrriirii", "uextra.rrriirii",
                                                                       "sextra.rrriirii")):
        return "misc"
    return None


def solve(i, name, want):
    """A raw value for field `name` that stands for `want`, or None."""
    f, w = i.fields[name], len(i.field_bits(name))
    if f.kind in ("uimm", "simm") and f.zero_as is None:
        q, r = divmod(want - f.add, f.scale)
        raw = q & ((1 << w) - 1)
        return raw if r == 0 and codec.value(f, raw, w) == want else None
    for raw in range(1 << min(w, 16)):
        if codec.value(f, raw, w) == want:
            return raw
    return None


def small_raw(i, name, rng, limit, multiple=1):
    """A raw value of an offset field whose value is at most `limit` in magnitude (and a multiple of `multiple`)."""
    f, w = i.fields[name], len(i.field_bits(name))
    raws = [r for r in list(range(1 << min(w, 12))) + [(1 << w) - k for k in range(1, 1 << 11)] if 0 <= r < 1 << w
            and abs(codec.value(f, r, w)) <= limit and codec.value(f, r, w) % multiple == 0]
    return rng.choice(raws) if raws else 0


def regs_of(i, name, raw):
    """The register numbers a register field names."""
    f = i.fields[name]
    if f.kind in ("gpr", "gpr_lo"):
        return [raw]
    if f.kind == "gpr_hi":
        return [raw + 8]
    if f.kind == "pair":
        return [2 * raw, 2 * raw + 1]
    if f.kind == "pair_regs":
        return [2 * (raw >> 2) + (raw >> 1 & 1), 2 * (raw >> 2) + (raw & 1)]
    return []


def make_special_cases(tab, insns, per_entry, rng):
    """Cases for memory, stack, branch and misc forms: address registers point into the scratch, index registers
    and offsets are small, branches aim at the stub's own taken label, jumps and returns at hw_taken."""
    cases = []
    for i in insns:
        widths = {f: len(i.field_bits(f)) for f in i.fields}
        addrs = address_fields(i) if BRACKET.search(i.syntax) else []
        tgt = target_field(i)
        made = tries = 0
        while made < per_entry and tries < per_entry * 50:
            tries += 1
            values = {f: rng.randrange(1 << w) for f, w in widths.items()}
            regs = [rng.getrandbits(32) if rng.random() < 0.5 else rng.choice(EDGES) for _ in range(16)]
            fixed = {}                         # register -> value it must have
            small = set()
            ok = True
            for k, (base, idx, imms, sp, npc) in enumerate(addrs):
                for n in imms:
                    values[n] = small_raw(i, n, rng, 0x40 if sp else 0x80, 4 if npc else 1)
                if base:
                    for r in regs_of(i, base, values[base]):
                        fixed.setdefault(r, f"hw_scratch+{DATA_BASES[k % 2] + 4 * rng.randrange(-8, 9):#x}")
                for n in idx:
                    for r in regs_of(i, n, values[n]):
                        small.add(r)
            if small & set(fixed):
                ok = False                     # an index register that is also an address register
            if i.id in ("add.sp_i", "add.sp_i.l"):
                values["n"] = small_raw(i, "n", rng, 0x40)
            if tgt:
                raw = solve(i, tgt, EXIT_GOTO)
                if raw is None:
                    ok = False
                else:
                    values[tgt] = raw
            if not ok:
                continue
            for r in small:
                regs[r] = rng.choice([0, 4, 8, 12, 16, -4 & 0xFFFFFFFF, -8 & 0xFFFFFFFF])
            for r, v in fixed.items():
                regs[r] = v
            if i.id in ("goto.r", "call.r"):
                regs[values["x"]] = "hw_taken"
            if i.id.startswith(("insert.", "uextra.", "sextra.")) and "t" in values:
                regs[values["t"]] = rng.getrandbits(13) & 0x1F1F
            if i.group == "branches" and made % 3 == 0:
                # an equal pair or a register equal to the immediate, so that equality conditions are taken
                rf = [n for n in i.fields if i.fields[n].kind in ("gpr", "gpr_lo", "gpr_hi") and n != tgt]
                imm = [n for n in i.fields if i.fields[n].kind in ("uimm", "simm", "modimm") and n != tgt]
                if len(rf) >= 2:
                    regs[regs_of(i, rf[1], values[rf[1]])[0]] = regs[regs_of(i, rf[0], values[rf[0]])[0]]
                elif rf and imm:
                    op = codec.value(i.fields[imm[0]], values[imm[0]], widths[imm[0]]) \
                        if i.fields[imm[0]].kind != "modimm" else codec.modimm(values[imm[0]])
                    regs[regs_of(i, rf[0], values[rf[0]])[0]] = op & 0xFFFFFFFF
            cases.append({"id": i.id, "values": values, "bytes": codec.encode(i, values).hex(),
                          "text": codec.format(i, values), "in": regs, "flags": rng.randrange(16),
                          "taken": bool(tgt)})
            made += 1
    return cases


def enc(tab, id_, **values):
    """The bytes of one table form with the given raw field values."""
    return codec.encode(tab.by_id(id_), values)


def byte_line(b):
    return "\t.byte " + ", ".join(f"0x{x:02x}" for x in b)


def marker(tab, reg, value):
    """`reg = value` (li.s16, 4 bytes, any register): the body instruction that shows a part of a block ran."""
    return enc(tab, "li.s16", r=reg, n=value & 0xFFFF)


def low_regs(i, values, names, limit=8):
    """True if every register the named fields stand for is below r<limit>."""
    return all(r < limit for n in names for r in regs_of(i, n, values[n]))


def block_lines(tab, i, values, data=None):
    """An if-block stub: the opener, then-part markers r8.. = 0x100 + k, else-part markers r12.. = 0x200 + k."""
    nthen, nelse = values[i.block["then"]] + 1, values[i.block["else"]]
    lines = [byte_line(data or codec.encode(i, values))]
    lines += [byte_line(marker(tab, 8 + k, 0x100 + k)) for k in range(nthen)]
    lines += [byte_line(marker(tab, 12 + k, 0x200 + k)) for k in range(nelse)]
    return lines + ["\tgoto hw_exit0"]


def make_block_cases(tab, insns, per_entry, rng):
    """if/iff/ifs blocks: the then-part writes r8.. (0x100 + k), the else-part r12.. (0x200 + k), so the registers
    that changed show which part ran. rep / rep.i: a body of `r7 += 1`; r7 counts the iterations. tbb / tbh: a
    jump table of three entries, each landing on `r8 = k + 1; goto hw_exit1`."""
    cases = []
    for i in insns:
        widths = {f: len(i.field_bits(f)) for f in i.fields}
        made = tries = 0
        while made < per_entry and tries < per_entry * 100:
            tries += 1
            values = {f: rng.randrange(1 << w) for f, w in widths.items()}
            regs = [rng.getrandbits(32) if rng.random() < 0.5 else rng.choice(EDGES) for _ in range(16)]
            lines, extra = [], {}
            if i.block:
                tf, ef = i.block["then"], i.block["else"]
                cond = [n for n in i.fields if n not in (tf, ef) and i.fields[n].kind in REG_KINDS]
                if not low_regs(i, values, cond):
                    continue
                values[tf], values[ef] = rng.randrange(4), rng.randrange(4)
                nthen, nelse = values[tf] + 1, values[ef]
                if nelse > 3:
                    continue
                if made % 3 == 0:              # equal operands / register equal to the constant
                    rf = [n for n in cond if i.fields[n].kind in ("gpr", "gpr_lo", "gpr_hi")]
                    imm = [n for n in i.fields if n not in (tf, ef) and i.fields[n].kind in ("uimm", "simm", "modimm")]
                    if len(rf) >= 2:
                        regs[regs_of(i, rf[1], values[rf[1]])[0]] = regs[regs_of(i, rf[0], values[rf[0]])[0]]
                    elif rf and imm:
                        f = i.fields[imm[0]]
                        op = codec.modimm(values[imm[0]]) if f.kind == "modimm" else codec.value(f, values[imm[0]], widths[imm[0]])
                        regs[regs_of(i, rf[0], values[rf[0]])[0]] = op & 0xFFFFFFFF
                data = codec.encode(i, values)
                lines = block_lines(tab, i, values)
            elif i.id in ("rep", "rep.i"):
                body = rng.choice([1, 1, 2, 3])
                bf = i.body
                values[bf] = solve(i, bf, 2 * body)
                if i.id == "rep":
                    if values["r"] > 6:
                        continue
                    regs[values["r"]] = rng.choice([1, 2, 3, 5, 7])
                data = codec.encode(i, values)
                lines = [byte_line(data)] + [byte_line(enc(tab, "add.ri.u5", r=7, n=1))] * body + ["\tgoto hw_exit0"]
                regs[7] = rng.randrange(0x100)
            elif i.id in ("tbb", "tbh"):
                if values["x"] > 7:
                    continue
                k = rng.randrange(3)
                width = 1 if i.id == "tbb" else 2
                regs[values["x"]] = k * width
                data = codec.encode(i, values)
                tsize = 3 * width + (3 * width) % 2      # the table, padded to a halfword
                entries = [(tsize + 8 * n) // 2 for n in range(3)]
                table_bytes = b"".join(e.to_bytes(width, "little") for e in entries) + bytes((3 * width) % 2)
                lines = [byte_line(data), byte_line(table_bytes)]
                for n in range(3):
                    lines += [byte_line(marker(tab, 8, n + 1)), "\tgoto hw_exit1"]
                extra["taken_any"] = True
            else:
                continue
            cases.append({"id": i.id, "values": values, "bytes": data.hex(), "text": codec.format(i, values),
                          "in": regs, "flags": rng.randrange(16), "lines": lines, **extra})
            made += 1
    return cases


B_FORMS = ("st.w", "ld.w")        # the second instruction of a pair: a 16-bit store or load on r0..r7


def plain_model(i):
    """The register-only model of a twin's plain form (tools/hwtest/semantics), or None."""
    sys.path.insert(0, str(HERE))
    import check
    return check.load_models().get(i.id[:-2])


def make_pair_cases(tab, insns, per_entry, rng):
    """`A #` then B: A a .p twin, B `[rb+n] = rd` (stores A's destination: old or new value?) or `rd = [rb+n]`
    (loads into A's destination: which write wins?), with rb pointing into the scratch."""
    sys.path.insert(0, str(HERE))
    import check
    cases = []
    for i in insns:
        plain = tab.by_id(i.id[:-2])
        model = plain_model(i)
        if model is None:
            continue
        widths = {f: len(i.field_bits(f)) for f in i.fields}
        made = tries = 0
        while made < per_entry and tries < per_entry * 100:
            tries += 1
            values = {f: rng.randrange(1 << w) for f, w in widths.items()}
            regs = [rng.getrandbits(32) if rng.random() < 0.5 else rng.choice(EDGES) for _ in range(16)]
            try:
                writes, _ = model(list(regs), 0, check.operands(plain, values))
            except Exception:
                continue
            dest = sorted(writes)
            if not dest or dest[0] > 7:
                continue
            free = [r for r in range(8) if r not in writes]
            if not free:
                continue
            rb = rng.choice(free)
            rd = dest[0]
            bform = B_FORMS[made % 2]
            off = 4 * rng.randrange(-4, 8)
            b = enc(tab, bform, d=rd, b=rb, n=solve(tab.by_id(bform), "n", off))
            regs[rb] = f"hw_scratch+{DATA_BASES[0]:#x}"
            data = codec.encode(i, values)
            cases.append({"id": i.id, "values": values, "bytes": data.hex(), "text": codec.format(i, values),
                          "in": regs, "flags": rng.randrange(16), "lines": [byte_line(data), byte_line(b), "\tgoto hw_exit0"],
                          "pair_b": {"id": bform, "d": rd, "b": rb, "n": off}})
            made += 1
    return cases


def select(tab, wave):
    """selftest: the runner's own check; 1: integer and DSP forms; fpu: the floating-point forms (the FPU may need
    enabling first); 2: forms that may trap or be missing (division, instruction revision 3); 3: register-only
    forms objdump prints but the assembler cannot write (unnamed `??` conditions); mem, stack, branch, misc:
    forms that need memory, sp or an exit (kind_of); block: if/iff/ifs blocks, rep, rep.i, tbb, tbh; pair: the
    parallel twins (`A #` then a 16-bit load or store)."""
    if wave == "selftest":
        return [tab.by_id(x) for x in ("nop", "mov.rr", "add.rrr", "li.u8", "lsl.rri", "sub.rrr")]
    if wave == "3":
        return [i for i in tab.insns if runnable(i, no_syntax=True)]
    if wave in ("mem", "stack", "branch", "misc"):
        return [i for i in tab.insns if kind_of(i) == wave]
    if wave == "block":
        return [i for i in tab.insns if i.status == "confirmed" and not i.id.endswith(".p") and not i.asm_no_syntax
                and (i.block or i.id in ("rep", "rep.i", "tbb", "tbh"))]
    if wave == "pair":
        return [i for i in tab.insns if i.id.endswith(".p") and i.status == "confirmed"
                and any(b.id == i.id[:-2] for b in tab.insns) and runnable(tab.by_id(i.id[:-2]))]
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
    """Cases written by hand: a JSON list of {"id", "values" (raw field values), "in" (16 registers: numbers, or
    symbols such as "hw_scratch+0x100" and "hw_taken"), "flags"}, optionally "sp" and "rets" (same), "taken"
    (true for a branch aimed at the stub's own taken label), "misalign" (true: the stub starts 2 bytes past a word
    boundary instead of on one), "before" / "after" (lists of {"id", "values"}: instructions run before / after
    the one under test, e.g. to set or read a special register), "force" (true: run a form the generator would
    not, e.g. control forms, one case per batch), and "bytes" (hex) to run exactly those bytes, which
    must decode as the entry with those values. "model" selects a context model in check.py instead of the
    entry's ordinary single-instruction model; it has no effect on the image."""
    cases = []
    for c in json.loads(Path(path).read_text()):
        i = tab.by_id(c["id"])
        if not (runnable(i) or runnable(i, no_syntax=True) or kind_of(i) or i.block or c.get("force")):
            raise SystemExit(f"{i.id}: not a form the runner can execute (\"force\": true runs it anyway)")
        values = {f: c["values"][f] for f in i.fields}
        regs = [int(v, 0) if isinstance(v, str) and not v[0].isalpha() else v for v in c["in"]]
        if len(regs) != 16:
            raise SystemExit(f"{i.id}: 'in' needs 16 registers")
        data = codec.encode(i, values)
        if "bytes" in c:                # exact bytes, e.g. to set bits the entry ignores ('-')
            data = bytes.fromhex(c["bytes"].replace(" ", ""))
            got = codec.decode(tab, data)
            if not got or got[0].id != i.id or codec.fields_of(i, data) != values:
                raise SystemExit(f"{i.id}: bytes {data.hex()} do not decode as this entry with these values")
        case = {"id": i.id, "values": values, "bytes": data.hex(), "text": codec.format(i, values), "in": regs,
                "flags": c.get("flags", 0) & 0xF}
        for k in ("sp", "rets", "taken", "misalign", "force", "model"):
            if k in c:
                case[k] = c[k]
        if i.block:                     # the block's body: markers (block_lines)
            case["lines"] = block_lines(tab, i, values, data)
        if c.get("before") or c.get("after"):
            # set-up and read-back instructions around the one under test, each {"id", "values"}; the stub label
            # and "bytes" stay those of the instruction under test, so its address is the stub address
            def part(x):
                return byte_line(codec.encode(tab.by_id(x["id"]), x["values"]))
            case["pre_lines"] = [part(x) for x in c.get("before", [])]
            body = case.get("lines", [byte_line(data), "\tgoto hw_exit0"])
            case["lines"] = body[:-1] + [part(x) for x in c.get("after", [])] + body[-1:]
            case["before"], case["after"] = c.get("before", []), c.get("after", [])
        cases.append(case)
    return cases


def resolve(v, syms):
    """A number, or a symbol with an optional +/- offset, as a number."""
    if isinstance(v, int):
        return v & 0xFFFFFFFF
    m = re.fullmatch(r"([A-Za-z_]\w*)\s*(?:([+-])\s*(0x[0-9a-fA-F]+|\d+))?", v)
    if not m:
        raise SystemExit(f"cannot resolve {v!r}")
    off = int(m.group(3), 0) if m.group(3) else 0
    return (syms[m.group(1)] + (-off if m.group(2) == "-" else off)) & 0xFFFFFFFF


def asm_value(v):
    return f"{v & 0xFFFFFFFF:#010x}" if isinstance(v, int) else v


def build_batch(cases, workdir, flag_mask=0xF, base=BASE, pattern=None):
    """Assemble and link one batch with the repo's own assembler and linker; return (image, symbols)."""
    pattern = pattern or [0] * SCRATCH_WORDS
    lines = ["\t.text"]
    for n, c in enumerate(cases):
        b = bytes.fromhex(c["bytes"])
        # every stub starts on a word boundary, or 2 bytes past one with "misalign" (a nop fills the gap)
        lines += ["\t.p2align 2"]
        if c.get("pre_lines"):
            # Pad before entry, so setup falls straight through to the requested stub alignment.
            size = sum(line.count("0x") for line in c["pre_lines"])
            pad = ((2 if c.get("misalign") else 0) - size) % 4
            lines += ["\tnop"] * (pad // 2) + [f"hw_entry_{n}:"] + c["pre_lines"]
        elif c.get("misalign"):
            lines += ["\tnop"]
        if c.get("lines"):                    # a stub laid out by its generator (blocks, tables, pairs)
            lines += [f"hw_stub_{n}:"] + c["lines"]
        else:
            lines += [f"hw_stub_{n}:", "\t.byte " + ", ".join(f"0x{x:02x}" for x in b), "\tgoto hw_exit0"]
        if c.get("taken"):
            lines += [f"hw_tgt_{n}:", "\tgoto hw_exit1"]
    lines += ["\t.data", "\t.p2align 2", "\t.globl hw_ncases, hw_cases, hw_flagmask, hw_nwords, hw_pattern",
              f"hw_ncases:\t.4byte {len(cases)}", f"hw_flagmask:\t.4byte {flag_mask:#x}",
              f"hw_nwords:\t.4byte {SCRATCH_WORDS}", "hw_pattern:"]
    lines += [f"\t.4byte {asm_value(w)}" for w in pattern]
    lines.append("hw_cases:")
    for n, c in enumerate(cases):
        words = list(c["in"]) + [c["flags"], c.get("sp", f"hw_scratch+{SP_IN:#x}"), c.get("rets", "hw_taken")]
        entry = f"hw_entry_{n}" if c.get("pre_lines") else f"hw_stub_{n}"
        lines.append(f"\t.4byte {entry}, " + ", ".join(asm_value(w) for w in words))
    lines += ["\t.bss", "\t.p2align 2", "\t.globl hw_results, hw_scratch", f"hw_scratch:\t.space {SCRATCH_WORDS * 4}",
              f"hw_results:\t.space {len(cases) * OUT_WORDS * 4}", ""]
    workdir = Path(workdir)
    (workdir / "cases.s").write_text("\n".join(lines))
    (workdir / "runner.o").write_bytes(asm.assemble_source(
        subprocess.run(["cpp", "-P", str(HERE / "runner.S")], capture_output=True, text=True,
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
    status = ld.main(argparse.Namespace(argv=["-T", str(workdir / "hw.ld"), str(workdir / "runner.o"),
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
    for n, c in enumerate(cases):                     # every stub where the table says, every branch on target
        stub = syms[f"hw_stub_{n}"]
        if stub % 4 != (2 if c.get("misalign") else 0):
            raise SystemExit(f"case {n}: stub has the wrong alignment")
        b = bytes.fromhex(c["bytes"])
        if bytes(image[stub - base:stub - base + len(b)]) != b:
            raise SystemExit(f"case {n}: stub bytes not in the image")
        if c.get("taken") and syms[f"hw_tgt_{n}"] != stub + len(b) + EXIT_GOTO:
            raise SystemExit(f"case {n}: the taken label is not {EXIT_GOTO} bytes after the branch")
    return bytes(image), syms


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("outdir", type=Path)
    p.add_argument("--wave", default="1", choices=["selftest", "1", "fpu", "2", "3", "mem", "stack", "branch", "misc",
                                                         "block", "pair"])
    p.add_argument("--cases", type=Path, help="run these cases (JSON, see cases_from_file) instead of a wave; "
                                              "the batches are named after the file")
    p.add_argument("--flag-mask", type=lambda v: int(v, 0), default=0xF,
                   help="psr bits the cases set (default 0xF, the condition flags; 0 leaves psr as it is)")
    p.add_argument("--per-entry", type=int, default=12)
    p.add_argument("--batch", type=int, default=60)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--first-slot", type=lambda v: int(v, 0), default=SLOTS[1], choices=SLOTS,
                   help="the slot of the first batch (default 0x01C28000); when running waves one after another "
                        "without a power cycle, start each wave in the other slot from the previous wave's last batch")
    p.add_argument("--app", action="store_true",
                   help="batches for the test application (tools/hwtest/APP.md): each at its own RAM base, at most "
                        f"{len(APP_BASES)}, and app.S to build it with: fm1app.py OUT.fwsc app/driver.S OUTDIR/app.S")
    a = p.parse_args()
    tab = table.load()
    rng = random.Random(a.seed)
    if a.cases:
        cases = cases_from_file(tab, a.cases)
        if a.batch != 1 and any(c.get("force") for c in cases):
            raise SystemExit('"force": true requires --batch 1')
        insns = sorted({c["id"] for c in cases})
        a.wave = a.cases.stem
    else:
        insns = select(tab, a.wave)
        if a.wave in ("mem", "stack", "branch", "misc"):
            cases = make_special_cases(tab, insns, a.per_entry, rng)
        elif a.wave == "block":
            cases = make_block_cases(tab, insns, a.per_entry, rng)
        elif a.wave == "pair":
            cases = make_pair_cases(tab, insns, a.per_entry, rng)
        else:
            cases = make_cases(tab, insns, a.per_entry, rng)
    nop = tab.by_id("nop")
    a.outdir.mkdir(parents=True, exist_ok=True)
    run = ["#!/bin/sh", "# Run each batch on a unit in USB download mode; power-cycle it afterwards.", "set -e"]
    batches = [cases[k:k + a.batch] for k in range(0, len(cases), a.batch)]
    if a.app and len(batches) > len(APP_BASES):
        raise SystemExit(f"{len(batches)} batches; the application has room for {len(APP_BASES)}")
    app = ["/* gen.py --app: the batches for app/driver.S */", "\t.section .rodata", "\t.p2align 2",
           "\t.globl app_batches", f"app_batches:\t.4byte {len(batches)}"]
    blobs = []
    for n, part in enumerate(batches):
        calib = make_cases(tab, [nop], 2, rng)          # every batch starts with two nop calibration cases
        part = calib + part
        pattern = [rng.getrandbits(32) for _ in range(SCRATCH_WORDS)]
        for k in STACK_TAKEN:
            pattern[k] = "hw_taken"
        with tempfile.TemporaryDirectory() as d:
            # alternate slots: an upload never lands on the runner that is answering the ROM's commands
            base = APP_BASES[n] if a.app else SLOTS[(n + SLOTS.index(a.first_slot)) % 2]
            image, syms = build_batch(part, d, a.flag_mask, base, pattern)
        for k, c in enumerate(part):
            c["stub"] = syms[f"hw_stub_{k}"]
            if c.get("pre_lines"):
                c["entry"] = syms[f"hw_entry_{k}"]
            c["in_values"] = [resolve(v, syms) for v in c["in"]]
            c["sp_in"] = resolve(c.get("sp", f"hw_scratch+{SP_IN:#x}"), syms)
            c["rets_in"] = resolve(c.get("rets", "hw_taken"), syms)
            if c.get("taken"):
                c["tgt"] = syms[f"hw_tgt_{k}"]
        name = f"batch-{a.wave}-{n:03d}"
        image += bytes(-len(image) % 4)
        (a.outdir / f"{name}.bin").write_bytes(image)
        app.append(f"\t.4byte {name.replace('-', '_')}, {len(image)}, {base:#x}")
        blobs += ["\t.p2align 2", f"{name.replace('-', '_')}:", f'\t.incbin "{name}.bin"']
        length = len(part) * OUT_WORDS * 4
        (a.outdir / f"{name}.json").write_text(json.dumps({
            "format": FORMAT, "wave": a.wave, "seed": a.seed, "flag_mask": a.flag_mask, "base": base,
            "results": syms["hw_results"], "length": length, "out_words": OUT_WORDS,
            "scratch": syms["hw_scratch"], "hw_taken": syms["hw_taken"],
            "pattern": [resolve(w, syms) for w in pattern], "cases": part}, indent=0))
        run.append(f'm-flasher run-ram "{name}.bin" --addr {base:#x} --call FC60 '
                   f'--read {syms["hw_results"]:#x}:{length} -o "{name}.out"')
        print(f"{name}: {len(part)} cases, image {len(image)} bytes, results at {syms['hw_results']:#x}, {length} bytes")
    if a.app:
        (a.outdir / "app.S").write_text("\n".join(app + blobs) + "\n")
        print(f"application: python3 tools/hwtest/fm1app.py {a.outdir}/app.fwsc tools/hwtest/app/driver.S "
              f"{a.outdir}/app.S; results: analyze.py {a.outdir} --ram RAM.bin@0x01C30000")
        return
    (a.outdir / f"run-{a.wave}.sh").write_text("\n".join(run) + "\n")
    (a.outdir / f"run-{a.wave}.sh").chmod(0o755)
    print(f"{len(insns)} entries, {len(cases)} cases, {len(batches)} batches -> {a.outdir}; last batch in slot {base:#x}")


if __name__ == "__main__":
    main()
