# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0

import struct
import unittest

from pi32v2isa import asm, codec, elf, oracle, table

TABLE = table.load()


def build(source, **kw):
    """Assemble source text; return the parsed object."""
    return elf.read(asm.assemble_source(source, "t.s", tab=TABLE, **kw))


def text_of(source):
    obj = build("\t.text\n" + source)
    return bytes(next(s for s in obj.sections if s.name == ".text").data)


def section(obj, name):
    return next(s for s in obj.sections if s.name == name)


# Examples the assembler writes as another entry of the same length: JieLi's assembler picks the same one
# (checked line by line by the live comparison).
SAME_SIZE = {
    ("add.ri.u5", "add.rri"), ("and.nmodimm.rri.p", "and.modimm.rri.p"),     # as JieLi's assembler chooses
    ("add.modimm.rri", "add.s14.rri"), ("add.modimm.rri.p", "add.s14.rri.p"), ("add.rr", "add.rrr"),
    ("add.rr.p", "add.rrr.p"), ("and.nmodimm.rri", "and.modimm.rri"), ("li.modimm", "li.s16"),
    ("li.modimm.p", "li.s16.p"), ("pop.pc_rmask", "pop.srmask"), ("push.rets_rmask.c", "push.srmask.c"),
    ("rmw.add.s12", "rmw.add.modimm"), ("rmw.and.nmodimm", "rmw.and.modimm"),
} | {(f"{c}.ri.s12", f"{c}.ri.modimm") for c in
     ("if.eq", "if.ne", "if.ge", "if.gt", "if.le", "if.lt", "ifs.ge", "ifs.gt", "ifs.le", "ifs.lt")}


class RoundTrip(unittest.TestCase):
    def test_every_example_assembles_to_the_same_meaning(self):
        """Each confirmed entry's example text gives the example's bytes, or a form of the same meaning that is
        no longer (the assembler picks the shortest; the oracle test checks it picks as JieLi's does)."""
        n = 0
        for insn in TABLE.insns:
            for ex in insn.examples:
                text = ex.text
                if insn.asm_no_syntax:        # no syntax produces it: the assembler must refuse the text
                    with self.subTest(insn=insn.id, text=text), self.assertRaises(asm.AsmError):
                        text_of(text + ("\nnop\n}" if text.rstrip().endswith("{") else "") + "\n")
                    continue
                if text in insn.asm_rejects:
                    continue
                lines = [text]
                if insn.asm_syntax:       # how the assembler wants a block opener
                    lines = [codec.format(insn, codec.fields_of(insn, ex.bytes), insn.asm_syntax)]
                if insn.block:              # an if-block opener: a then and an else part of the example's sizes
                    vals = codec.fields_of(insn, ex.bytes)
                    size = {part: codec.value(insn.fields[f], vals[f], len(insn.field_bits(f)))
                            for part, f in insn.block.items()}
                    lines += ["nop"] * size.get("then", 1)
                    if size.get("else"):
                        lines += ["} else {"] + ["nop"] * size["else"]
                    lines += ["}"]
                elif text.rstrip().endswith("{"):
                    nops = {"n": 16, "b": 16}.get(insn.body, 1) if insn.body else 1
                    if insn.body:
                        body = codec.fields_of(insn, ex.bytes)[insn.body]
                        nops = codec.value(insn.fields[insn.body], body, len(insn.field_bits(insn.body))) // 2
                    lines += ["nop"] * nops + ["}"]
                if text.rstrip().endswith("#"):
                    lines.append("r1 = [r1+0]")
                with self.subTest(insn=insn.id, text=text):
                    got = text_of("\n".join(lines) + "\n")
                    dec = codec.decode(TABLE, got)
                    self.assertIsNotNone(dec)
                    mine = got[:dec[2]]
                    if mine != ex.bytes:
                        self.assertLessEqual(len(mine), len(ex.bytes))
                        if len(mine) == len(ex.bytes):
                            self.assertIn((insn.id, dec[0].id), SAME_SIZE)
                        self.assertTrue(oracle.same_meaning(codec.format(dec[0], dec[1]), text),
                                        f"{text!r} -> {codec.format(dec[0], dec[1])!r}")
                n += 1
        self.assertGreater(n, 4000)


