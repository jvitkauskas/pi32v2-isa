# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""The assembler tables of the LLVM PI32V2 target (AsmParser/PI32V2ParserGen.inc), from this repo's assembler.

The LLVM parser reads a line the way pi32v2isa/asm.py does: the line in canonical form (asm.canon), matched
against one template per way of writing each form (asm.Matcher, aliases included) and enum value, the readings
that fit sorted as asm.py sorts them (size, alias, tie, table order). The tables are taken from asm.py's
matchers, so the two assemblers accept the same lines.

Template text: literal characters; 0x80 + k is slot k; 0x01 is a space that may be left out when the next
character is not a word character, 0x02 one that may be left out when the previous character is not (the
spaces around a number, asm.Matcher).

Relaxation: for each branch form, the next larger form that matches the same line, and how its operands come
from the smaller one's (asm.py grows a branch through the candidates of its line; LLVM relaxes the instruction).
"""
import re

from pi32v2isa import asm, codec

SLOT_KIND = {"gpr": 0, "gpr_lo": 1, "gpr_hi": 2, "pair": 3, "pair_regs": 4, "sr": 5, "rlist4": 6, "rmask": 7,
             "srmask": 8}
NUM_KIND = {"uimm": 0, "simm": 1, "bit": 2, "invbit": 3, "modimm": 4}
REG_KINDS = ("gpr", "gpr_lo", "gpr_hi", "pair", "sr")


def c_string(data):
    out = []
    for b in data:
        if 32 <= b < 127 and chr(b) not in '"\\?':
            out.append(chr(b))
        else:
            out.append(f"\\x{b:02x}\"\"")
    return '"' + "".join(out) + '"'


def chr_lit(c):
    return f"'{c}'" if c else "'\\0'"


class NumTypes:
    def __init__(self):
        self.keys = {}

    def get(self, insn, name, target):
        f = insn.fields[name]
        width = len(insn.field_bits(name))
        kind = 5 if target else NUM_KIND[f.kind]
        rng = tuple(f.asm_range) if f.asm_range else None
        abs32 = asm.abs32_field(insn) == name
        key = (kind, width, f.scale, f.add, f.zero_as, rng, f.invert, abs32)
        return self.keys.setdefault(key, len(self.keys))

    def cxx(self):
        rows = []
        for (kind, width, scale, add, zero_as, rng, invert, abs32), _ in sorted(self.keys.items(), key=lambda x: x[1]):
            lo, hi = rng if rng else (0, 0)
            rows.append(f"    {{{kind}, {width}, {scale}, {add}, {int(zero_as is not None)}, {zero_as or 0}, "
                        f"{int(rng is not None)}, {lo}LL, {hi}LL, {int(invert)}, {int(abs32)}}},")
        return "static const PI32V2NumType NumTypes[] = {\n" + "\n".join(rows) + "\n};\n"


def template_bytes(m, combo_text):
    """The template of matcher m with its enum placeholders replaced: (bytes, [(field, plus)] in slot order)."""
    text = m.template
    out, slots = bytearray(), []
    skip_space = False
    for pos, ch in enumerate(text):
        code = ord(ch)
        if ch == " " and skip_space:
            skip_space = False
            continue
        if asm.SENT <= code < asm.SENT + 0x100:
            name, plus = m.holders[code - asm.SENT]
            fld = m.insn.fields[name]
            if fld.kind == "enum":
                out += combo_text[name].encode()
                continue
            if fld.kind in asm.NUMERIC_KINDS:
                if pos and text[pos - 1] == " " and not plus:
                    out[-1] = 0x01
                if pos + 1 < len(text) and text[pos + 1] == " ":
                    skip_space = True
                    out.append(0x80 + len(slots))
                    slots.append((name, plus))
                    out.append(0x02)
                    continue
            out.append(0x80 + len(slots))
            slots.append((name, plus))
        else:
            out += ch.encode()
    return bytes(out), slots


def generate(tab, records, header):
    isa = asm.Isa(tab)
    by_insn = {}
    for name, (insn, fixed, fields) in records.items():
        by_insn.setdefault(insn.id, []).append((name, fixed, fields))
    nums = NumTypes()
    templates, slots_out, ops_out, rejects, fixed_out = [], [], [], [], []
    op_index = {}

    def ops_for(record):
        if record in op_index:
            return op_index[record]
        insn, fixed, fields = records[record]
        start = len(ops_out)
        for f in fields:
            fld = insn.fields[f]
            block = int(f in (insn.body, *insn.block.values()))
            if fld.kind in REG_KINDS:
                ops_out.append(f"    {{'{f}', 0, 0, 0}},")
            elif fld.kind in asm.NUMERIC_KINDS:
                ops_out.append(f"    {{'{f}', 1, {nums.get(insn, f, asm.branch_field(insn) == f)}, {block}}},")
            else:
                ops_out.append(f"    {{'{f}', 2, 0, 0}},")
        op_index[record] = (start, len(fields))
        return op_index[record]

    for m in isa.matchers:
        insn = m.insn
        tie = asm.TIE.get(insn.id.removesuffix(".p"), 0)
        size = 2 * len(insn.words)
        texts = []
        for record, fixed, fields in by_insn[insn.id]:
            combo_text = {n: asm.canon(insn.fields[n].values[v]) for n, v in fixed.items()}
            data, slots = template_bytes(m, combo_text)
            variants = [data]
            if insn.id.removesuffix(".p") not in asm.U_REQUIRED:
                for tail in (b"(u)", b"(u)#"):
                    if data.endswith(tail):
                        variants.append(data[:-len(tail)] + tail[3:])
            for v in variants:
                slot_start = len(slots_out)
                first = {}
                for k, (name, plus) in enumerate(slots):
                    fld = insn.fields[name]
                    back = first.setdefault(name, k)
                    numeric = fld.kind in asm.NUMERIC_KINDS
                    kind = 9 if numeric else SLOT_KIND[fld.kind]
                    numtype = nums.get(insn, name, asm.branch_field(insn) == name) if numeric else 0
                    width = len(insn.field_bits(name))
                    slots_out.append(f"    {{'{name}', {kind}, {int(plus)}, {int(name == m.negate)}, {numtype}, "
                                     f"{back if back != k else -1}, \"{fld.lead}\", {width}}},")
                rej_start = len(rejects)
                rejects.extend(sorted(m.rejects))
                op_start, nops = ops_for(record)
                # ("same", a, d): field a is field d (asm.Isa._operands)
                same = (m.alias[2], m.alias[1]) if m.alias and m.alias[0] == "same" else ("\\0", "\\0")
                fixed_start = len(fixed_out)
                fixed = m.alias[1] if m.alias and m.alias[0] == "fixed" else {}
                for field, raw in fixed.items():
                    value = int(codec.operand(insn.fields[field], raw, len(insn.field_bits(field))), 0)
                    fixed_out.append(f"    {{'{field}', {value}LL}},")
                templates.append(
                    f"    {{{c_string(v)}, PI32V2::{record}, {size}, {int(bool(m.negate))}, {tie}, {m.order}, "
                    f"{slot_start}, {len(slots)}, {op_start}, {nops}, {rej_start}, {len(m.rejects)}, "
                    f"'{same[0]}', '{same[1]}', {fixed_start}, {len(fixed)}, {int(bool(asm.branch_field(insn)))}, "
                    f"{int(bool(asm.abs32_field(insn)))}, {chr_lit(insn.body)}, {chr_lit(insn.block.get('then'))}, "
                    f"{chr_lit(insn.block.get('else'))}}},")
    relax = relaxations(tab, isa, records, by_insn, ops_for, nums)
    out = [f"// {header}",
           "#ifdef PI32V2_GEN_PARSER_TABLES", "#undef PI32V2_GEN_PARSER_TABLES",
           nums.cxx(),
           "static const PI32V2Slot Slots[] = {", *slots_out, "};",
           "static const PI32V2Op Ops[] = {", *ops_out, "};",
           "static const char *const Rejects[] = {", *([f"    {c_string(r.encode())}," for r in rejects] or ["    \"\","]),
           "};",
           "static const PI32V2Fixed FixedFields[] = {", *(fixed_out or ["    {0, 0},"]), "};",
           "static const PI32V2Template Templates[] = {", *templates, "};",
           "#endif"]
    relax_inc = f"// {header}\n#ifdef PI32V2_GEN_RELAX_TABLES\n#undef PI32V2_GEN_RELAX_TABLES\n{relax}#endif\n"
    return "\n".join(out) + "\n", relax_inc


def relaxations(tab, isa, records, by_insn, ops_for, nums):
    """For each branch record: the next larger record of the same line and how to build its operands."""
    rows, prog = [], []
    record_of = {}
    for record, (insn, fixed, fields) in records.items():
        record_of[(insn.id, tuple(sorted(fixed.items())))] = record
    done = set()
    for record, (insn, fixed, fields) in records.items():
        bf = asm.branch_field(insn)
        if not bf or not insn.examples or insn.asm_no_syntax:
            continue
        values = codec.fields_of(insn, insn.examples[0].bytes)
        values.update(fixed)
        syntax = (insn.asm_syntax or insn.syntax).replace("{" + bf + "}", "LBL_RELAX")
        line = asm.canon(codec.format(insn, values, syntax))
        cands = [c for c in isa.candidates(line) if asm.branch_field(c.insn) and plain_numbers(c)]
        cands.sort(key=lambda c: (c.size, c.alias, asm.TIE.get(c.insn.id.removesuffix('.p'), 0), c.order))
        rec = lambda c: record_of.get((c.insn.id, tuple(sorted(
            (n, v) for n, v in c.ops.items() if c.insn.fields[n].kind == "enum"))))
        names = [rec(c) for c in cands]
        if record not in names:
            continue
        i = names.index(record)
        nxt = next((k for k in range(i + 1, len(cands)) if cands[k].size > cands[i].size and names[k]), None)
        if nxt is None or record in done:
            continue
        done.add(record)
        a, b = cands[i], cands[nxt]
        span_a = spans(a, line)
        span_b = spans(b, line)
        a_fields = records[record][2]
        start = len(prog)
        for f in records[names[nxt]][2]:
            src = next((g for g, sp in span_a.items() if sp == span_b.get(f)), None)
            if src is not None and src in a_fields:
                prog.append(f"    {{0, {a_fields.index(src)}}},")
                continue
            fld = b.insn.fields[f]
            raw = b.ops.get(f)
            if fld.kind in ("gpr", "gpr_lo"):
                prog.append(f"    {{1, PI32V2::R{raw}}},")
            elif fld.kind == "gpr_hi":
                prog.append(f"    {{1, PI32V2::R{raw + 8}}},")
            elif fld.kind in asm.NUMERIC_KINDS and isinstance(raw, asm.Num):
                v = int(raw.node, 0)
                prog.append(f"    {{2, {-v if raw.neg else v}}},")
            elif fld.kind in asm.NUMERIC_KINDS and isinstance(raw, int):
                prog.append(f"    {{2, {codec.value(fld, raw, len(b.insn.field_bits(f)))}}},")
            elif isinstance(raw, int):
                prog.append(f"    {{2, {raw}}},")
            else:
                raise SystemExit(f"relaxation {record} -> {names[nxt]}: no source for field {f}")
        rows.append(f"    {{PI32V2::{record}, PI32V2::{names[nxt]}, {start}, {len(prog) - start}}},")
    return ("// kind 0: copy operand n of the smaller form; 1: register n; 2: immediate n\n"
            "static const PI32V2RelaxOp RelaxProg[] = {\n" + ("\n".join(prog) or "    {0, 0},") + "\n};\n"
            "static const PI32V2Relax Relaxations[] = {\n" + ("\n".join(rows) or "    {0, 0, 0, 0},") + "\n};\n")


def plain_numbers(cand):
    """True if every numeric operand of a candidate reads as a number or the branch label (asm.py rejects the
    other readings when it evaluates them)."""
    for op in cand.ops.values():
        if isinstance(op, asm.Num) and op.node != "LBL_RELAX":
            try:
                int(op.node, 0)
            except ValueError:
                return False
    return True


def spans(cand, line):
    """{field: (start, end)} of a candidate's operands in the line."""
    m = cand.matcher
    got = m.regex.match(line)
    if not got:
        return {}
    return {name: got.span(group) for name, group in m.groups.items() if got.group(group) is not None}
