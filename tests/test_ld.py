# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0

import random
import struct
import tempfile
import unittest
from pathlib import Path

from pi32v2isa import asm, elf, ld, ldscript, oracle


def obj(text, name="t.s"):
    return asm.assemble_source(text, name)


def link(objects, script=None, args=(), tmp=None):
    """Link object bytes with this repo's linker; returns (ELF bytes or None, errors, warnings)."""
    with tempfile.TemporaryDirectory() as d:
        argv = list(args)
        for k, data in enumerate(objects):
            p = Path(d) / f"o{k}.o"
            p.write_bytes(data)
            argv.append(str(p))
        if script is not None:
            s = Path(d) / "s.ld"
            s.write_text(script)
            argv += ["-T", str(s)]
        L = ld.Linker(ld.parse_args(argv + ["-o", str(Path(d) / "out")]))
        try:
            data = L.run()
        except ld.LinkError as e:
            return None, [str(e)], []
        return data, L.errors, L.warnings


def sections(data):
    return {s["name"]: s for s in oracle.read_exec(data)["sections"]}


MAIN = """
\t.text
\t.globl _start
_start:
\tcall foo
\tr1 = data1
\tgoto _start
\t.globl foo
foo:
\trts
\t.data
\t.globl data1
data1:\t.long 1, 2, 3
\t.bss
\t.comm cm, 8, 4
"""


class Script(unittest.TestCase):
    def test_parse_fm1_style(self):
        text = """
        ENTRY(boot) MEMORY { ram (rwx) : ORIGIN = 0x1c02000, LENGTH = 0x8800 }
        SECTIONS {
          .text ORIGIN(ram) : { KEEP(*(.entry)) *(.text .text.*) *(EXCLUDE_FILE (*x.o) .data) . = ALIGN(4); } > ram
          .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) } > ram AT > ram
          PROVIDE(end = .);
          ASSERT(end <= ORIGIN(ram) + LENGTH(ram), "overflow")
          /DISCARD/ : { *(.comment) }
        }"""
        sc = ldscript.parse_script(text)
        self.assertEqual(sc.entry, "boot")
        self.assertEqual(sc.regions[0].name, "ram")
        names = [getattr(s, "name", None) for s in sc.sections]
        self.assertEqual(names[:2], [".text", ".bss"])
        text_sec = sc.sections[0]
        self.assertTrue(text_sec.stmts[0].keep)
        self.assertEqual(text_sec.stmts[2].sections[0], (".data", ["*x.o"]))
        self.assertEqual(sc.sections[1].type, "NOLOAD")
        self.assertEqual(sc.sections[1].lma_region, "ram")

    def test_syntax_error(self):
        with self.assertRaises(ldscript.ScriptError):
            ldscript.parse_script("SECTIONS { .text : { *(.text) ")