class RegisterNamedSymbols(unittest.TestCase):
    def test_allowed_in_directives_not_as_operands(self):
        """A C function called `pc`: JieLi's assembler takes it in .size and data, refuses `call pc`."""
        build("\t.text\n\t.globl pc\n\t.type pc,@function\npc:\n\trts\n\t.size pc, .-pc\n"
              "\t.data\n\t.4byte pc\n")
        with self.assertRaises(asm.AsmError):
            build("\t.text\npc:\n\trts\n\tcall pc\n")


class Syntax(unittest.TestCase):
    def check(self, *lines):
        """All the lines assemble to the same bytes (as the first one)."""
        want = text_of(lines[0] + "\n")
        for ln in lines[1:]:
            self.assertEqual(text_of(ln + "\n"), want, ln)
        return want

    def test_constants_pick_the_shortest_form(self):
        self.assertEqual(text_of("r1 = 5\n").hex(" "), "41 25")                    # li.u8
        self.assertEqual(text_of("r1 = -1\n").hex(" "), "11 3f")                   # li.neg5
        self.assertEqual(text_of("r9 = 0\n").hex(" "), "c1 14")                    # li.zero_hi
        self.assertEqual(text_of("r1 = 1024\n").hex(" "), "41 e0 00 04")           # li.s16, not li.modimm
        self.assertEqual(text_of("r1 = 0x10000\n").hex(" "), "60 e0 80 1b")        # li.modimm
        self.assertEqual(text_of("r1 = 0x12345678\n").hex(" "), "c1 ff 78 56 34 12")   # li.u32
        self.assertEqual(text_of("r15 = 4294967295\n").hex(" "), "4f e0 ff ff")    # wraps to -1

    def test_spellings(self):
        self.check("r2 = [r1+4]", "r2 = [r1 + 4]", "r2 = [ r1 + 4 ]", "r2=[r1+4]", "r2 = [r1+0x4]")
        self.check("[r1+-4] = r2", "[r1 + -4] = r2", "[r1+ -4] = r2")
        self.check("r2 = b[r1+4] (u)", "r2 = b[r1+4]", "r2 = b[ r1 + 4 ](u)")
        self.check("r1 += r2", "r1 = r1 + r2")
        self.check("r1 |= r2", "r1 = r1 | r2", "r1 = r2 | r1")
        self.check("r1 <<= 3", "r1 = r1 << 3")
        self.check("r1 = r1 - 3", "r1 -= 3", "r1 += -3")
        self.check("r0 = r1 + r2  #\nr1 = [r1+0]", "r0 = r1 + r2 #\nr1 = [r1+0]", "r0 = r1 + r2#\nr1 = [r1+0]")
        self.check("sr7 = r1", "uspn = r1")
        self.check("r1 = 0x10", "r1 = 16", "r1 = 0b10000", "r1 = 020", "r1 = (4 << 2)", "r1 = 1+3*5", "r1 = 8*2")
        self.check("goto -2", "goto .")
        self.check("{r3-r0} = [sp++]", "{r0, r1, r2, r3} = [sp++]", "{ r3 - r0 } = [sp++]")

    def test_zero_offset_base_address(self):
        self.assertIsNotNone(codec.decode(TABLE, text_of("flushinv [r2]\n")))
        for lhs, rhs in (("[r0] = r2", "[r0+0] = r2"),
                         ("r3 = [r10]", "r3 = [r10+0]"),
                         ("b[r2] = r4", "b[r2+0] = r4"),
                         ("r1 = h[r4] (s)", "r1 = h[r4+0] (s)")):
            self.check(lhs, rhs)

    def test_subtraction_alias_does_not_wrap_to_small_addition(self):
        self.assertEqual(text_of("r3 = r0 - 0xFFFFFFFF\n").hex(" "), "f3 e0 ff 03")
        self.assertEqual(text_of("r3 = r0 - 0xFFFFFFFE\n").hex(" "), "03 e1 02 00")
        self.assertEqual(text_of("r3 = r0 - -3\n"), text_of("r3 = r0 + 3\n"))

    def test_expression_precedence_follows_llvm(self):
        """`*`, `/`, `%`, `<<`, `>>` bind tighter than `|`, `&`, `^`, which bind tighter than `+`, `-`."""
        self.assertEqual(text_of("r1 = 1+2*3\n"), text_of("r1 = 7\n"))
        self.assertEqual(text_of("r1 = 1+1|1\n"), text_of("r1 = 2\n"))
        self.assertEqual(text_of("r1 = 1<<2+1\n"), text_of("r1 = 5\n"))
        self.assertEqual(text_of("r1 = -7/2\n"), text_of("r1 = -3\n"))
        self.assertEqual(text_of("r1 = -5>>1\n"), text_of("r1 = -3\n"))       # 64-bit logical shift, then 32 bits

    def test_refused(self):
        for bad in ["r1 = r2 + ", "r16 = 1", "R1 = 1", "r1 = [r2-4]", "frobnicate r1", "nop #\n", "r1 = 1f",
                    "r0 += r7 #\nnop", "r1 = [sp+2]", "if (r1 == r2) {\n}"]:
            with self.subTest(bad=bad), self.assertRaises(asm.AsmError):
                text_of(bad + "\n")


