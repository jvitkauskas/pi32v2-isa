# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""The objdump replacement (docs/OBJDUMP.md): exact text on a built-in object and on hand-made ELF files, and,
when JieLi's toolchain is present, line-by-line agreement with its objdump."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from pi32v2isa import asm, elf, objdump, oracle, table

TABLE = table.load()

EXAMPLE = """\
\t.text
\t.globl f
\t.type f,@function
f:
\t[--sp] = {rets, r4}
\tr4 = r0
\tif (r4 == r1) {
\tr0 = 5
\t} else {
\tr0 = 7
\t}
\tr0 = 0x12345678
\tr1 = r2 + r3 #
\t[sp+4] = r1
\trep 3 {
\tnop
\t}
\tcall ext
\t{pc, r4} = [sp++]
\t.type tbl,@object
tbl:
\t.byte 1,2,3
\t.globl g
g:
\tgoto g
\t.data
\t.globl v
v:
\t.long 1
"""

DISASSEMBLY = (
    "\nex.o:\tfile format ELF32-pi32v2\n"
    "\nDisassembly of section .text:\n"
    "f:\n"
    "       0:    74 04             \t[--sp] = {rets, r4}\n"
    "       2:    04 16             \tr4 = r0\n"
    "       4:    14 e8 00 11       \tif (r4 == r1) {\n"
    "       8:    40 25             \t\tr0 = 5\n"
    "                               \t} else {\n"
    "       a:    40 27             \t\tr0 = 7\n"
    "                               \t}\n"
    "       c:    c0 ff 78 56 34 12 \tr0 = 305419896 <g+0x12345655 : 12345678 >\n"
    "      12:    a9 dc             \tr1 = r2 + r3  #\n"
    "      14:    81 21             \t\t [sp+4] = r1\n"
    "      16:    00 82             \trep 2 3 {\n"
    "      18:    00 00             \t\tnop\n"
    "                               \t}\n"
    "      1a:    80 ea 00 00       \tcall 0 <f+0x1E : 1e >\n"
    "      1e:    54 04             \t{pc, r4} = [sp++]\n"
    "\n"
    "\t\t\t0000001a:  R_PI32V2_LONG_JUMP_23M2\tUnknown\n"
    "\n"
    "tbl:\n"
    "      20:\t 01 02 03                        ...\n"
    "\n"
    "\n"
    "g:\n"
    "      23:    f7 9f             \tgoto -2 <tbl+0x2 : 22 >\n"
    "\n")

TABLES = (
    "Sections:\n"
    "Idx Name          Size      Address          Type\n"
    "  0               00000000 0000000000000000 \n"
    "  1 .strtab       0000002c 0000000000000000 \n"
    "  2 .text         00000025 0000000000000000 TEXT DATA \n"
    "  3 .rela.text    0000000c 0000000000000000 \n"
    "  4 .data         00000004 0000000000000000 DATA \n"
    "  5 .symtab       00000060 0000000000000000 \n"
    "SYMBOL TABLE:\n"
    "00000000         *UND*\t\t 00000000 \n"
    "00000020 l       .text\t\t 00000000 tbl\n"
    "00000000         *UND*\t\t 00000000 ext\n"
    "00000000 g     F .text\t\t 00000000 f\n"
    "00000023         .text\t\t 00000000 g\n"
    "00000000         .data\t\t 00000000 v\n")


def run(path, *options):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = objdump.main([*options, str(path)], tab=TABLE)
    return status, out.getvalue(), err.getvalue()


def make(d, name, sections, symbols):
    path = Path(d) / name
    path.write_bytes(elf.write(sections, symbols))
    return path


def text_section(data, **kw):
    return elf.Section(".text", elf.SHT_PROGBITS, elf.SHF_ALLOC | elf.SHF_EXECINSTR, 2, data=bytearray(data), **kw)