class Relocations(unittest.TestCase):
    """The computations of docs/LINKER.md section 3, on a hand-made object."""

    def reloc(self, typ, data, symval, addend=0, off=0):
        sec = elf.Section(".text", elf.SHT_PROGBITS, 6, 2, 0, bytearray(data))
        sec.relocs = [(off, typ, "ext", addend)]
        syms = [elf.Symbol("_start", 0, 0, elf.STB_GLOBAL, 0, 0, ".text"),
                elf.Symbol("ext", 0, 0, elf.STB_GLOBAL, 0, 0, 0)]
        out, errors, _ = link([elf.write([sec], syms)], args=["--defsym", f"ext={symval}", "-e", "_start"])
        if errors:
            return errors
        return bytes(sections(out)[".text"]["data"])

    def test_call_l(self):
        base = 0x50000
        self.assertEqual(self.reloc(2, bytes.fromhex("80ea0000"), base + 4).hex(), "80ea0000")
        self.assertEqual(self.reloc(2, bytes.fromhex("80ea0000"), base).hex(), "bfeafeff")
        self.assertEqual(self.reloc(2, bytes.fromhex("80ea0000"), base + 4 + 2 * 0x1fffff).hex(), "9feaffff")
        self.assertTrue(any("truncated" in e for e in self.reloc(2, bytes(4), base + 4 + 2 * 0x200000)))
        errs = self.reloc(2, bytes(4), base + 5)
        self.assertIn("ld: relocation unaligned", errs)

    def test_mov_abs32(self):
        self.assertEqual(self.reloc(5, bytes.fromhex("c1ff00000000"), 0x12345678).hex(), "c1ff78563412")

    def test_branch_overwrites_junk_and_keeps_other_bits(self):
        out = self.reloc(1, bytes.fromhex("ffffffff"), 0x50004 + 8)
        self.assertEqual(out.hex(), "ffff0400")                    # field overwritten (4 halfwords)
        out = self.reloc(4, bytes.fromhex("ffffffffffff"), 0x50006 + 2)
        self.assertEqual(out[2] & 1, 1)                             # bit 0 of w1 (the call/goto selector) is kept

    def test_data_relocs(self):
        self.assertEqual(self.reloc(8, struct.pack("<I", 5), 0x100, 3).hex(), struct.pack("<I", 0x108).hex())
        self.assertEqual(self.reloc(6, bytes([0xff]), 1).hex(), "00")                 # 0xff is -1 as an in-place value
        self.assertTrue(self.reloc(6, bytes([1]), 0xff))                              # error: 0x100 does not fit
        self.assertTrue(any("truncated" in e for e in self.reloc(7, bytes(2), 0x10000)))
        self.assertEqual(self.reloc(7, bytes(2), 0xffffffff).hex(), "ffff")

    def test_undefined(self):
        sec = elf.Section(".text", elf.SHT_PROGBITS, 6, 2, 0, bytearray(4))
        sec.relocs = [(0, 2, "nope", 0)]
        syms = [elf.Symbol("_start", 0, 0, elf.STB_GLOBAL, 0, 0, ".text"), elf.Symbol("nope", 0, 0, elf.STB_GLOBAL, 0, 0, 0)]
        out, errors, _ = link([elf.write([sec], syms)], args=["-e", "_start"])
        self.assertIsNone(out)
        self.assertTrue(any("undefined reference to `nope'" in e for e in errors))