class Branches(unittest.TestCase):
    def test_local_labels_resolve_without_relocations(self):
        obj = build("\t.text\nfoo:\n\tnop\n\tgoto foo\n\tgoto 1f\n\tnop\n1:\tcall foo\n")
        self.assertEqual(section(obj, ".text").relocs, [])
        data = bytes(section(obj, ".text").data)
        self.assertEqual(data[2:4], bytes.fromhex("f7 9e"))     # goto foo: -4 from the end of the instruction
        self.assertEqual(data[4:6], bytes.fromhex("04 81"))     # goto 1f: over the nop, +2

    def test_relaxation_grows_to_fit(self):
        near = text_of("goto L\nnop\nL: nop\n")
        far = text_of("goto L\n.space 3000\nL: nop\n")
        self.assertEqual(len(near), 6)
        self.assertEqual(len(far), 4 + 3000 + 2)                # goto.l
        self.assertEqual(far[:2].hex(), "c0ea")
        far2 = text_of("if (r1 == 0) goto L\n.space 400\nL: nop\n")
        self.assertEqual(len(far2), 4 + 400 + 2)                # beq.ri: 32-bit
        far3 = text_of("if (r1 == 0) goto L\n.space 5000\nL: nop\n")
        self.assertEqual(len(far3), 6 + 5000 + 2)               # beq.ri.l: 48-bit

    def test_numbers_are_displacements_from_the_end(self):
        self.assertEqual(text_of("goto 100\n").hex(" "), "14 92")
        self.assertEqual(text_of("goto 0\n").hex(" "), "04 80")
        self.assertEqual(text_of("goto -2\n").hex(" "), "f7 9f")

    def test_if_blocks_count_their_instructions(self):
        one = text_of("if (r4 == r3) {\nnop\n}\n")
        self.assertEqual(one[:4].hex(" "), "14 e8 00 03")
        two = text_of("if (r4 == r3) {\nnop\nnop\n}\n")
        self.assertEqual(two[2:4].hex(" "), "00 43")
        els = text_of("if (r4 == r3) {\nnop\n} else {\nr1 = 0x12345678\n}\n")
        self.assertEqual(els[2:4].hex(" "), "00 13")
        pair = text_of("if (r4 == r3) {\nr0 += r7 #\nr1 = [r1+0]\n}\n")
        self.assertEqual(pair[2:4].hex(" "), "00 03")            # a parallel pair counts once
        with self.assertRaises(asm.AsmError):
            text_of("if (r4 == r3) {\n" + "nop\n" * 5 + "}\n")
        with self.assertRaises(asm.AsmError):
            text_of("if (r4 == r3) {\nnop\n} else {\n" + "nop\n" * 4 + "}\n")

    def test_rep_body_length(self):
        dec = codec.decode(TABLE, text_of("rep 5 {\nnop\nr1 = 0x12345678\n}\n"))
        self.assertEqual((dec[0].id, dec[1]["b"], dec[1]["n"]), ("rep.i", 3, 4))       # 8 bytes in the body; count 5
        got = text_of("rep r1 {\nnop\nnop\n}\n")
        dec = codec.decode(TABLE, got)
        self.assertEqual(dec[0].id, "rep")
        self.assertEqual(codec.value(dec[0].fields["n"], dec[1]["n"], 4), 4)


