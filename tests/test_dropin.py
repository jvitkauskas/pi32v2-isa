# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""The drop-in toolchain's command line translation (docs/DROPIN.md, tools/dropin/jlwrap.py): what is dropped,
translated and kept of the options JieLi's clang and ld take, and the tools' text for a hand-made ELF file."""

import importlib.util
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools" / "dropin"
spec = importlib.util.spec_from_file_location("jlwrap", TOOLS / "jlwrap.py")
jlwrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jlwrap)

SDK_CFLAGS = ("-target pi32v2 -integrated-as -mcpu=r3 -mfprev1 -Wuninitialized -fno-common -Oz -g -flto "
              "-fallow-pointer-null -fprefer-gnu-section -femulated-tls -mllvm -pi32v2-large-program=true "
              "-fms-extensions -w -ffunction-sections -c a.c -o a.o").split()


class ClangTest(unittest.TestCase):
    def test_jieli_only_options(self):
        out = jlwrap.clang_args(SDK_CFLAGS)
        self.assertNotIn("-fallow-pointer-null", out)
        self.assertIn("-fprefer-gnu-section", out)       # the fork's clang has the option itself
        self.assertIn("-pi32v2-large-program=true", out)
        self.assertIn("-mllvm", out)
        self.assertIn("-fno-delete-null-pointer-checks", out)
        self.assertIn("+fprev1", out)
        for kept in ("-target", "pi32v2", "-mcpu=r3", "-Oz", "-flto", "-femulated-tls", "-fms-extensions", "a.c"):
            self.assertIn(kept, out)

    def test_other_mllvm_options_stay(self):
        out = jlwrap.clang_args(["-mllvm", "-print-after-all", "-c", "a.c"])
        self.assertEqual(out[out.index("-mllvm"):out.index("-mllvm") + 2], ["-mllvm", "-print-after-all"])

    def test_default_standard(self):
        self.assertIn("-std=gnu11", jlwrap.clang_args(["-c", "a.c"]))
        self.assertNotIn("-std=gnu11", jlwrap.clang_args(["-std=c99", "-c", "a.c"]))
        self.assertFalse([a for a in jlwrap.clang_args(["-std=gnu++14", "-c", "a.cpp"]) if a == "-std=gnu11"])

    def test_dwarf_version(self):
        self.assertIn("-gdwarf-4", jlwrap.clang_args(["-g", "-c", "a.c"]))
        self.assertNotIn("-gdwarf-4", jlwrap.clang_args(["-c", "a.c"]))
        self.assertNotIn("-gdwarf-4", jlwrap.clang_args(["-g", "-gdwarf-5", "-c", "a.c"]))

    def test_old_c_is_not_an_error(self):
        out = jlwrap.clang_args(["-c", "a.c"])
        self.assertIn("-Wno-error=implicit-function-declaration", out)
        self.assertIn("-Wno-error=incompatible-function-pointer-types", out)


LD_ARGS = ("-o sdk.elf @objs.txt --plugin-opt=-pi32v2-always-use-itblock=false --plugin-opt=-enable-ipra=true "
           "--plugin-opt=mcpu=r3 --plugin-opt=-inline-max-allocated-size=32 --plugin-opt=-inline-threshold=5 "
           "--plugin-opt=save-temps --plugin-opt=-enable-movable-region=true --plugin-opt=-mattr=+fprev1 "
           "--sort-common --start-group libm.a libc.a libcompiler_rt.a --start-group cpu.a system.a --end-group "
           "libc++.a -Tsdk.ld -M=sdk.map --end-group --plugin /x/LLVMgold.so").split()


class LdTest(unittest.TestCase):
    def test_plugin_options(self):
        out, rel = jlwrap.ld_args(LD_ARGS)
        self.assertFalse(rel)
        self.assertNotIn("--plugin", out)
        self.assertFalse([a for a in out if "LLVMgold" in a or "itblock" in a or "movable" in a or "mattr" in a])
        self.assertIn("-mllvm=-enable-ipra=true", out)
        self.assertIn("-mllvm=-inline-max-stacksize=32", out)
        self.assertIn("--plugin-opt=mcpu=r3", out)
        self.assertIn("--save-temps", out)
        self.assertIn("-Map=sdk.map", out)
        self.assertFalse([a for a in out if "inline-threshold" in a])

    def test_groups(self):
        out, _ = jlwrap.ld_args(LD_ARGS)
        self.assertEqual(out.count("--start-group"), 1)
        self.assertEqual(out.count("--end-group"), 1)
        # the C library, last in its group
        self.assertEqual(out[out.index("--end-group") - 3:out.index("--end-group")],
                         ["libm.a", "libc.a", "libcompiler_rt.a"])
        self.assertLess(out.index("cpu.a"), out.index("libm.a"))

    def test_used_symbols(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "used")
            Path(f).write_text("\nsdfile_vfs_ops\n\nclock_port\n")
            out, _ = jlwrap.ld_args(["--plugin-opt=-used-symbol-file=" + f])
        self.assertEqual(out, ["--undefined-glob=sdfile_vfs_ops", "--undefined-glob=clock_port"])

    def test_relocatable(self):
        self.assertTrue(jlwrap.ld_args(["-r", "a.o"])[1])

    def test_response_file(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "objs")
            Path(f).write_text("a.o\nb.o\n")
            self.assertEqual(jlwrap.expand(["-o", "x", "@" + f]), ["-o", "x", "a.o", "b.o"])


def elf32(sections, symbols):
    """A tiny ELF32 file: sections [(name, type, flags, addr, data)], symbols [(name, value, size, info, shndx)]."""
    names = b"\0"
    nameoff = {}
    for n, *_ in sections:
        nameoff[n] = len(names)
        names += n.encode() + b"\0"
    nameoff[".shstrtab"] = len(names)
    names += b".shstrtab\0"
    nameoff[".symtab"] = len(names)
    names += b".symtab\0"
    nameoff[".strtab"] = len(names)
    names += b".strtab\0"
    strtab = b"\0"
    symtab = b"\0" * 16
    for n, value, size, info, shndx in symbols:
        symtab += struct.pack("<IIIBBH", len(strtab), value, size, info, 0, shndx)
        strtab += n.encode() + b"\0"
    body = b""
    off = 52
    heads = [struct.pack("<10I", *([0] * 10))]
    for n, typ, flags, addr, data in sections:
        heads.append(struct.pack("<10I", nameoff[n], typ, flags, addr, off + len(body), len(data), 0, 0, 1, 0))
        body += data
    shstr_off = off + len(body)
    body += names
    heads.append(struct.pack("<10I", nameoff[".shstrtab"], 3, 0, 0, shstr_off, len(names), 0, 0, 1, 0))
    nsec = len(sections) + 3          # null, the sections, .shstrtab, .symtab, .strtab
    sym_off = off + len(body)
    body += symtab
    heads.append(struct.pack("<10I", nameoff[".symtab"], 2, 0, 0, sym_off, len(symtab), nsec, 0, 4, 16))
    str_off = off + len(body)
    body += strtab
    heads.append(struct.pack("<10I", nameoff[".strtab"], 3, 0, 0, str_off, len(strtab), 0, 0, 1, 0))
    shoff = off + len(body)
    ident = b"\x7fELF" + bytes([1, 1, 1, 0]) + b"\0" * 8
    hdr = ident + struct.pack("<HHIIIIIHHHHHH", 2, 241, 1, 0, 0, shoff, 0, 52, 0, 0, 40, len(heads), len(heads) - 3)
    return hdr + body + b"".join(heads)


def ar_file(members, armap):
    """A GNU archive: members [(name, data)], armap [(symbol, member index)]."""
    longnames = b""
    heads = []
    for name, data in members:
        if len(name) > 15:
            heads.append("/%d" % len(longnames))
            longnames += name.encode() + b"/\n"
        else:
            heads.append(name + "/")
    body = b""
    offsets = []
    tail = b""
    # the symbol table and the name table come first; offsets are known once their sizes are
    sym_size = 4 + 4 * len(armap) + sum(len(s) + 1 for s, _ in armap)
    sym_size += sym_size & 1
    pos = 8 + 60 + sym_size + (60 + len(longnames) + (len(longnames) & 1) if longnames else 0)
    for (name, data), h in zip(members, heads):
        offsets.append(pos)
        hdr = ("%-16s%-12d%-6d%-6d%-8s%-10d`\n" % (h, 0, 0, 0, "644", len(data))).encode()
        body += hdr + data + (b"\0" if len(data) & 1 else b"")
        pos += 60 + len(data) + (len(data) & 1)
    sym = struct.pack(">I", len(armap)) + b"".join(struct.pack(">I", offsets[i]) for _, i in armap)
    sym += b"".join(s.encode() + b"\0" for s, _ in armap)
    sym += b"\0" * (len(sym) & 1)
    out = b"!<arch>\n" + ("%-16s%-12d%-6d%-6d%-8s%-10d`\n" % ("/", 0, 0, 0, "0", len(sym))).encode() + sym
    if longnames:
        ln = longnames + b"\0" * (len(longnames) & 1)
        out += ("%-16s%-12d%-6d%-6d%-8s%-10d`\n" % ("//", 0, 0, 0, "0", len(longnames))).encode() + ln
    return out + body


class ArchiveTest(unittest.TestCase):
    def test_members_and_symbol_table(self):
        data = ar_file([("a.o", b"AAA"), ("a_rather_long_member_name.o", b"BBBB"), ("c.o", b"C")],
                       [("fa", 0), ("fb", 1), ("fc", 2), ("fb2", 1)])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.a")
            Path(path).write_bytes(data)
            members, armap, raw = jlwrap.ar_members(path)
        self.assertEqual([m[0] for m in members.values()], ["a.o", "a_rather_long_member_name.o", "c.o"])
        offs = list(members)
        self.assertEqual([(s, offs.index(o)) for s, o in armap], [("fa", 0), ("fb", 1), ("fc", 2), ("fb2", 1)])
        name, body, size = members[offs[1]]
        self.assertEqual(raw[body:body + size], b"BBBB")


class ObjsizedumpTest(unittest.TestCase):
    def test_lite_listing(self):
        data = elf32([(".text", 1, 6, 0x2000000, b"\0" * 16), (".data", 1, 3, 0x1c00000, b"\0" * 8)],
                     [("main", 0x2000000, 12, 0x12, 1), ("tab", 0x1c00000, 8, 0x11, 2),
                      ("empty", 0x2000010, 0, 0x12, 1), ("loc", 0x2000008, 4, 0x02, 1),
                      ("weak", 0x2000004, 4, 0x22, 1)])
        with tempfile.TemporaryDirectory() as d:
            # started under the tool's name, in <root>/common/bin
            bin_dir = Path(d) / "common" / "bin"
            bin_dir.mkdir(parents=True)
            tool = bin_dir / "objsizedump"
            tool.symlink_to(TOOLS / "jlwrap.py")
            elf = Path(d) / "t.elf"
            elf.write_bytes(data)
            out = subprocess.run([sys.executable, str(tool), "-lite", "-skip-zero", str(elf)],
                                 capture_output=True, text=True, check=True).stdout.splitlines()
        self.assertEqual(out, [
            "SYMBOL TABLE LITE:",
            "02000000 g-   -F .text\t\t 0000000c main",
            "01c00000 g-   -O .data\t\t 00000008 tab",
            "02000008 l-   -F .text\t\t 00000004 loc",
            "02000004 gw   -F .text\t\t 00000004 weak",
        ])


if __name__ == "__main__":
    unittest.main()
