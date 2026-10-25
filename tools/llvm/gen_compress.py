# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Compression rules of the LLVM PI32V2 target (MCTargetDesc/PI32V2CompressGen.inc): which shorter form JieLi's
assembler would choose for a line the code generator writes in a long form.

The code generator selects the general forms (any register, the larger ranges); JieLi's assembler would assemble
their text into the smallest form that takes it. For each form the code generator uses, lines are sampled
(low and high registers, registers equal, small numbers) and read with pi32v2isa.asm's matchers; when a shorter
form is chosen, a rule is kept: the long form, the operands of the short one taken from the long one's, the
equalities the sample had, and the short form's own operand ranges (checked when the rule is used). Forms with a
`hw` entry for the AC791N are never a target.
"""
import itertools

from pi32v2isa import asm, codec

import codegen_flags
import gen_parser

REG_KINDS = ("gpr", "gpr_lo", "gpr_hi", "pair", "sr")
REG_SAMPLES = ([0, 1, 2, 3], [8, 9, 10, 11], [0, 9, 2, 11], [8, 1, 10, 3])
NUM_SAMPLES = (1, 4, 2, 0, 8, 16)


def key(c):
    return (c.size, c.alias, asm.TIE.get(c.insn.id.removesuffix(".p"), 0), c.order)


def generate(tab, records, ops, header):
    isa = asm.Isa(tab)
    record_of = {}
    for name, (insn, fixed, fields) in records.items():
        record_of[(insn.id, tuple(sorted(fixed.items())))] = name
    rules = {}           # (long record, short record, eq) -> program
    used = codegen_flags.ALU + codegen_flags.MOVES + codegen_flags.LOADS + codegen_flags.STORES
    for lid in used:
        L = tab.by_id(lid)
        lrec = record_of.get((lid, ()))
        if lrec is None:
            continue
        lfields = records[lrec][2]
        regs = [n for n in L.fields if L.fields[n].kind == "gpr"]
        nums = [n for n in L.fields if L.fields[n].kind in asm.NUMERIC_KINDS]
        for sample, num, eq in itertools.product(REG_SAMPLES, NUM_SAMPLES,
                                                 [None] + list(itertools.combinations(regs, 2))):
            vals = {}
            for k, n in enumerate(regs):
                vals[n] = sample[k % 4]
            if eq:
                vals[eq[1]] = vals[eq[0]]
            ok = True
            for n in nums:
                f = L.fields[n]
                raw = asm.numeric_raw(L, n, num * (4 if f.scale == 4 else 1))
                if raw is None:
                    ok = False
                    break
                vals[n] = raw
            if not ok:
                continue
            for n, f in L.fields.items():
                vals.setdefault(n, 0)
            line = asm.canon(codec.format(L, vals))
            cands = sorted([c for c in isa.candidates(line) if gen_parser.plain_numbers(c)], key=key)
            if not cands:
                continue
            best = cands[0]
            if best.size >= 2 * len(L.words) or best.insn.hw.get("ac791n"):
                continue
            srec = record_of.get((best.insn.id, tuple(sorted(
                (n, v) for n, v in best.ops.items() if best.insn.fields[n].kind == "enum"))))
            if srec is None:
                continue
            # the long form's operands: where each field's text is in the line
            lmatch = next((m for m in isa.matchers if m.insn is L and m.regex.match(line)), None)
            if lmatch is None:
                continue
            got = lmatch.regex.match(line)
            lspans = {n: got.span(g) for n, g in lmatch.groups.items() if got.group(g) is not None}
            sspans = gen_parser.spans(best, line)
            prog = []
            for f in records[srec][2]:
                src = next((g for g, sp in lspans.items() if sp == sspans.get(f)), None)
                if src is None:            # the same text at another place: a repeated field
                    text = line[slice(*sspans[f])] if f in sspans else None
                    src = next((g for g, sp in lspans.items() if text is not None and line[slice(*sp)] == text),
                               None)
                if src is None or src not in lfields:
                    prog = None
                    break
                prog.append(lfields.index(src))
            if prog is None:
                continue
            cond = tuple(sorted({(lfields.index(eq[0]), lfields.index(eq[1]))})) if eq else ()
            # a number of the long form that the short form does not carry must be the sample's
            fixed = tuple((k, codec.value(L.fields[f], vals[f], len(L.field_bits(f))))
                          for k, f in enumerate(lfields)
                          if L.fields[f].kind in asm.NUMERIC_KINDS and k not in prog)
            if any(L.fields[lfields[k]].kind not in ("uimm", "simm") for k, _ in fixed):
                continue
            rules.setdefault((lrec, srec, cond, fixed), (tuple(prog), key(best)))
    return emit(rules, records, ops, header)


def fit_expr(key):
    """C++ that is true when the int64_t V is a value of an immediate operand type (gen_td.Operands keys)."""
    kind = key[0]
    if kind in ("uimm", "simm"):
        _, width, scale, add, zero_as, _ = key
        return (f"fitsNum(V, {int(kind == 'simm')}, {width}, {scale}, {add}, {int(zero_as is not None)}, "
                f"{zero_as or 0})")
    if kind == "bit":
        return "(uint64_t(V) >> 32) == 0 && llvm::isPowerOf2_32(uint32_t(V))"
    if kind == "invbit":
        return "(uint64_t(V) >> 32) == 0 && llvm::isPowerOf2_32(~uint32_t(V))"
    if kind == "modimm":
        return f"PI32V2::modImmRawFor(uint32_t(V){' ^ 0xFFFFFFFFu' if key[1] else ''}).has_value()"
    return "true"


def emit(rules, records, ops, header):
    by_long = {}
    for (lrec, srec, cond, fixed), (prog, k) in rules.items():
        by_long.setdefault(lrec, []).append((k, srec, cond, fixed, prog))
    rows = []
    for lrec in sorted(by_long):
        for k, srec, cond, fixed, prog in sorted(by_long[lrec]):
            eq = cond[0] if cond else (-1, -1)
            fx = fixed[0] if fixed else (-1, 0)
            assert len(fixed) <= 1
            rows.append(f"    {{PI32V2::{lrec}, PI32V2::{srec}, {eq[0]}, {eq[1]}, {fx[0]}, {fx[1]}, {len(prog)}, "
                        f"{{{', '.join(map(str, prog))}}}}},")
    fits = ["static bool immFits(unsigned Opc, unsigned OpNo, int64_t V) {", "  switch (Opc) {"]
    for srec in sorted({srec for (_, srec, _, _) in rules}):
        insn, fixed, fields = records[srec]
        checks = []
        for k, f in enumerate(fields):
            if insn.fields[f].kind in REG_KINDS:
                continue
            op = ops.get(insn, f, False)
            if op.key and fit_expr(op.key) != "true":
                checks.append(f"    if (OpNo == {k})\n      return {fit_expr(op.key)};")
        if checks:
            fits += [f"  case PI32V2::{srec}:"] + checks + ["    return true;"]
    fits += ["  default:", "    return true;", "  }", "}"]
    return (f"// {header}\n#ifdef PI32V2_GEN_COMPRESS\n#undef PI32V2_GEN_COMPRESS\n"
            "// long form, short form, operands that must be equal (-1: none), an operand that must have a value\n"
            "// (-1: none) and the value, the short form's operands as\n"
            "// operands of the long one; for one long form the rules are in the order JieLi's assembler prefers\n"
            "static const PI32V2CompressRule CompressRules[] = {\n" + "\n".join(rows) + "\n};\n"
            + "\n".join(fits) + "\n#endif\n")