class Relocations(unittest.TestCase):
    def relocs(self, source, name=".text"):
        return section(build(source), name).relocs

    def test_types(self):
        r = self.relocs("\t.text\n\tr1 = ext\n\tcall ext\n\tifeq goto ext\n\tif (r1 == 0) goto ext\n\tgotoss ext\n")
        self.assertEqual([(o, t, n, a) for o, t, n, a in r],
                         [(0, 5, "ext", 0), (6, 2, "ext", 0), (10, 1, "ext", 0), (14, 3, "ext", 0), (20, 4, "ext", 0)])
        d = self.relocs("\t.data\n\t.byte ext\n\t.short ext+3\n\t.long ext-4\n\t.long lab\nlab:\n", ".data")
        self.assertEqual(d, [(0, 6, "ext", 0), (1, 7, "ext", 3), (3, 8, "ext", -4), (7, 8, "lab", 0)])

    def test_unsigned_spelling_of_signed_relocation_addends(self):
        source = "r1 = (ext + 4294967295)\nr2 = (ext + 2147483648)\n"
        self.assertEqual(self.relocs(source), [(0, 5, "ext", -1), (6, 5, "ext", -2147483648)])
        self.assertEqual(asm.assemble_source(source, tab=TABLE),
                         asm.assemble_source("r1 = ext-1\nr2 = ext-2147483648\n", tab=TABLE))

    def test_addends_and_registers(self):
        r = self.relocs("\t.text\n\tr1 = ext+4\n\tr1 = 4+ext\n\tcall (ext-8)\n\treti = ext\n")
        self.assertEqual([(t, a) for _, t, _, a in r], [(5, 4), (5, 4), (2, -8), (5, 0)])

    def test_unresolved_choose_the_long_form(self):
        data = text_of("call ext\ngoto ext\nif (r1 == 0) goto ext\n")
        self.assertEqual(len(data), 4 + 4 + 6)

    def test_weak_and_other_sections_are_not_resolved(self):
        obj = build("\t.text\n\t.weak w\nw:\n\tcall w\n\t.section .b,\"ax\"\nb:\n\tcall w\n\tcall b\n")
        self.assertEqual([t for _, t, _, _ in section(obj, ".text").relocs], [2])
        self.assertEqual(section(obj, ".b").relocs[0][2:], ("w", 0))

    def test_label_in_another_section_uses_the_label_itself(self):
        obj = build("\t.text\n\tcall far\n\t.section .b,\"ax\"\nfar:\n\tnop\n")
        self.assertEqual(section(obj, ".text").relocs, [(0, 2, "far", 0)])
        self.assertIn("far", [s.name for s in obj.symbols])

    def test_got_variants(self):
        r = self.relocs("\t.text\n\tr1 = x@PI32V2GOT\n\tr1 = x@PI32V2GOTFUNCDESC\n\tr1 = x@PLT\n")
        self.assertEqual([t for _, t, _, _ in r], [9, 10, 5])