class BuiltIn(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "ex.o"
        self.path.write_bytes(asm.assemble_source(EXAMPLE, "ex.s", tab=TABLE))

    def output(self, *options):
        status, out, err = run(self.path, *options)
        self.assertEqual((status, err), (0, ""))
        return out.replace(str(self.path), "ex.o")

    def test_disassembly_with_relocations(self):
        self.assertEqual(self.output("-d", "-r"), DISASSEMBLY)

    def test_without_relocations_the_blank_lines_stay(self):
        self.assertEqual(self.output("-d"), DISASSEMBLY.replace("\t\t\t0000001a:  R_PI32V2_LONG_JUMP_23M2\tUnknown\n", ""))

    def test_section_and_symbol_tables(self):
        self.assertEqual(self.output("-h", "-t"), "\nex.o:\tfile format ELF32-pi32v2\n\n" + TABLES)

    def test_relocation_records_alone(self):
        self.assertEqual(self.output("-r"), "\nex.o:\tfile format ELF32-pi32v2\n\n"
                         "RELOCATION RECORDS FOR [.rela.text]:\n0000001a R_PI32V2_LONG_JUMP_23M2 Unknown\n\n")

    def test_j_picks_sections(self):
        out = self.output("-h", "-j", ".data")
        self.assertEqual(out.splitlines()[-2:], ["Idx Name          Size      Address          Type",
                                                   "  0 .data         00000004 0000000000000000 DATA "])
        self.assertEqual(self.output("-d", "-j", ".data"), "\nex.o:\tfile format ELF32-pi32v2\n\n")

    def test_D_prints_data_sections_as_text(self):
        out = self.output("-D")
        self.assertIn("Disassembly of section .data:\nv:\n       0:    01 00 00 00     \"\\x01\\0\\0\\0\"\n", out)
        self.assertIn("Disassembly of section .strtab:\n.strtab:\n", out)       # a section with no code or data

    def test_s_contents(self):
        out = self.output("-s")
        self.assertIn("Contents of section .data:\n 0000 01000000                             ....\n", out)

    def test_options_errors(self):
        self.assertEqual(run(self.path, "-print-imm-hex")[0], 1)
        self.assertEqual(run(self.path, "-d", "-mcpu=r1")[0], 1)
        self.assertEqual(run(Path(self.dir.name) / "none.o", "-d")[0], 1)
        with contextlib.redirect_stderr(io.StringIO()) as usage:
            self.assertEqual(objdump.main([], tab=TABLE), 1)
        self.assertIn("usage: objdump", usage.getvalue())


class HandMade(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def disassemble(self, data, symbols=(), *options):
        path = make(self.dir.name, "t.o", [text_section(data)], list(symbols))
        status, out, err = run(path, "-d", *options)
        self.assertEqual((status, err), (0, ""))
        return out.split("Disassembly of section .text:\n", 1)[-1]

    def test_cpu_options_enable_the_floating_point_forms(self):
        fadd = bytes.fromhex("3f e5 00 00")
        self.assertEqual(self.disassemble(fadd), ".text:\n       0:    3f e5              <unknown instruction>\n"
                         "       2:    00 00             \tnop\n\n")
        for option in ("-mcpu=r3", "-mcpu=r4", "-mattr=+fprev1"):
            self.assertEqual(self.disassemble(fadd, (), option), ".text:\n       0:    3f e5 00 00       \tr0 = r0 + r0 (f)\n\n")

    def test_unknown_instruction_lengths(self):
        """A word that is no instruction takes 2 bytes, or 1 when its instruction would not fit; with no whole
        word left the last length is used again, and the bytes shown come from the file."""
        self.assertEqual(self.disassemble(bytes.fromhex("ff ff 00")),
                         ".text:\n       0:    ff                 <unknown instruction>\n"
                         "       1:    ff 00             \tsti r15\n\n")
        self.assertEqual(self.disassemble(bytes.fromhex("00 e0 00 00 00")),
                         ".text:\n       0:    00 e0 00 00       \tr0.l = 0\n"
                         "       4:    00 00 00 00        <unknown instruction>\n\n")

    def test_branch_targets_use_the_symbols_of_the_section(self):
        out = self.disassemble(bytes.fromhex("04 81 80 00 00 00"),
                               [elf.Symbol("f", 0, 0, elf.STB_GLOBAL, elf.STT_FUNC, 0, ".text"),
                                elf.Symbol("g", 4, 0, elf.STB_GLOBAL, elf.STT_FUNC, 0, ".text")])
        self.assertEqual(out, "f:\n       0:    04 81             \tgoto 2 <g : 4 >\n       2:    80 00             \trts\n"
                         "\n\ng:\n       4:    00 00             \tnop\n\n")

    def test_jump_tables_and_data_symbols(self):
        data = bytes.fromhex("04 01") + bytes([3, 7, 11]) + bytes.fromhex("00 00") + bytes([1, 2, 0x41, 0x80])
        syms = [elf.Symbol(".GJTIS1", 2, 0, elf.STB_LOCAL, elf.STT_NOTYPE, 0, ".text"),
                elf.Symbol(".GJTIE1", 5, 0, elf.STB_LOCAL, elf.STT_NOTYPE, 0, ".text"),
                elf.Symbol("d", 7, 0, elf.STB_GLOBAL, elf.STT_OBJECT, 0, ".text")]
        self.assertEqual(self.disassemble(data, syms),
                         ".text:\n       0:    04 01             \ttbb [r4]\n"
                         "\n\n.GJTIS1:\n"
                         "       2:    03     < 3 : 0x3 >\n"
                         "       3:    07     < 7 : 0x7 >\n"
                         "       4:    0b     < 11 : 0xB >\n"
                         "       5:    00 00             \tnop\n"
                         "\n\nd:\n"
                         "       7:\t 01 02 41 80                     ..A.\n\n")

    def test_pairs_and_blocks(self):
        """The second of a pair has a space, an `if` block ends after the pair as one instruction."""
        code = bytes.fromhex("11 e8 00 42") + bytes.fromhex("88 dd 81 21") + bytes.fromhex("00 00 00 00")
        self.assertEqual(self.disassemble(code),
                         ".text:\n       0:    11 e8 00 42       \tif (r1 == r2) {\n"
                         "       4:    88 dd             \t\tr0 = r0 + r7  #\n"
                         "       6:    81 21             \t\t  [sp+4] = r1\n"
                         "       8:    00 00             \t\tnop\n"
                         "                               \t}\n"
                         "       a:    00 00             \tnop\n\n")

    def test_symbol_table_flags(self):
        syms = [elf.Symbol("w", 0, 0, elf.STB_WEAK, elf.STT_NOTYPE, 0, ".text"),
                elf.Symbol("h", 0, 4, elf.STB_GLOBAL, elf.STT_OBJECT, 2, ".text"),
                elf.Symbol("c", 4, 16, elf.STB_GLOBAL, elf.STT_OBJECT, 0, elf.SHN_COMMON),
                elf.Symbol("u", 8, 4, elf.STB_GLOBAL, elf.STT_FUNC, 0, elf.SHN_UNDEF)]
        path = make(self.dir.name, "s.o", [text_section(bytes(4))], syms)
        status, out, _ = run(path, "-t")
        self.assertEqual(out.split("SYMBOL TABLE:\n")[1],
                         "00000000         *UND*\t\t 00000000 \n"
                         "00000000  w      .text\t\t 00000000 w\n"
                         "00000000 g       .text\t\t 00000004 .hidden h\n"
                         "00000010 g       *COM*\t\t 00000004 c\n"
                         "00000000 g     F *UND*\t\t 00000004 u\n")

    def test_h_describes_sections(self):
        secs = [text_section(bytes(2)),
                elf.Section(".data", elf.SHT_PROGBITS, elf.SHF_ALLOC | elf.SHF_WRITE, 4, data=bytearray(4)),
                elf.Section(".bss", elf.SHT_NOBITS, elf.SHF_ALLOC | elf.SHF_WRITE, 4, size=8),
                elf.Section(".x", elf.SHT_PROGBITS, elf.SHF_EXECINSTR, 1, data=bytearray(1))]
        path = make(self.dir.name, "h.o", secs, [])
        rows = run(path, "-h")[1].split("Type\n")[1].splitlines()
        self.assertEqual([r.split(None, 4)[-1].strip() if len(r.split()) > 4 else "" for r in rows],
                         ["", "", "TEXT DATA", "DATA", "BSS", "TEXT", ""])


def _toolchain():
    try:
        return oracle.Oracle()
    except oracle.OracleError:
        return None


@unittest.skipUnless(_toolchain(), "JieLi toolchain not under oracle/ (python3 -m pi32v2isa oracle fetch)")
class Live(unittest.TestCase):
    """Against JieLi's objdump, line by line (oracle objdumpcompare)."""

    def setUp(self):
        self.o = _toolchain()
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def compare(self, path, sets):
        for options in sets:
            with self.subTest(file=Path(path).name, options=" ".join(options)):
                self.assertEqual(oracle.objdumpcompare(self.o, path, options, TABLE), [])

    def test_built_in_object(self):
        path = Path(self.dir.name) / "ex.o"
        path.write_bytes(asm.assemble_source(EXAMPLE, "ex.s", tab=TABLE))
        self.compare(path, [["-d"], ["-d", "-mcpu=r3"], ["-d", "-r"], ["-D"], ["-h"], ["-t"], ["-r"], ["-s"],
                            ["-d", "-j", ".text"], ["-h", "-j", ".data", "-j", ".text"]])

    def test_compiled_code_and_a_linked_executable(self):
        corpus = Path(__file__).with_name("corpus")
        objects = []
        for name in ("e_sw.c", "e_br2.c", "e_fp.c"):
            obj = Path(self.dir.name) / (Path(name).stem + ".o")
            code, _, err = self.o._run([self.o.clang, "-target", "pi32v2", "-mcpu=r3", "-O2", "-c", corpus / name, "-o", obj])
            self.assertEqual(code, 0, err)
            objects.append(obj)
        for obj in objects:
            self.compare(obj, [["-d"], ["-d", "-mcpu=r3", "-r"], ["-D"], ["-h"], ["-t"], ["-r"], ["-s"]])
        exe = Path(self.dir.name) / "linked.elf"
        exe.write_bytes(oracle.link_objects(self.o, [objects[1].read_bytes()]))
        self.compare(exe, [["-d", "-mcpu=r3"], ["-D"], ["-h"], ["-t"], ["-s"], ["-d", "-j", ".text"]])

    def test_garbage_and_blocks_of_a_random_object(self):
        """Random instruction words (table entries with random fields, some bytes of noise) read the same."""
        import random
        from pi32v2isa import codec
        rng = random.Random(7)
        for k in range(6):
            code = bytearray()
            for _ in range(60):
                insn = rng.choice(TABLE.insns)
                code += codec.encode(insn, {l: rng.randrange(min(4, 1 << len(insn.field_bits(l)))) for l in insn.fields})
                if rng.random() < 0.05:
                    code += bytes(rng.randrange(256) for _ in range(rng.choice([1, 2, 3])))
            path = make(self.dir.name, f"rnd{k}.o", [text_section(code)],
                        [elf.Symbol("f", 0, 0, elf.STB_GLOBAL, elf.STT_FUNC, 0, ".text")])
            self.compare(path, [["-d", "-mcpu=r3"]])


if __name__ == "__main__":
    unittest.main()


class ChipNotes(unittest.TestCase):
    def test_chip_annotation_and_default(self):
        import contextlib
        import io
        import tempfile
        from pi32v2isa import asm
        obj = asm.assemble_source("\t.text\n\tr0 = popcnt(r1)\n\tr2 = r3 + r4\n", "x.s", features={"instrev3"})
        with tempfile.NamedTemporaryFile(suffix=".o") as f:
            f.write(obj)
            f.flush()
            outs = []
            for extra in (["--chip=ac791n"], []):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    self.assertEqual(objdump.main(["-d", "-mattr=+instrev3", *extra, f.name]), 0)
                outs.append(buf.getvalue())
        self.assertIn("r0 = popcnt(r1)\t; ac791n: does nothing\n", outs[0])
        self.assertNotIn("ac791n", outs[1])
        self.assertEqual(outs[0].replace("\t; ac791n: does nothing", ""), outs[1])