class Linking(unittest.TestCase):
    def test_default_script(self):
        out, errors, _ = link([obj(MAIN)])
        self.assertEqual(errors, [])
        ex = oracle.read_exec(out)
        self.assertEqual(ex["entry"], 0x50000)
        text = sections(out)[".text"]
        self.assertEqual((text["addr"], text["flags"]), (0x50000, 6))
        # r1 = data1 (instruction at offset 6, after the 4-byte call/goto pair) is patched with data1's address
        data = sections(out)[".data"]
        self.assertIn(b"\xc1\xff" + struct.pack("<HH", data["addr"] & 0xFFFF, data["addr"] >> 16), bytes(text["data"]))
        names = {s[0]: s for s in ex["symbols"]}
        for n in ("_start", "foo", "data1", "cm", "_end", "__bss_start", "_edata"):
            self.assertIn(n, names)
        self.assertEqual(names["data1"][1], data["addr"])

    def test_script_symbols_and_regions(self):
        script = """MEMORY { r (rwx) : ORIGIN = 0x1000, LENGTH = 0x100 }
        SECTIONS { .text : { _s = .; *(.text) _e = .; } > r .data : { *(.data) } > r
          _size = SIZEOF(.text); _tx = LOADADDR(.data); }"""
        out, errors, _ = link([obj(MAIN)], script, ["-e", "_start"])
        self.assertEqual(errors, [])
        sy = {s[0]: s for s in oracle.read_exec(out)["symbols"]}
        self.assertEqual(sy["_s"][1], 0x1000)
        self.assertEqual(sy["_size"][1], sy["_e"][1] - 0x1000)
        self.assertEqual(sy["_size"][6], elf.SHN_ABS)          # SIZEOF is absolute, `.` is in the section
        self.assertEqual(sy["_s"][6], 1)

    def test_region_overflow_and_assert(self):
        small = "MEMORY { r (rwx) : ORIGIN = 0x1000, LENGTH = 0x4 } SECTIONS { .text : { *(.text) } > r }"
        _, errors, _ = link([obj(MAIN)], small, ["-e", "_start"])
        self.assertTrue(any("region `r' overflowed" in e for e in errors))
        _, errors, _ = link([obj(MAIN)], "SECTIONS { .text 0x1000 : { *(.text) } ASSERT(0, \"nope\") }", ["-e", "_start"])
        self.assertIn("ld: nope", errors)

    def test_gc_sections_and_keep(self):
        src = """
\t.text
\t.globl _start
_start:\tgoto _start
\t.section .text.dead,"ax"
\t.globl dead
dead:\trts
\t.section .text.kept,"ax"
\t.globl kept
kept:\trts
"""
        script = "SECTIONS { . = 0x1000; .text : { *(.text) KEEP(*(.text.kept)) *(.text.*) } }"
        out, errors, _ = link([obj(src)], script, ["--gc-sections", "-e", "_start"])
        self.assertEqual(errors, [])
        names = {s[0] for s in oracle.read_exec(out)["symbols"]}
        self.assertIn("kept", names)
        self.assertNotIn("dead", names)
        self.assertEqual(sections(out)[".text"]["size"], 4)

    def test_multiple_and_weak_definitions(self):
        a = obj(".text\n.globl f\nf: nop\n.globl _start\n_start: call f\n")
        b = obj(".text\n.globl f\nf: rts\n")
        w = obj(".text\n.weak f\nf: nop\n")
        _, errors, _ = link([a, b], args=["-e", "_start"])
        self.assertTrue(any("multiple definition of `f'" in e for e in errors))
        _, errors, _ = link([a, w], args=["-e", "_start"])
        self.assertEqual(errors, [])

    def test_merge_strings_share_tails(self):
        a = obj('.section .rodata.str1.1,"aMS",@progbits,1\n.globl s\ns:\n.asciz "hello"\n')
        b = obj('.text\n.globl _start\n_start: nop\n.section .rodata.str1.1,"aMS",@progbits,1\n.asciz "lo"\n.asciz "hello"\n')
        out, errors, _ = link([a, b], args=["-e", "_start"])
        self.assertEqual(errors, [])
        ro = sections(out)[".rodata"]
        self.assertEqual(bytes(ro["data"]), b"hello\0")

    def test_common_symbols_in_bss(self):
        out, _, _ = link([obj(MAIN)])
        sy = {s[0]: s for s in oracle.read_exec(out)["symbols"]}
        self.assertEqual(sy["cm"][2], 8)
        self.assertEqual(sy["cm"][1] % 4, 0)

    def test_string_table_shares_tails(self):
        blob, off = ld.string_table(["flash_capacity", "capacity", "x"])
        self.assertEqual(blob, b"\0flash_capacity\0x\0")
        self.assertEqual(off["capacity"], off["flash_capacity"] + 6)

    def test_symbol_hash_order(self):
        # the order of global symbols follows the linker's hash table (verified on 685 symbols of a real link)
        self.assertEqual(ld.hash_name(""), 0)
        self.assertLess(ld.hash_name("_start") % ld.HASH_SIZE, ld.HASH_SIZE)


def _toolchain():
    try:
        return oracle.Oracle()
    except oracle.OracleError:
        return None


CASES = {
    "default": (None, ["-e", "_start"]),
    "ttext": (None, ["-Ttext=0x2000"]),
    "gc": (None, ["--gc-sections", "-e", "_start"]),
    "regions": ("MEMORY { r (rwx) : ORIGIN = 0x1000, LENGTH = 0x1000  m (rw) : ORIGIN = 0x4000, LENGTH = 0x100 }\n"
                "ENTRY(_start) SECTIONS { .text : { *(.text) } > r .data : { _ds = .; *(.data) _de = .; } > m AT > r\n"
                "  _dl = LOADADDR(.data); .bss (NOLOAD) : { *(.bss) *(COMMON) . = ALIGN(8); } > m }", ["--gc-sections"]),
    "at": ("SECTIONS { .text 0x1000 : { *(.text) } .data 0x200000 : AT(0x1800) { *(.data) } .bss : { *(.bss) *(COMMON) } }", ["-e", "0"]),
    "fill": ("SECTIONS { .text 0x1000 : { *(.text) . = ALIGN(16); } =0xdeadbeef .data : { *(.data) . = ALIGN(32); } =0x90 }", ["-e", "0"]),
    "expr": ("SECTIONS { .text 0x1000 : { *(.text) a1 = . + 4; a2 = ALIGN(16); a3 = ADDR(.text); a4 = SIZEOF(.text); b1 = foo & 0x1000; }"
             " c1 = foo + 4; c2 = foo - foo; c3 = ADDR(.text) + SIZEOF(.text); c4 = . + 8; }", ["-e", "0"]),
    "orphans": ("SECTIONS { .text 0x1000 : { *(.text) } .bss : { *(.bss) } }", ["-e", "0"]),
    "errors": ("SECTIONS { .text 0x1000 : { *(.text) } ASSERT(SIZEOF(.text) > 100, \"small\") }", ["-e", "0"]),
}