class Directives(unittest.TestCase):
    def data(self, source):
        obj = build("\t.data\n" + source)
        return bytes(section(obj, ".data").data)

    def test_data(self):
        self.assertEqual(self.data(".byte 1, -1, 255\n.short 1, -1\n.long 7\n.2byte 2\n.4byte 3\n.int 4\n.quad 5\n").hex(" "),
                         "01 ff ff 01 00 ff ff 07 00 00 00 02 00 03 00 00 00 04 00 00 00 05 00 00 00 00 00 00 00")
        self.assertEqual(self.data('.ascii "ab"\n.asciz "c"\n.string "d\\n\\101"\n'), b"abc\0d\nA\0")
        self.assertEqual(self.data(".space 2\n.space 2, 0x55\n.skip 1\n.zero 2, 9\n.fill 2, 2, 0x1234\n").hex(" "),
                         "00 00 55 55 00 09 09 34 12 34 12")
        self.assertEqual(self.data(".float 1.5\n.double 1.5\n").hex(" "), "00 00 c0 3f 00 00 00 00 00 00 f8 3f")
        self.assertEqual(self.data(".uleb128 300\n.sleb128 -129\n").hex(" "), "ac 02 ff 7e")

    def test_alignment_and_org(self):
        self.assertEqual(self.data(".byte 1\n.align 4\n.byte 2\n.balign 8, 0xaa\n.p2align 4\n.byte 3\n").hex(" "),
                         "01 00 00 00 02" + " aa" * 3 + " 00" * 8 + " 03")
        self.assertEqual(self.data(".byte 1\n.org 4, 0x77\n.byte 2\n").hex(" "), "01 77 77 77 02")
        with self.assertRaises(asm.AsmError):
            self.data(".byte 1, 2\n.org 1\n")
        obj = build("\t.text\n\t.p2align 3\n\tnop\n")
        self.assertEqual(section(obj, ".text").align, 8)

    def test_expressions_and_symbols(self):
        d = self.data("a:\n.byte 1\nb:\n.long b-a\n.long .-a\n.set K, 5\n.byte K+1\n")
        self.assertEqual(d.hex(" "), "01 01 00 00 00 05 00 00 00 06")
        self.assertEqual(self.data(".equ A, 3\n.byte A\n.set A, 4\n.byte A\n"), bytes([3, 4]))
        self.assertEqual(self.data(".byte later\n.equ later, 9\n"), bytes([9]))
        with self.assertRaises(asm.AsmError):
            self.data(".byte 256\n")
        with self.assertRaises(asm.AsmError):
            self.data(".long ext-ext2\n")

    def test_macros_and_conditionals(self):
        src = ("\t.macro PUT a, b=3\n\t.byte \\a, \\b\n\t.endm\n\tPUT 1\n\tPUT 4, 5\n\tPUT b=7, a=6\n"
               "\t.rept 2\n\t.byte 9\n\t.endr\n\t.irp v, 1, 2\n\t.byte \\v\n\t.endr\n"
               "\t.if 1 == 2\n\t.byte 100\n\t.elseif 2 == 2\n\t.byte 101\n\t.else\n\t.byte 102\n\t.endif\n"
               "\t.ifdef PUT\n\t.byte 103\n\t.endif\n")
        self.assertEqual(self.data(src), bytes([1, 3, 4, 5, 6, 7, 9, 9, 1, 2, 101, 103]))

    def test_comments_and_numeric_labels(self):
        src = "\t.text\n/* a\n b */ nop // c\n1: nop ; d\n# e\n\tgoto 1b\n"
        self.assertEqual(text_of(src.replace("\t.text\n", "")).hex(" "), "00 00 00 00 f7 9e")
        self.assertEqual(text_of("/* x */\n1: nop\n goto 1b\n")[2:], bytes.fromhex("f7 9e"))

    def test_sections(self):
        obj = build("\t.text\n\tnop\n\t.section .foo,\"aw\",@progbits\n\t.long 1\n\t.section .rodata.str1.1,\"aMS\",@progbits,1\n"
                    "\t.asciz \"x\"\n\t.section .bar\n\t.byte 1\n\t.bss\n\t.space 4\n\t.section .nb,\"aw\",@nobits\n\t.space 8\n")
        names = [s.name for s in obj.sections[1:] if s.type not in (elf.SHT_SYMTAB, elf.SHT_STRTAB)]
        self.assertEqual(names, [".text", ".foo", ".rodata.str1.1", ".bar", ".bss", ".nb"])
        flags = {s.name: (s.flags, s.type, s.entsize, s.align) for s in obj.sections}
        self.assertEqual(flags[".text"], (6, 1, 0, 2))
        self.assertEqual(flags[".foo"], (3, 1, 0, 1))
        self.assertEqual(flags[".rodata.str1.1"], (0x32, 1, 1, 1))
        self.assertEqual(flags[".bar"], (0, 1, 0, 1))          # no flags given, none assumed
        self.assertEqual(flags[".bss"], (3, 8, 0, 1))
        self.assertEqual(section(obj, ".nb").length, 8)
        with self.assertRaises(asm.AsmError):
            build("\t.bss\n\t.byte 1\n")

    def test_symbols(self):
        obj = build("""
\t.text
\t.globl g
\t.type g,@function
g:\tnop
\t.size g, .-g
\t.local l
l:\tnop
\t.weak w
\t.comm cm, 16, 4
\t.lcomm lc, 8
\t.set alias, g
\t.hidden g
""")
        syms = {s.name: s for s in obj.symbols}
        self.assertEqual((syms["g"].bind, syms["g"].type, syms["g"].size, syms["g"].other), (1, 2, 2, 2))
        self.assertEqual(syms["l"].bind, 0)
        self.assertEqual((syms["cm"].shndx, syms["cm"].value, syms["cm"].size), (elf.SHN_COMMON, 4, 16))
        self.assertEqual((syms["lc"].type, syms["lc"].size, syms["lc"].bind), (1, 8, 0))
        self.assertEqual(syms["alias"].type, 2)           # an alias has its base's type and size
        self.assertEqual(syms["alias"].size, 2)
        self.assertEqual((syms["w"].bind, syms["w"].shndx), (2, 0))      # declared weak: kept, undefined
        locals_ = [s.name for s in obj.symbols[1:] if s.bind == 0]
        globals_ = [s.name for s in obj.symbols[1:] if s.bind != 0]
        self.assertEqual(locals_, sorted(locals_))
        self.assertEqual(globals_, sorted(globals_))

    def test_unknown_directives(self):
        for bad in [".word 1", ".hword 1", ".cfi_startproc", ".bogus"]:
            with self.assertRaises(asm.AsmError):
                build("\t.text\n" + bad + "\n")


class ObjectFormat(unittest.TestCase):
    def test_layout(self):
        data = asm.assemble_source("\t.text\nfoo:\n\tcall ext\n\tgoto foo\n", "t.s", tab=TABLE)
        self.assertEqual(data[:4], b"\x7fELF")
        machine, flags = struct.unpack_from("<H", data, 18)[0], struct.unpack_from("<I", data, 36)[0]
        self.assertEqual((machine, flags), (0xF1, 0))
        self.assertEqual(struct.unpack_from("<H", data, 50)[0], 1)         # section names live in section 1
        obj = elf.read(data)
        self.assertEqual([s.name for s in obj.sections], ["", ".strtab", ".text", ".rela.text", ".symtab"])
        symtab = obj.sections[4]
        self.assertEqual((symtab.entsize, symtab.align), (16, 4))
        self.assertEqual(obj.sections[3].entsize, 12)

    def test_string_table_order(self):
        """Sorted by reversed spelling, largest first; a string ending another shares it."""
        st = elf.StringTable()
        for n in (".text", "fm1_cstart", "_start", ".strtab", ".symtab", ".rela.text.crt0", ".text.crt0"):
            st.add(n)
        data, where = st.layout()
        self.assertEqual(data, b"\0.text\0fm1_cstart\0_start\0.strtab\0.symtab\0.rela.text.crt0\0")
        self.assertEqual(data[where[".text.crt0"]:].split(b"\0")[0], b".text.crt0")

    def test_reader_round_trip(self):
        a = asm.assemble_source("\t.text\nx:\tnop\n\t.data\n\t.long x\n", "t.s", tab=TABLE)
        obj = elf.read(a)
        self.assertEqual(section(obj, ".data").relocs, [(0, 8, "x", 0)])