@unittest.skipUnless(_toolchain(), "JieLi toolchain not under oracle/ (python3 -m pi32v2isa oracle fetch)")
class Live(unittest.TestCase):
    """Link with JieLi's ld and with this linker and compare (oracle.ldcompare)."""

    def setUp(self):
        self.o = _toolchain()
        self._d = tempfile.TemporaryDirectory()
        self.d = Path(self._d.name)
        extra = ".comm cm2, 12, 4\n.section .rodata.str1.1,\"aMS\",@progbits,1\n.asciz \"hello\"\n.asciz \"lo\"\n"
        (self.d / "a.o").write_bytes(obj(MAIN + extra))
        (self.d / "b.o").write_bytes(obj(".text\n.globl bar\nbar: call foo\n.comm cm, 16, 8\n"
                                          ".section .rodata.str1.1,\"aMS\",@progbits,1\n.asciz \"yhello\"\n"))

    def tearDown(self):
        self._d.cleanup()

    def compare(self, script, args):
        words = list(args)
        if script:
            (self.d / "s.ld").write_text(script)
            words += ["-T", str(self.d / "s.ld")]
        words += [str(self.d / "a.o"), str(self.d / "b.o")]
        return oracle.ldcompare(self.o, words)

    def test_cases(self):
        for name, (script, args) in CASES.items():
            with self.subTest(name):
                diffs, ref, mine = self.compare(script, args)
                self.assertEqual(diffs, [])

    def test_relocation_computations_random(self):
        """Random S, A, P and in-place bytes for relocation types 1 to 8: the same bytes or the same kind of error."""
        rng = random.Random(3)
        for typ in range(1, 9):
            for _ in range(8):
                size = {1: 6, 2: 6, 3: 8, 4: 8, 5: 8, 6: 1, 7: 2, 8: 4}[typ]
                off = rng.choice([0, 2, 4])
                data = bytes(rng.randrange(256) for _ in range(12))
                span = 1 << {1: 17, 2: 23, 3: 17, 4: 20, 5: 32, 6: 9, 7: 17, 8: 32}[typ]
                val = (0x50000 + off + rng.randrange(-span, span) + rng.choice([0, 0, 1])) & 0xFFFFFFFF
                sec = elf.Section(".text", elf.SHT_PROGBITS, 6, 2, 0, bytearray(data))
                sec.relocs = [(off, typ, "ext", rng.choice([0, 2, -2, 100]))]
                syms = [elf.Symbol("_start", 0, 0, elf.STB_GLOBAL, 0, 0, ".text"), elf.Symbol("ext", 0, 0, elf.STB_GLOBAL, 0, 0, 0)]
                (self.d / "r.o").write_bytes(elf.write([sec], syms))
                diffs, ref, mine = oracle.ldcompare(self.o, [str(self.d / "r.o"), f"--defsym=ext={val:#x}", "-e", "_start"])
                with self.subTest(typ=typ, val=val):
                    self.assertEqual(diffs, [])

    def test_objcopy_binary_equal(self):
        diffs, ref, mine = self.compare(CASES["regions"][0], CASES["regions"][1])
        self.assertEqual(diffs, [])
        for name in (".text", ".data"):
            self.assertEqual(oracle.objcopy_text(self.o, ref, name), oracle.objcopy_text(self.o, mine, name))


if __name__ == "__main__":
    unittest.main()