class Command(unittest.TestCase):
    def test_as_writes_an_object(self):
        import contextlib
        import io
        import tempfile
        from pathlib import Path

        from pi32v2isa import __main__ as cli

        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / "a.s", Path(d) / "a.o"
            src.write_text("\t.text\nstart:\n\tr1 = 5\n\tgoto start\n")
            self.assertEqual(cli.main(["as", str(src), "-o", str(out)]), 0)
            obj = elf.read(out.read_bytes())
            self.assertEqual(bytes(section(obj, ".text").data).hex(" "), "41 25 f7 9e")
            bad = Path(d) / "bad.s"
            bad.write_text("\tfrobnicate\n")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(cli.main(["as", str(bad), "-o", str(out)]), 1)
            self.assertIn("bad.s:1", err.getvalue())

    def test_cpp_for_capital_s(self):
        import tempfile
        from pathlib import Path

        from pi32v2isa import __main__ as cli

        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / "a.S", Path(d) / "a.o"
            src.write_text("#define N 7\n/* c */\n\t.text\n\tr1 = N\n#ifdef X\n\tnop\n#endif\n")
            self.assertEqual(cli.main(["as", str(src), "-o", str(out), "-DX"]), 0)
            self.assertEqual(bytes(section(elf.read(out.read_bytes()), ".text").data).hex(" "), "41 27 00 00")

    def test_features_gate_instructions(self):
        src = "\t.text\n\tr1 = popcnt(r2)\n"
        asm.assemble_source(src, "t.s", tab=TABLE)
        asm.assemble_source(src, "t.s", tab=TABLE, features={"instrev3"})
        with self.assertRaises(asm.AsmError):
            asm.assemble_source(src, "t.s", tab=TABLE, features={"fprev1"})


class Compat(unittest.TestCase):
    def test_late_equ_gets_the_wide_load_with_the_right_value(self):
        data = text_of("r1 = K\n.equ K, 0x12345\n")
        self.assertEqual(data.hex(" "), "c1 ff 45 23 01 00")       # JieLi's swaps the halves

    def test_known_jieli_bugs_are_not_reproduced(self):
        self.assertNotEqual(text_of("r0 = r0 | 0\n").hex(" "), "30 20")           # JieLi: r0 |= 1
        dec = codec.decode(TABLE, text_of("r0 = r0 | 0\n"))
        self.assertEqual(codec.format(dec[0], dec[1]), "r0 = r0 | 0x0")
        with self.assertRaises(asm.AsmError):
            text_of("call 0x1000000000\n")

    def test_missing_table_forms(self):
        """Forms JieLi's assembler writes that the table does not list yet."""
        self.assertEqual(text_of("if ((r1 & 3) == 0) goto 0\n").hex(" "), "60 ff 03 10 00 00")
        self.assertEqual(text_of("if (r1 == 2048) goto 0\n").hex(" "), "20 ff 00 1e 00 00")   # bit 5: modified immediate
        self.assertEqual(text_of("r1 = r1 | r13  #\nr1 = [r1+0]\n")[:4].hex(" "), "90 f1 10 1d")


def _toolchain():
    try:
        return oracle.Oracle()
    except oracle.OracleError:
        return None


EXAMPLE = """
\t.text
\t.globl entry
\t.type entry,@function
entry:
\tr1 = ext
\tr2 = 0x12345
\tr3 = [r1 + 4]
\tcall helper
\tif (r1 == 0) goto done
\tif (r1 != r2) goto entry
\tgoto 1f
\tnop
1:\tif (r3 == r2) {
\tnop
\t} else {
\tr1 = 0x10000
\t}
\trep r3 {
\tr1 += r2
\t}
\tr4 += r4 #
\tr1 = [r1+0]
\t{r3-r0} = [sp++]
done:\trts
\t.size entry, .-entry
helper:\tgoto helper
\t.data
\t.align 4
tbl:\t.long entry, ext+4, tbl
\t.short 1, 2
\t.asciz "hi"
\t.bss
\t.comm buf, 64, 4
"""


@unittest.skipUnless(_toolchain(), "JieLi toolchain not under oracle/ (python3 -m pi32v2isa oracle fetch)")
class Live(unittest.TestCase):
    def setUp(self):
        self.o = _toolchain()

    def test_asmcompare_small_example(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "example.s"
            p.write_text(EXAMPLE)
            self.assertEqual(oracle.asmcompare(self.o, p, table=TABLE), [])
            self.assertEqual(oracle.linkcompare(self.o, p, table=TABLE), [])

    def test_snippets(self):
        """tests/asm/*.s are assembled by JieLi's clang and by this assembler: same objects, except where a
        constant is defined after its use (JieLi's swaps the halves of the 32-bit load)."""
        from pathlib import Path

        known = {"fwdref.s": "contents differ first at +0x2", "expr.s": "contents differ first at +0x6"}
        files = sorted(Path(__file__).with_name("asm").glob("*.s"))
        self.assertGreater(len(files), 25)
        for f in files:
            with self.subTest(file=f.name):
                diffs = oracle.asmcompare(self.o, f, table=TABLE)
                if f.name in known:
                    self.assertEqual(len(diffs), 1, diffs)
                    self.assertIn(known[f.name], diffs[0])
                else:
                    self.assertEqual(diffs, [])

    def test_implicit_steps_and_vector_compare_aliases(self):
        # Exercise every generated fixed-operand alias at both register-bank
        # extremes. These are fresh oracle results, not table-derived evidence.
        cases = []
        for m in asm.Isa(TABLE).matchers:
            fixed = m.alias[1] if m.alias and m.alias[0] == "fixed" else None
            if fixed is None and not (m.insn.id.startswith("cmp.") and "cmpu(" in m.template):
                continue
            for high in (False, True):
                vals = {n: (1 << len(m.insn.field_bits(n))) - 1 if high else 0 for n in m.insn.fields}
                vals.update(fixed or {})
                text = m.template
                for k, (name, _) in enumerate(m.holders):
                    text = text.replace(chr(asm.SENT + k),
                                        codec.operand(m.insn.fields[name], vals[name], len(m.insn.field_bits(name))))
                if text.endswith("#"):
                    text += "\nr0 = [r0]"
                cases.append((m.insn.id, text))
        self.assertGreater(len(cases), 300)
        refs = self.o.encode([text for _, text in cases], ["fprev1", "instrev3"])
        for (ident, text), ref in zip(cases, refs):
            with self.subTest(id=ident, text=text):
                self.assertIsInstance(ref, bytes, ref)
                self.assertEqual(text_of(text + "\n")[:len(ref)], ref)

    def test_choices_agree_with_jielis_assembler(self):
        lines = ["r1 = 5", "r1 = 1024", "r1 = 0x10000", "r15 = -1", "r1 += r2", "r1 = r2 | r1", "r0 = r0 - 0", "r1 = r2 - 3",
                 "r1 -= 3", "r1 = r2 + 0x1FE", "{pc} = [sp++]", "r1 = r1 + 200", "if (r3 == 33280) goto -2", "r0 = r7 * r0",
                 "[--sp] = {rets, r8-r4}", "[--sp] = {rets, r15-r0}", "{pc, r15-r4} = [sp++]", "r5 = [sp+192]", "r0 = r1 << 32",
                 "r1.l = r2.h", "r1 = r2 + r3 (usat)", "r1 = r2 & 0xFFFFFF07"]
        want = self.o.encode(lines, ["fprev1", "instrev3"])
        for text, ref in zip(lines, want):
            if isinstance(ref, str):
                continue
            with self.subTest(text=text):
                got = text_of(text + "\n")
                self.assertEqual(got[:len(ref)], ref)


if __name__ == "__main__":
    unittest.main()


class ChipWarnings(unittest.TestCase):
    SRC = "\t.text\n\tr0 = popcnt(r1)\n\tr2 = r3 + r4\n"

    def test_warns_once_per_line(self):
        warnings = []
        asm.assemble_source(self.SRC, "x.s", features={"instrev3"}, chip="ac791n", warnings=warnings)
        self.assertEqual(warnings, ["x.s:2: popcnt.rr does nothing on the ac791n (isa/pi32v2.toml, hw)"])

    def test_errors_and_default(self):
        with self.assertRaises(asm.AsmError):
            asm.assemble_source(self.SRC, "x.s", features={"instrev3"}, chip="ac791n", chip_errors=True)
        warnings = []
        asm.assemble_source(self.SRC, "x.s", features={"instrev3"}, warnings=warnings)
        self.assertEqual(warnings, [])
