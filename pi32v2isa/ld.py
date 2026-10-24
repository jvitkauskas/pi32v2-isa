# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""An open linker for pi32v2 ELF objects (docs/LINKER.md). It reads the relocatable objects JieLi's assembler and
compiler write (docs/ELF.md), lays them out as a linker script says, applies the relocations and writes an ELF
executable laid out like JieLi's `ld` writes it.

    python3 -m pi32v2isa ld [options] objects... -o OUT

Everything here was established by linking small test objects and the FM-1 projects with JieLi's `ld` and comparing
(`python3 -m pi32v2isa oracle ldcompare`); docs/LINKER.md has the evidence."""

import fnmatch
import os
import struct
import sys
from pathlib import Path

from . import elf
from . import ldscript as S
from .ldscript import MASK64, ScriptError, parse_script

PAGE = 0x500                       # JieLi's ld aligns program segments to 0x500 bytes
HASH_SIZE = 4051                   # size of the linker's symbol hash table: it sets the order of global symbols
SHF_ALLOC, SHF_WRITE, SHF_EXEC = elf.SHF_ALLOC, elf.SHF_WRITE, elf.SHF_EXECINSTR
SHT_PROGBITS, SHT_NOBITS, SHT_NOTE = elf.SHT_PROGBITS, elf.SHT_NOBITS, 7
SHT_INIT_ARRAY, SHT_FINI_ARRAY, SHT_PREINIT_ARRAY, SHT_GROUP = 14, 15, 16, 17
SHF_MERGE, SHF_STRINGS = elf.SHF_MERGE, elf.SHF_STRINGS
PT_LOAD = 1
RELOC_MAX = 16

# The script used when none is given: text at 0x50000, data in the next page-offset-preserving address.
DEFAULT_SCRIPT = """
SECTIONS
{
  . = 0x50000;
  .text : { *(.text .stub .text.*) }
  .rodata : { *(.rodata .rodata.*) }
  . = ALIGN(0x500) + (. & 0x4ff);
  .data : { *(.data .data.*) *(.sdata .sdata.*) }
  .bss : { __bss_start = .; *(.bss .bss.*) *(.sbss .sbss.*) *(COMMON) . = ALIGN(4); }
  .comment : { *(.comment) }
  /DISCARD/ : { *(.note.GNU-stack) }
}
"""


class LinkError(Exception):
    pass


def align_up(x, a):
    return x if a <= 1 else (x + a - 1) // a * a


def s32(x):
    x &= 0xFFFFFFFF
    return x - (1 << 32) if x >> 31 else x


def hash_name(name):
    """The linker's symbol hash (the order of global symbols in the output follows its buckets)."""
    h = 0
    for c in name.encode():
        h = (h + c + (c << 17)) & 0xFFFFFFFF
        h ^= h >> 2
    n = len(name.encode())
    h = (h + n + (n << 17)) & 0xFFFFFFFF
    h ^= h >> 2
    return h


def string_table(names):
    """(bytes, {name: offset}) for names given in the order they were first added: a name that ends another name is
    stored inside it (found the way the linker finds them: sort by reversed spelling, a name ending the next one
    in that order is merged into it); the remaining names keep their order of first appearance."""
    uniq = []
    seen = set()
    for n in names:
        if n and n not in seen:
            seen.add(n)
            uniq.append(n)
    raw = [n.encode() for n in uniq]
    order = sorted(range(len(uniq)), key=lambda k: raw[k][::-1])
    into = {}
    for a, b in zip(order, order[1:]):
        if raw[b].endswith(raw[a]) and raw[a] != raw[b]:
            into[a] = b
    out = bytearray(b"\0")
    off = {}
    for k in range(len(uniq)):
        if k not in into:
            off[k] = len(out)
            out += raw[k] + b"\0"
    for k in range(len(uniq)):
        if k in into:
            t, shift = k, 0
            while t in into:
                nxt = into[t]
                shift += len(raw[nxt]) - len(raw[t])
                t = nxt
            off[k] = off[t] + shift
    return bytes(out), {uniq[k]: off[k] for k in range(len(uniq))} | {"": 0}


# --- input -----------------------------------------------------------------------------------------------------

class InSec:
    """One section of one input object."""

    def __init__(self, obj, index, name, typ, flags, align, entsize, data, size):
        self.obj, self.index, self.name, self.type, self.flags = obj, index, name, typ, flags
        self.align, self.entsize, self.data, self.size = max(align, 1), entsize, data, size
        self.relocs = []                # (offset, type, symbol index, addend)
        self.live = True
        self.keep = False
        self.out = None                 # OutSection it is placed in
        self.offset = 0                 # offset in the output section
        self.discarded = False
        self.mergemap = None            # for SHF_MERGE sections: [(old start, old length, holder, new offset)]

    @property
    def alloc(self):
        return bool(self.flags & SHF_ALLOC)

    @property
    def nobits(self):
        return self.type == SHT_NOBITS

    def __repr__(self):
        return f"<{self.obj.name}:{self.name}>"


class ObjSym:
    __slots__ = ("name", "value", "size", "bind", "type", "other", "shndx", "index", "g", "sec", "keep")

    def __init__(self, name, value, size, bind, typ, other, shndx, index):
        self.name, self.value, self.size, self.bind, self.type, self.other = name, value, size, bind, typ, other
        self.shndx, self.index, self.g, self.sec, self.keep = shndx, index, None, None, True


class ObjFile:
    def __init__(self, name, data):
        self.name = name
        self.sections = {}               # index -> InSec (loadable sections only)
        self.symbols = []
        self.parse(data)

    def parse(self, data):
        if data[:4] != b"\x7fELF" or len(data) < 52:
            raise LinkError(f"{self.name}: file not recognized: File format not recognized")
        if data[4] != 1 or data[5] != 1:
            raise LinkError(f"{self.name}: file not recognized: File format not recognized")
        etype, machine, _, _, _, shoff, _, _, _, _, shentsize, shnum, shstrndx = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
        if etype != 1 or machine != elf.EM_PI32V2:
            raise LinkError(f"{self.name}: file not recognized: File format not recognized")
        raw = [struct.unpack_from("<10I", data, shoff + k * shentsize) for k in range(shnum)]

        def cstr(base, off):
            return data[base + off:data.index(b"\0", base + off)].decode()

        strbase = raw[shstrndx][4]
        symtab = None
        for k, (name, typ, flg, addr, off, size, link, info, align, entsize) in enumerate(raw):
            if typ == elf.SHT_SYMTAB:
                symtab = (off, size, link)
        for k, (name, typ, flg, addr, off, size, link, info, align, entsize) in enumerate(raw):
            if k == 0 or typ in (elf.SHT_SYMTAB, elf.SHT_STRTAB, elf.SHT_RELA, 9, SHT_GROUP):
                continue
            body = None if typ == SHT_NOBITS else bytearray(data[off:off + size])
            self.sections[k] = InSec(self, k, cstr(strbase, name), typ, flg, align, entsize, body, size)
        if symtab:
            off, size, link = symtab
            sb = raw[link][4]
            for n in range(size // 16):
                nm, value, sz, infob, other, shndx = struct.unpack_from("<IIIBBH", data, off + 16 * n)
                sym = ObjSym(cstr(sb, nm), value, sz, infob >> 4, infob & 15, other, shndx, n)
                self.symbols.append(sym)
                if 0 < shndx < 0xFF00:
                    sym.sec = self.sections.get(shndx)
        for k, (name, typ, flg, addr, off, size, link, info, align, entsize) in enumerate(raw):
            if typ == elf.SHT_RELA:
                target = self.sections.get(info)
                for n in range(size // 12):
                    o, i, a = struct.unpack_from("<IIi", data, off + 12 * n)
                    if target is not None:
                        target.relocs.append((o, i & 0xFF, i >> 8, a))
            elif typ == 9:
                raise LinkError(f"{self.name}: REL relocations are not supported")


class Archive:
    def __init__(self, name, data):
        self.name = name
        self.members = []                # (member name, bytes or None once pulled)
        pos, longnames = 8, b""
        while pos + 60 <= len(data):
            hdr = data[pos:pos + 60]
            mname = hdr[:16].decode().strip()
            size = int(hdr[48:58].decode().strip())
            body = data[pos + 60:pos + 60 + size]
            pos += 60 + size + (size & 1)
            if mname == "//":
                longnames = body
                continue
            if mname in ("/", "/SYM64/"):
                continue
            if mname.startswith("/") and mname[1:].isdigit():
                start = int(mname[1:])
                mname = longnames[start:longnames.index(b"/\n", start)].decode()
            self.members.append((mname.rstrip("/"), body))


# --- linker state ----------------------------------------------------------------------------------------------

class GSym:
    """A global symbol after resolution."""

    def __init__(self, name):
        self.name = name
        self.kind = "undef"              # undef, def, common, script
        self.sym = None                  # defining ObjSym
        self.obj = None
        self.weak = False                # the definition is weak
        self.weakref = True              # every reference seen so far was weak
        self.common_size = 0
        self.common_align = 1
        self.refs = False                # referenced by some object
        self.order = 0                   # insertion number (hash-table order)
        self.script = None               # (value, out section or None) from the last script evaluation
        self.hidden = False
        self.in_sec = False              # a script symbol assigned inside an output section statement
        self.top_ref = False             # referenced by a script expression outside output sections
        self.live_ref = False            # referenced from a live input section
        self.defsym_sec = None           # the synthetic section of an allocated common symbol
        self.defsym_off = 0


class OutSection:
    def __init__(self, name, spec=None):
        self.name = name
        self.spec = spec
        self.inputs = []                 # InSec, in placement order
        self.matched = {}                # id(InputSpec) -> [InSec]
        self.vma = self.lma = self.size = 0
        self.align = 1
        self.type = SHT_PROGBITS
        self.flags = 0
        self.data = bytearray()
        self.index = 0
        self.offset = 0
        self.region = None
        self.lma_region = None
        self.nobits = False
        self.noload = False
        self.emit = True
        self.has_syms = False
        self.alloc = True
        self.fill = b"\0"
        self.pieces = []                 # (offset, bytes) data statements
        self.gaps = []                   # (start offset, end offset) to fill

    def __repr__(self):
        return f"<out {self.name} {self.vma:#x}+{self.size:#x}>"


class MemRegion:
    def __init__(self, name, attrs, origin, length):
        self.name, self.attrs, self.origin, self.length = name, attrs, origin, length
        self.current = origin


class Val:
    __slots__ = ("v", "sec")

    def __init__(self, v, sec=None):
        self.v, self.sec = v & MASK64, sec


class Options:
    def __init__(self):
        self.output = "a.out"
        self.scripts = []
        self.entry = None
        self.gc = False
        self.map = None
        self.defsyms = []                # (name, expr text)
        self.undefined = []
        self.libpaths = []
        self.inputs = []                 # ("file", path) / ("lib", name) / ("start-group",) / ("end-group",)
        self.ttext = self.tdata = self.tbss = None
        self.strip_all = False
        self.strip_debug = False
        self.allow_multiple = False
        self.noinhibit = False
        self.print_gc = False
        self.fatal_warnings = False
        self.discard_all = False


def glob_match(pat, name):
    return fnmatch.fnmatchcase(name, pat)


def file_match(pat, path):
    if pat is None:
        return True
    if "/" not in pat and glob_match(pat, os.path.basename(path)):
        return True
    return glob_match(pat, path)


def section_class(sec):
    return (bool(sec.flags & SHF_EXEC), bool(sec.flags & SHF_WRITE), sec.nobits)


class Linker:
    def __init__(self, opts):
        self.o = opts
        self.errors = []
        self.warnings = []
        self.objs = []
        self.globals = {}                # name -> GSym
        self.counter = 0
        self.script = None
        self.regions = {}
        self.outs = []                   # OutSection, in script order (includes /DISCARD/ ones: .discard True)
        self.outs_by_name = {}
        self.script_defined = set()
        self.entry_name = None
        self.entry_value = 0
        self.asserts = []
        self.hdr_size = 52
        self.nphdr = 0
        self.pass_no = 0

    # -- diagnostics
    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    # ======================================================================================================
    # 1. reading the inputs
    # ======================================================================================================
    def read_script(self):
        o = self.o
        self.script = S.Script()
        for p in o.scripts:
            try:
                one = parse_script(Path(p).read_text(), p)
            except OSError as e:
                raise LinkError(f"cannot open linker script file {p}: {e.strerror}")
            except ScriptError as e:
                raise LinkError(str(e))
            sc = self.script
            sc.entry = sc.entry or one.entry
            sc.regions += one.regions
            if one.sections is not None:
                sc.sections = (sc.sections or []) + one.sections
            sc.top += one.top
            sc.extern += one.extern
            sc.inputs += one.inputs
        if self.script.sections is None:
            self.script.sections = parse_script(DEFAULT_SCRIPT, "<default>").sections
            if o.scripts:
                pass
        if o.ttext is not None:
            for st in self.script.sections:
                if isinstance(st, S.Assign) and st.name == ".":
                    st.expr = ("num", o.ttext)
                    break
        for r in self.script.regions:
            self.regions[r.name] = MemRegion(r.name, r.attrs, 0, 0)

    def read_inputs(self):
        o = self.o
        for name in list(o.undefined) + list(self.script.extern):
            g = self.gsym(name)
            g.refs = True
        archives = []
        for item in list(o.inputs) + [("file", n) for n in self.script.inputs]:
            if item[0] in ("start-group", "end-group"):
                continue
            path = self.find_lib(item[1]) if item[0] == "lib" else item[1]
            try:
                data = Path(path).read_bytes()
            except OSError as e:
                raise LinkError(f"{path}: {e.strerror}" if item[0] == "file" else f"cannot find {path}")
            if data[:8] == b"!<arch>\n":
                archives.append(Archive(path, data))
            else:
                self.add_object(ObjFile(path, data))
            self.pull_archives(archives)
        self.pull_archives(archives)

    def find_lib(self, name):
        if name.startswith(":"):
            cands = [name[1:]]
        else:
            cands = [f"lib{name}.a"]
        for d in list(self.o.libpaths) + list(self.script.search_dirs):
            for cand in cands:
                p = os.path.join(d, cand)
                if os.path.exists(p):
                    return p
        raise LinkError(f"cannot find -l{name}")

    def gsym(self, name):
        g = self.globals.get(name)
        if g is None:
            g = self.globals[name] = GSym(name)
            g.order = self.counter
            self.counter += 1
        return g

    def add_object(self, obj):
        self.objs.append(obj)
        for sym in obj.symbols[1:]:
            if sym.type in (elf.STT_FILE, elf.STT_SECTION) or sym.bind == elf.STB_LOCAL:
                continue
            g = self.gsym(sym.name)
            sym.g = g
            if sym.shndx == elf.SHN_UNDEF:
                g.refs = True
                if sym.bind != elf.STB_WEAK:
                    g.weakref = False
                continue
            weak = sym.bind == elf.STB_WEAK
            if sym.shndx == elf.SHN_COMMON:
                if g.kind == "def" and not g.weak:
                    continue
                if g.kind == "common":
                    g.common_size = max(g.common_size, sym.size)
                    g.common_align = max(g.common_align, sym.value)
                else:
                    g.kind, g.sym, g.obj = "common", sym, obj
                    g.common_size, g.common_align = sym.size, sym.value
                continue
            if g.kind == "def":
                if g.weak and not weak:
                    pass
                elif weak:
                    continue
                elif self.o.allow_multiple:
                    continue
                else:
                    self.error(f"{obj.name}: In function `{sym.name}':\n{obj.name}: multiple definition of `{sym.name}'"
                               f"\n{g.obj.name}: first defined here")
                    continue
            g.kind, g.sym, g.obj, g.weak = "def", sym, obj, weak

    def pull_archives(self, archives):
        changed = True
        while changed:
            changed = False
            for ar in archives:
                for k, (mname, body) in enumerate(ar.members):
                    if body is None:
                        continue
                    try:
                        obj = ObjFile(f"{ar.name}({mname})", body)
                    except LinkError:
                        continue
                    for sym in obj.symbols[1:]:
                        if sym.bind != elf.STB_LOCAL and sym.shndx != elf.SHN_UNDEF and sym.type not in (
                                elf.STT_FILE, elf.STT_SECTION):
                            g = self.globals.get(sym.name)
                            if g is not None and g.kind in ("undef", "common") and g.refs:
                                ar.members[k] = (mname, None)
                                self.add_object(obj)
                                changed = True
                                break

    # ======================================================================================================
    # 2. matching input sections to the script's output sections
    # ======================================================================================================
    def all_inputs(self):
        for obj in self.objs:
            for idx in sorted(obj.sections):
                yield obj.sections[idx]

    def alloc_commons(self):
        """Every object that declares common symbols gets a section named COMMON (as BFD does): the symbols are laid
        out in it in the order of the linker's hash table (layout_commons does that once garbage collection has
        said which are used), and `*(COMMON)` in the script picks the objects' sections up in command-line order."""
        for g in self.globals.values():
            if g.kind == "common":
                obj = g.obj
                if not hasattr(obj, "common"):
                    sec = InSec(obj, 0x10000, "COMMON", SHT_NOBITS, SHF_ALLOC | SHF_WRITE, 1, 0, None, 0)
                    sec.keep = True      # never collected itself: layout_commons drops unused symbols from it
                    obj.sections[0x10000] = sec
                    obj.common = sec

    def layout_commons(self):
        per = {}
        used = {id(g.obj) for g in self.globals.values() if g.kind == "common" and g.live_ref}
        for g in self.globals.values():
            if g.kind == "common":
                g.defsym_sec = None
                # garbage collection works on whole COMMON sections: one used symbol keeps its object's others
                if id(g.obj) in used or not self.o.gc:
                    per.setdefault(id(g.obj), (g.obj, []))[1].append(g)
        for obj in self.objs:
            if hasattr(obj, "common"):
                obj.common.size, obj.common.align = 0, 1
        for obj, syms in per.values():
            sec = obj.common
            off, al = 0, 1
            for g in sorted(syms, key=lambda g: (hash_name(g.name) % HASH_SIZE, -g.order)):
                a = max(g.common_align, 1)
                off = align_up(off, a)
                g.defsym_sec, g.defsym_off = sec, off
                off += g.common_size
                al = max(al, a)
            sec.size, sec.align = off, al

    def build_outs(self):
        script = self.script
        self.outs = []
        for st in script.sections:
            if isinstance(st, S.OutSec):
                o = OutSection(st.name, st)
                o.noload = st.type == "NOLOAD"
                o.has_syms = any(isinstance(x, (S.DataStmt, S.FillStmt)) or (isinstance(x, S.Assign) and x.name != ".")
                                 for x in st.stmts)
                self.outs.append(o)

    def match(self):
        claimed = set()
        # (discard sections are matched like the others)
        inputs = list(self.all_inputs())
        for o in self.outs:
            for spec in o.spec.stmts:
                if not isinstance(spec, S.InputSpec):
                    continue
                found = []
                for sec in inputs:
                    if id(sec) in claimed:
                        continue
                    if not any(file_match(p, sec.obj.name) for p in spec.file_pats):
                        continue
                    if any(file_match(p, sec.obj.name) for p in spec.file_excl):
                        continue
                    for pat, excl in spec.sections:
                        if glob_match(pat, sec.name) and not any(file_match(p, sec.obj.name) for p in excl):
                            found.append(sec)
                            claimed.add(id(sec))
                            break
                if spec.sort == "name":
                    found.sort(key=lambda s: s.name)
                elif spec.sort == "alignment":
                    found.sort(key=lambda s: -s.align)
                o.matched[id(spec)] = found
                for sec in found:
                    if o.spec.name == "/DISCARD/":
                        sec.discarded, sec.live = True, False
                    else:
                        sec.out = o
                        sec.keep = sec.keep or spec.keep
        # orphans: sections no statement wanted
        orphans = [s for s in inputs if id(s) not in claimed]
        for sec in orphans:
            self.place_orphan(sec)

    def out_class(self, o):
        """Kind of an output section for orphan placement: ('code'|'ro'|'data'|'bss'|'other')."""
        kinds = {self.sec_kind(s) for lst in o.matched.values() for s in lst if not s.discarded}
        if o.name == ".text":
            return "code"
        for k in ("code", "data", "ro", "bss"):
            if k in kinds:
                return k
        return "other"

    @staticmethod
    def sec_kind(sec):
        if not sec.alloc:
            return "other"
        if sec.nobits:
            return "bss"
        if sec.flags & SHF_EXEC:
            return "code"
        if sec.flags & SHF_WRITE:
            return "data"
        return "ro"

    def place_orphan(self, sec):
        """An input section no script statement mentions gets an output section of its own name, placed after the
        last output section of its kind (else after the last loaded one; a bss-like one after the last allocated)."""
        name = sec.name
        for o in self.outs:
            if o.spec.name == name and getattr(o, "orphan", False):
                break
        else:
            spec = S.OutSec(name)
            spec.stmts = [S.InputSpec([None], [], [(name, [])])]
            o = OutSection(name, spec)
            o.orphan = True
            o.matched[id(spec.stmts[0])] = []
            kind = self.sec_kind(sec)
            idx = len(self.outs)
            if kind != "other":
                kinds = [self.out_class(x) for x in self.outs]
                same = [k for k, c in enumerate(kinds) if c == kind and self.outs[k].spec.name != "/DISCARD/"]
                if same:
                    idx = same[-1] + 1
                else:
                    loaded = [k for k, c in enumerate(kinds) if c in ("code", "ro", "data")
                              and self.outs[k].spec.name != "/DISCARD/"]
                    anyalloc = [k for k, c in enumerate(kinds) if c != "other" and self.outs[k].spec.name != "/DISCARD/"]
                    pick = loaded if kind != "bss" else anyalloc
                    if pick:
                        idx = pick[-1] + 1
            nxt = self.outs[idx].spec if idx < len(self.outs) else None
            self.outs.insert(idx, o)
            at = self.script.sections.index(nxt) if nxt is not None else len(self.script.sections)
            self.script.sections.insert(at, spec)
        o.matched[id(o.spec.stmts[0])].append(sec)
        sec.out = o

    # ======================================================================================================
    # 3. garbage collection
    # ======================================================================================================
    def sym_section(self, obj, sym):
        """The InSec a symbol of `obj` is defined in, or None."""
        if sym.shndx in (elf.SHN_UNDEF, elf.SHN_ABS, elf.SHN_COMMON) or sym.shndx >= 0xFF00:
            return None
        return obj.sections.get(sym.shndx)

    def resolve_sym(self, obj, idx):
        """For a relocation: (section or None, value in section or absolute value, global or None, defined?)"""
        sym = obj.symbols[idx]
        if sym.bind == elf.STB_LOCAL:
            if sym.shndx == elf.SHN_ABS:
                return None, sym.value, None, True
            return sym.sec, sym.value, None, sym.sec is not None
        g = sym.g or self.globals.get(sym.name)
        return self.global_def(g)

    def global_def(self, g):
        if g.kind == "def":
            sym = g.sym
            if sym.shndx == elf.SHN_ABS:
                return None, sym.value, g, True
            return sym.sec, sym.value, g, True
        if g.kind == "common":
            return g.defsym_sec, g.defsym_off, g, True
        if g.kind == "script":
            return None, 0, g, True
        return None, 0, g, False

    def gc(self):
        roots = []
        entry = self.o.entry or self.script.entry
        todo = []
        live = set()

        def mark(sec):
            if sec is not None and id(sec) not in live and not sec.discarded:
                live.add(id(sec))
                todo.append(sec)

        g = self.globals.get(entry) if entry else None
        if g is not None:
            mark(self.global_def(g)[0])
        for name in list(self.o.undefined) + list(self.script.extern):
            if name in self.globals:
                mark(self.global_def(self.globals[name])[0])
        for sec in self.all_inputs():
            if sec.keep or not sec.alloc or sec.type in (SHT_INIT_ARRAY, SHT_FINI_ARRAY, SHT_PREINIT_ARRAY):
                mark(sec)
        for name in list(self.o.undefined) + list(self.script.extern) + ([entry] if entry else []):
            if name in self.globals:
                self.globals[name].live_ref = True
        while todo:
            sec = todo.pop()
            for _, _, idx, _ in sec.relocs:
                sym = sec.obj.symbols[idx]
                if sym.bind != elf.STB_LOCAL:
                    (sym.g or self.globals[sym.name]).live_ref = True
                tsec = self.resolve_sym(sec.obj, idx)[0]
                mark(tsec)
        for sec in self.all_inputs():
            if id(sec) not in live and not sec.discarded:
                sec.live = False
                if self.o.print_gc:
                    self.warn(f"removing unused section '{sec.name}' in file '{sec.obj.name}'")

    # ======================================================================================================
    # 4. mergeable sections (strings and constants)
    # ======================================================================================================
    def merge_sections(self):
        for o in self.outs:
            groups = {}
            for sec in self.placed_inputs(o):
                if sec.flags & SHF_MERGE and sec.entsize > 0 and not sec.nobits and sec.alloc is not None:
                    key = (sec.flags & (SHF_MERGE | SHF_STRINGS | SHF_ALLOC | SHF_WRITE | SHF_EXEC), sec.entsize, sec.align)
                    groups.setdefault(key, []).append(sec)
            for (flags, entsize, _), secs in groups.items():
                self.merge_group(secs, entsize, bool(flags & SHF_STRINGS))

    def placed_inputs(self, o):
        seen = []
        for spec in o.spec.stmts:
            if isinstance(spec, S.InputSpec):
                seen += [s for s in o.matched.get(id(spec), []) if s.live and not s.discarded]
        return seen

    def merge_group(self, secs, es, strings):
        entries = []                      # (sec, old offset, bytes)
        for sec in secs:
            d = bytes(sec.data)
            if len(d) % es:
                return                    # not a whole number of entries: leave the group alone
            if strings:
                pos = 0
                while pos < len(d):
                    end = pos
                    while end < len(d) and d[end:end + es] != bytes(es):
                        end += es
                    if end >= len(d):
                        return            # an unterminated string: leave the group alone
                    entries.append((sec, pos, d[pos:end + es]))
                    pos = end + es
            else:
                for pos in range(0, len(d), es):
                    entries.append((sec, pos, d[pos:pos + es]))
        first = {}                        # content -> index of first entry
        for k, (_, _, b) in enumerate(entries):
            first.setdefault(b, k)
        # tail merging: a string that ends the next string in reversed-spelling order is stored inside it
        tail = {}                         # content -> (longer content, shift)
        if strings:
            def units(b):
                return [b[k:k + es] for k in range(0, len(b), es)]
            uniq = sorted(first, key=lambda b: units(b)[::-1])
            for a, b in zip(uniq, uniq[1:]):
                if len(b) > len(a) and b.endswith(a):
                    tail[a] = (b, len(b) - len(a))
        # surviving entries in original order, per section
        newoff = {sec: 0 for sec in secs}
        pieces = {sec: bytearray() for sec in secs}
        where = {}                        # content -> (holder, offset)
        for k, (sec, pos, b) in enumerate(entries):
            if first[b] != k or b in tail:
                continue
            where[b] = (sec, len(pieces[sec]))
            pieces[sec] += b
        for b, (big, cut) in tail.items():
            root = big
            shift = cut
            while root in tail:
                nxt = tail[root]
                shift += nxt[1]
                root = nxt[0]
            holder, off = where[root]
            where[b] = (holder, off + shift)
        maps = {sec: [] for sec in secs}
        for sec, pos, b in entries:
            holder, off = where[b]
            maps[sec].append((pos, len(b), holder, off))
        for sec in secs:
            sec.data = pieces[sec]
            sec.size = len(pieces[sec])
        for sec in secs:
            sec.mergemap = maps[sec]
        self._merge_orig = getattr(self, "_merge_orig", {})

    def map_merge(self, sec, off):
        """(holder section, offset in it) for an offset in a section that was merged."""
        m = sec.mergemap
        lo, hi = 0, len(m) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            pos, ln, holder, new = m[mid]
            if off < pos:
                hi = mid - 1
            elif off >= pos + ln:
                lo = mid + 1
            else:
                return holder, new + off - pos
        return sec, off

    # ======================================================================================================
    # 5. addresses of symbols
    # ======================================================================================================
    def sec_addr(self, sec, off):
        """Output address of `off` bytes into input section `sec`."""
        if sec.mergemap is not None:
            sec, off = self.map_merge(sec, off)
        return sec.out.vma + sec.offset + off

    def gaddr(self, g):
        """(value, output section or None) of a global symbol, as laid out so far."""
        if g.kind == "script":
            return g.script
        sec, val, _, ok = self.global_def(g)
        if not ok:
            return (0, None)
        if sec is None:
            return (val, None)
        if sec.out is None or sec.discarded:
            return (0, None)
        return (self.sec_addr(sec, val), sec.out)

    def laddr(self, sec, val):
        return self.sec_addr(sec, val), sec.out

    # ======================================================================================================
    # 6. the script: expressions and layout
    # ======================================================================================================
    def ev(self, e, st):
        t = e[0]
        if t == "num":
            return Val(e[1])
        if t == "dot":
            return Val(st.dot, st.sec or st.last)
        if t == "name":
            return self.ev_name(e[1], st)
        if t == "un":
            a = self.ev(e[2], st)
            op = e[1]
            if op == "-":
                return Val(-a.v)
            if op == "+":
                return a
            if op == "~":
                return Val(~a.v)
            return Val(0 if a.v else 1)
        if t == "cond":
            return self.ev(e[2], st) if self.ev(e[1], st).v else self.ev(e[3], st)
        if t == "bin":
            return self.ev_bin(e, st)
        if t == "call":
            return self.ev_call(e, st)
        raise LinkError(f"bad expression {e!r}")

    def ev_bin(self, e, st):
        op = e[1]
        if op == "&&":
            return Val(1 if self.ev(e[2], st).v and self.ev(e[3], st).v else 0)
        if op == "||":
            return Val(1 if self.ev(e[2], st).v or self.ev(e[3], st).v else 0)
        a, b = self.ev(e[2], st), self.ev(e[3], st)
        x, y = a.v, b.v
        sec = None
        if op == "+":
            r = x + y
            sec = a.sec if b.sec is None else b.sec if a.sec is None else None
        elif op == "-":
            r = x - y
            sec = a.sec if b.sec is None else None
        elif op == "*":
            r = x * y
        elif op in ("/", "%"):
            if y == 0:
                raise LinkError("division by zero in a linker script expression")
            r = x // y if op == "/" else x % y
        elif op == "<<":
            r = x << y if y < 64 else 0
        elif op == ">>":
            r = x >> y if y < 64 else 0
        elif op == "&":
            r = x & y
            sec = a.sec if b.sec is None and False else None
        elif op == "|":
            r = x | y
        elif op == "^":
            r = x ^ y
        elif op == "==":
            r = int(x == y)
        elif op == "!=":
            r = int(x != y)
        elif op == "<":
            r = int(x < y)
        elif op == ">":
            r = int(x > y)
        elif op == "<=":
            r = int(x <= y)
        elif op == ">=":
            r = int(x >= y)
        else:
            raise LinkError(f"bad operator {op}")
        return Val(r, sec)

    def find_out(self, name):
        o = self.outs_by_name.get(name)
        if o is None:
            raise LinkError(f"undefined section `{name}' referenced in expression")
        return o

    def ev_call(self, e, st):
        f, args = e[1], e[2]
        if f == "ABSOLUTE":
            return Val(self.ev(args[0], st).v)
        if f in ("ADDR", "LOADADDR", "SIZEOF", "ALIGNOF"):
            o = self.find_out(args[0][1])
            return Val({"ADDR": o.vma, "LOADADDR": o.lma, "SIZEOF": o.size, "ALIGNOF": o.align}[f])
        if f in ("ALIGN", "BLOCK", "NEXT"):
            if len(args) == 1:
                a = self.ev(args[0], st).v
                return Val(align_up(st.dot, a), st.sec or st.last)
            x, a = self.ev(args[0], st), self.ev(args[1], st).v
            return Val(align_up(x.v, a), x.sec)
        if f == "DEFINED":
            n = args[0][1]
            g = self.globals.get(n)
            return Val(1 if (n in self.defined_now or (g is not None and g.kind in ("def", "common"))) else 0)
        if f in ("ORIGIN", "ORG", "LENGTH", "LEN"):
            r = self.regions.get(args[0][1])
            if r is None:
                raise LinkError(f"undefined memory region `{args[0][1]}' referenced in expression")
            return Val(r.origin if f in ("ORIGIN", "ORG") else r.length)
        if f == "MAX":
            return Val(max(self.ev(a, st).v for a in args))
        if f == "MIN":
            return Val(min(self.ev(a, st).v for a in args))
        if f == "LOG2CEIL":
            x = self.ev(args[0], st).v
            return Val(0 if x <= 1 else (x - 1).bit_length())
        if f == "SEGMENT_START":
            return self.ev(args[1], st)
        if f == "SIZEOF_HEADERS":
            return Val(self.hdr_size)
        if f == "CONSTANT":
            return Val(PAGE)
        if f == "DATA_SEGMENT_ALIGN":
            m = self.ev(args[0], st).v
            return Val(align_up(st.dot, m) + (st.dot & (m - 1)), st.sec or st.last)
        if f in ("DATA_SEGMENT_END", "DATA_SEGMENT_RELRO_END"):
            return self.ev(args[-1], st)
        if f == "ASSERT":
            if not self.ev(args[0], st).v:
                self.error(f"ld: {args[1][1] if len(args) > 1 and args[1][0] == 'name' else 'assertion failed'}")
            return Val(1)
        raise LinkError(f"unsupported function {f}")

    def ev_name(self, name, st):
        g = self.globals.get(name)
        if g is not None and self.in_top:
            g.top_ref = True
        if g is None:
            self.undef_expr.add(name)
            return Val(0)
        if g.kind in ("undef",):
            self.undef_expr.add(name)
            return Val(0)
        v, sec = self.gaddr(g)
        return Val(v, sec)

    # -- assignments
    def assign(self, a, st):
        name = a.name
        if name == ".":
            val = self.ev(a.expr, st)
            if a.op != "=":
                cur = Val(st.dot, st.sec or st.last)
                val = self.compound(a.op, cur, val)
            if st.sec is not None and val.sec is None:
                new = st.sec.vma + val.v          # inside a section an absolute value is an offset from its start
            else:
                new = val.v
            if new < st.dot and st.sec is not None:
                self.error(f"ld: cannot move location counter backwards (from {st.dot:#x} to {new:#x})")
                return
            if st.sec is None and st.dot_set and new < st.dot and False:
                pass
            st.dot = new & MASK64
            st.dot_set = True
            return
        g = self.globals.get(name)
        if a.provide:
            if g is None or not g.refs and name not in self.referenced_by_script:
                return
            if g.kind in ("def", "common") or (g.kind == "script" and name in self.defined_now):
                return
            if g.kind == "script" and False:
                return
        val = self.ev(a.expr, st)
        if a.op != "=":
            cur = self.gaddr(g) if g is not None and g.kind != "undef" else (0, None)
            val = self.compound(a.op, Val(cur[0], cur[1]), val)
        if g is None:
            g = self.gsym(name)
        sec = val.sec
        if sec is None and False:
            pass
        g.kind, g.script, g.hidden = "script", (val.v, sec), a.hidden
        g.in_sec = st.sec is not None
        g.sym = None
        self.defined_now.add(name)
        self.script_defined.add(name)

    def compound(self, op, cur, val):
        base = op[:-1]
        return self.ev_bin(("bin", base, ("num", cur.v), ("num", val.v)), None) if cur.sec is None and val.sec is None \
            else Val({"+": cur.v + val.v, "-": cur.v - val.v}.get(base, self.ev_bin(
                ("bin", base, ("num", cur.v), ("num", val.v)), None).v), cur.sec)

    # -- layout of one pass
    class State:
        def __init__(self):
            self.dot = 0
            self.sec = None          # output section being laid out
            self.last = None         # last output section laid out
            self.dot_set = False

    def default_region(self, o):
        flags = 0
        for sec in self.placed_inputs(o):
            flags |= sec.flags
        for r in self.script.regions:
            attrs = r.attrs.lower().replace("!", "")
            neg = r.attrs.split("!")[1:] if "!" in r.attrs else []
            ok = True
            if "w" in "".join(neg).lower() and flags & SHF_WRITE:
                ok = False
            if "x" in "".join(neg).lower() and flags & SHF_EXEC:
                ok = False
            if ok:
                return self.regions[r.name]
        return self.regions[self.script.regions[0].name] if self.script.regions else None

    def layout_pass(self):
        self.pass_no += 1
        st = Linker.State()
        self.defined_now = set()
        self.undef_expr = set()
        self.in_top = True
        for r in self.script.regions:
            reg = self.regions[r.name]
            reg.origin = self.ev(r.origin, st).v
            reg.length = self.ev(r.length, st).v
            reg.current = reg.origin
        self.region_lma = {}
        self.asserts = []
        for a in self.script.top:
            if isinstance(a, S.Assign):
                self.assign(a, st)
            else:
                self.asserts.append(a)
        for stmt in self.script.sections:
            if isinstance(stmt, S.Assign):
                self.assign(stmt, st)
            elif isinstance(stmt, S.AssertStmt):
                self.asserts.append(stmt)
            elif isinstance(stmt, tuple):
                pass
            else:
                o = self.outs_by_spec[id(stmt)]
                if stmt.name == "/DISCARD/":
                    continue
                self.in_top = False
                self.place_section(o, st)
                self.in_top = True
        for a in self.asserts:
            if not self.ev(a.expr, st).v:
                self.error(f"ld: {a.message}")

    def place_section(self, o, st):
        spec = o.spec
        ins = self.placed_inputs(o)
        o.inputs = ins
        al = 1
        for sec in ins:
            al = max(al, sec.align)
        if spec.align is not None:
            al = max(al, self.ev(spec.align, st).v)
        o.align = al
        na = bool(ins) and not any(sec.alloc for sec in ins)      # e.g. .comment: no address, no memory
        saved_dot = st.dot
        region = self.regions.get(spec.region) if spec.region and not na else None
        if spec.region and region is None and not na:
            raise LinkError(f"{spec.name}: region `{spec.region}' undefined")
        if na:
            dot = 0
        elif spec.addr is not None:
            dot = self.ev(spec.addr, st).v
        elif region is not None:
            dot = region.current
        elif self.regions:
            region = self.default_region(o)
            dot = region.current
        else:
            dot = st.dot
        dot = align_up(dot, al)
        o.region = region
        o.vma = dot
        # load address
        lma_region = self.regions.get(spec.lma_region) if spec.lma_region else None
        if spec.lma_region and lma_region is None:
            raise LinkError(f"{spec.name}: region `{spec.lma_region}' undefined")
        if spec.at is not None:
            o.lma = self.ev(spec.at, st).v
        elif lma_region is not None:
            o.lma = lma_region.current
        elif region is not None and id(region) in self.region_lma:
            o.lma = self.region_lma[id(region)].current
        else:
            o.lma = o.vma
        o.lma_region = lma_region or (self.region_lma.get(id(region)) if spec.at is None else None)
        st.dot, st.sec = dot, o
        o.pieces, o.gaps, o.fill = [], [], b"\0"
        fill_expr = spec.fill
        if fill_expr is not None:
            o.fill = self.fill_bytes(self.ev(fill_expr, st).v)
        for item in spec.stmts:
            if isinstance(item, S.InputSpec):
                for sec in o.matched.get(id(item), []):
                    if not sec.live or sec.discarded:
                        continue
                    start = align_up(st.dot, sec.align)
                    if start > st.dot:
                        o.gaps.append((st.dot - o.vma, start - o.vma))
                    sec.offset = start - o.vma
                    st.dot = start + sec.size
            elif isinstance(item, S.Assign):
                before = st.dot
                self.assign(item, st)
                if item.name == "." and st.dot > before:
                    o.gaps.append((before - o.vma, st.dot - o.vma))
            elif isinstance(item, S.DataStmt):
                n = {"BYTE": 1, "SHORT": 2, "LONG": 4, "QUAD": 8, "SQUAD": 8}[item.kind]
                v = self.ev(item.expr, st).v
                o.pieces.append((st.dot - o.vma, (v & ((1 << (8 * n)) - 1)).to_bytes(n, "little")))
                st.dot += n
            elif isinstance(item, S.FillStmt):
                o.fill = self.fill_bytes(self.ev(item.expr, st).v)
            elif isinstance(item, S.AssertStmt):
                self.asserts.append(item)
        o.size = st.dot - o.vma
        st.sec = None
        if not na:
            st.last = o
        # section properties
        has_data = any(not s.nobits and s.size for s in ins) or bool(o.pieces)
        o.nobits = o.noload or not has_data
        flags = 0
        types = set()
        for sec in ins:
            flags |= sec.flags & (SHF_ALLOC | SHF_WRITE | SHF_EXEC)
            types.add(sec.type)
        if not ins:
            # no inputs: a section only moved the location counter (or defined symbols)
            if o.size > 0:
                flags = SHF_ALLOC | SHF_WRITE
            else:
                flags = SHF_WRITE
        o.alloc = bool(flags & SHF_ALLOC)
        if o.name == ".text":                 # the one section name with fixed properties: AX, aligned to 2 at least
            flags = (flags | SHF_ALLOC | SHF_EXEC) & ~SHF_WRITE
            o.align = max(o.align, 2)
            o.alloc = True
        o.flags = flags
        if o.alloc and o.nobits:
            o.type = SHT_NOBITS
        else:
            rest = types - {SHT_NOBITS}
            o.type = next(iter(rest)) if len(rest) == 1 else SHT_PROGBITS
        o.emit = o.size > 0 or (not ins and o.has_syms)
        if na:
            st.dot = saved_dot
        # advance memory regions
        if o.alloc and o.size:
            if region is not None:
                region.current = st.dot
                if region.current > region.origin + region.length:
                    self.error(f"ld: region `{region.name}' overflowed by {region.current - region.origin - region.length} bytes")
            target = lma_region
            if target is not None and not o.noload:
                target.current = o.lma + o.size
                if target.current > target.origin + target.length:
                    self.error(f"ld: region `{target.name}' overflowed by {target.current - target.origin - target.length} bytes")
            if lma_region is not None and region is not None:
                self.region_lma[id(region)] = lma_region
        elif lma_region is not None and region is not None:
            self.region_lma[id(region)] = lma_region
        st.dot = st.dot if o.alloc else st.dot

    @staticmethod
    def fill_bytes(v):
        return (v & 0xFFFFFFFF).to_bytes(4, "big")

    def layout(self):
        self.outs_by_spec = {id(o.spec): o for o in self.outs}
        self.outs_by_name = {}
        for o in self.outs:
            self.outs_by_name.setdefault(o.spec.name, o)
        self.referenced_by_script = set()
        for pass_ in range(6):
            n_err = len(self.errors)
            snapshot = self.snapshot()
            self.layout_pass()
            if pass_ > 0 and snapshot == self.snapshot():
                break
            del self.errors[n_err:]
        # a final pass produces the real diagnostics
        n_err = len(self.errors)
        self.layout_pass()
        for name in sorted(self.undef_expr):
            self.error(f"ld: undefined symbol `{name}' referenced in expression")

    def snapshot(self):
        return ([(o.vma, o.lma, o.size) for o in self.outs],
                {n: g.script for n, g in self.globals.items() if g.kind == "script"})

    # ======================================================================================================
    # 7. symbol resolution results
    # ======================================================================================================
    def check_undefined(self):
        for obj in self.objs:
            for sec in obj.sections.values():
                if not sec.live or sec.discarded or sec.out is None:
                    continue
                seen = set()
                for off, typ, idx, add in sec.relocs:
                    sym = obj.symbols[idx]
                    if sym.bind != elf.STB_LOCAL and sym.shndx == elf.SHN_UNDEF:
                        g = sym.g
                        if g.kind == "undef" and not (sym.bind == elf.STB_WEAK) and (g.name, ) not in seen:
                            seen.add((g.name,))
                            self.error(f"{obj.name}:({sec.name}+{off:#x}): undefined reference to `{g.name}'")

    # ======================================================================================================
    # 8. relocation
    # ======================================================================================================
    RELOC_NAMES = elf.RELOCS

    def reloc_name(self, typ):
        return {9: "R_PI32V2_GOT", 10: "R_PI32V2_GOTFUNCDESC", 12: "R_PI32V2_FUNCDESCVALUE", 13: "R_PI32V2_REL32",
                14: "R_PI32V2_MOV_ABS16", 15: "R_PI32V2_GOT16", 16: "R_PI32V2_GOTFUNCDESC16"}.get(typ) or \
            elf.RELOCS.get(typ, f"R_PI32V2_{typ}")

    def apply_relocs(self):
        for o in self.outs:
            if not o.emit or o.spec.name == "/DISCARD/":
                continue
            for sec in o.inputs:
                if sec.nobits:
                    continue
                for off, typ, idx, add in sec.relocs:
                    self.apply_one(o, sec, off, typ, idx, add)

    def apply_one(self, o, sec, off, typ, idx, add):
        obj = sec.obj
        sym = obj.symbols[idx]
        bsec, val, g, defined = self.resolve_sym(obj, idx)
        if typ == 0:
            return
        if typ > RELOC_MAX:
            raise LinkError(f"{obj.name}: BFD (GNU Binutils) 2.26.51: unsupported relocation type {typ}")
        if not defined:
            if g is not None and g.kind == "undef" and sym.bind == elf.STB_WEAK:
                S_ = 0
            elif g is not None and g.kind == "undef" and g.weakref:
                S_ = 0
            else:
                return                           # reported by check_undefined
        elif g is not None and g.kind == "script":
            S_ = g.script[0]
        elif bsec is None:
            S_ = val
        else:
            if bsec.discarded or bsec.out is None or not bsec.live:
                self.error(f"{obj.name}:({sec.name}+{off:#x}): relocation against `{sym.name}' in a discarded section")
                return
            S_ = self.sec_addr(bsec, val)
        S_ &= 0xFFFFFFFFFFFFFFFF
        pos = sec.offset + off
        P = o.vma + pos
        d = o.data
        name = sym.name if sym.bind != elf.STB_LOCAL else (sym.name or bsec.name if bsec else sym.name)
        A = add

        def fail(kind="trunc"):
            where = f"{obj.name}:({sec.name}+{off:#x})"
            if kind == "unaligned":
                self.error("ld: relocation unaligned")
            self.error(f"{where}: relocation truncated to fit: {self.reloc_name(typ)} against symbol `{name}'")

        if typ in (1, 2, 3, 4):
            end = P + (6 if typ in (3, 4) else 4)
            offset = s32(S_ + A - end)
            if offset & 1:
                fail("unaligned")
                return
            v = offset >> 1
            if typ == 1:
                if not -(1 << 15) <= v < (1 << 15):
                    return fail()
                d[pos + 2:pos + 4] = (v & 0xFFFF).to_bytes(2, "little")
            elif typ == 2:
                if not -(1 << 21) <= v < (1 << 21):
                    return fail()
                d[pos] = (d[pos] & 0xC0) | ((v >> 16) & 0x3F)
                d[pos + 2:pos + 4] = (v & 0xFFFF).to_bytes(2, "little")
            elif typ == 3:
                if not -(1 << 15) <= v < (1 << 15):
                    return fail()
                d[pos + 4:pos + 6] = (v & 0xFFFF).to_bytes(2, "little")
            else:
                w1 = d[pos + 2] | d[pos + 3] << 8
                w1 = (w1 & 1) | ((v & 0x7FFF) << 1)
                d[pos + 2:pos + 4] = w1.to_bytes(2, "little")
                d[pos + 4:pos + 6] = ((v >> 15) & 0xFFFF).to_bytes(2, "little")
        elif typ in (5, 9, 10):
            v = (S_ + A) & 0xFFFFFFFF
            d[pos + 2:pos + 4] = (v & 0xFFFF).to_bytes(2, "little")
            d[pos + 4:pos + 6] = (v >> 16).to_bytes(2, "little")
        elif typ in (14, 15, 16):
            v = s32(S_ + A)
            if not -(1 << 15) <= v < (1 << 15):
                return fail()
            d[pos + 2:pos + 4] = (v & 0xFFFF).to_bytes(2, "little")
        elif typ in (6, 7):
            n = typ - 5
            bits = 8 * n
            ip = int.from_bytes(d[pos:pos + n], "little")
            ip = ip - (1 << bits) if ip >> (bits - 1) else ip
            r = s32(S_ + A)
            if not -(1 << bits) <= r < (1 << bits) or not -(1 << bits) <= r + ip < (1 << bits):
                return fail()
            d[pos:pos + n] = ((r + ip) & ((1 << bits) - 1)).to_bytes(n, "little")
        elif typ == 8:
            ip = int.from_bytes(d[pos:pos + 4], "little")
            d[pos:pos + 4] = ((ip + S_ + A) & 0xFFFFFFFF).to_bytes(4, "little")
        elif typ in (11, 12, 13):
            ip = s32(int.from_bytes(d[pos:pos + 4], "little"))
            r = s32(S_ + A)
            if not -(1 << 31) <= r + ip < (1 << 31):
                return fail()
            d[pos:pos + 4] = ((r + ip) & 0xFFFFFFFF).to_bytes(4, "little")

    # ======================================================================================================
    # 9. building the output
    # ======================================================================================================
    def build_data(self):
        for o in self.outs:
            if not o.emit or o.spec.name == "/DISCARD/":
                continue
            if o.nobits and o.alloc:
                o.data = bytearray()
                continue
            buf = bytearray(o.size)
            if o.fill != b"\0":
                pat = o.fill
                for s, e in o.gaps:
                    for k in range(s, e):
                        buf[k] = pat[(k - s) % len(pat)]
            for sec in o.inputs:
                if not sec.nobits and sec.size:
                    buf[sec.offset:sec.offset + sec.size] = sec.data
            for off, b in o.pieces:
                buf[off:off + len(b)] = b
            o.data = buf

    def segments(self):
        """Program headers and file offsets of the alloc sections, laid out the way JieLi's ld does."""
        alloc = [o for o in self.emitted if o.alloc]
        order = sorted(alloc, key=lambda o: o.lma)         # stable: script order for equal addresses
        segs = []
        for o in order:
            cur = segs[-1] if segs else None
            if cur is not None:
                last = cur[-1]
                same_delta = (o.vma - o.lma) & 0xFFFFFFFF == (last.vma - last.lma) & 0xFFFFFFFF
                if not same_delta or (last.nobits is False and o.nobits is False and False):
                    cur = None
                elif not o.nobits and last.nobits:
                    cur = None
                elif self.page(last.lma + last.size - 1) != self.page(o.lma):
                    cur = None
            if cur is None:
                segs.append([o])
            else:
                cur.append(o)
        return segs

    @staticmethod
    def page(a):
        # JieLi's ld masks addresses with ~(PAGE - 1) although 0x500 is not a power of two; so does this
        return a & ~(PAGE - 1)

    def assign_offsets(self, segs):
        n = len(segs)
        self.nphdr = n
        self.hdr_size = 52 + 32 * n
        pos = self.hdr_size
        phdrs = []
        for k, seg in enumerate(segs):
            first = seg[0]
            off = pos + ((first.vma - pos) % PAGE)
            include_hdr = k == 0 and off < PAGE
            first.offset = off
            cur_end = off
            last = first
            for o in seg:
                if o is not first:
                    if o.nobits:
                        o.offset = cur_end
                    else:
                        o.offset = last.offset + (o.vma - last.vma)
                if not o.nobits:
                    cur_end = o.offset + o.size
                last = o
            end_file = max([o.offset + o.size for o in seg if not o.nobits] or [first.offset])
            p_off = 0 if include_hdr else first.offset
            delta = first.offset - p_off
            filesz = (end_file - p_off) if any(not o.nobits for o in seg) else (self.hdr_size if include_hdr else 0)
            memsz = (seg[-1].vma + seg[-1].size) - first.vma + delta
            flags = 4
            for o in seg:
                if o.flags & SHF_WRITE:
                    flags |= 2
                if o.flags & SHF_EXEC:
                    flags |= 1
            phdrs.append((PT_LOAD, p_off, first.vma - delta, first.lma - delta, filesz, memsz, flags, PAGE))
            pos = max(pos, end_file) if any(not o.nobits for o in seg) else pos
        self.phdrs = phdrs
        return pos

    # -- symbol table
    def keep_local(self, obj, sym):
        if sym.type == elf.STT_SECTION:
            return False
        if sym.type == elf.STT_FILE:
            return True
        sec = sym.sec
        if sym.shndx in (elf.SHN_ABS,):
            return True
        if sec is None or (sec.flags & SHF_MERGE and sym.name.startswith(".L")):
            return False     # temporary labels in mergeable sections are dropped (ld's default discards just those)
        return sec.live and not sec.discarded and sec.out is not None and sec.out.emit

    def build_symtab(self):
        """(.symtab bytes, .strtab bytes, number of local symbols including the null one)."""
        ents = []           # (name, value, size, info, other, shndx)
        index_of = {o: i + 1 for i, o in enumerate(self.emitted)}
        for o in self.emitted:
            ents.append(("", o.vma, 0, (elf.STB_LOCAL << 4) | elf.STT_SECTION, 0, index_of[o]))
        # files in the order of their first contribution to the output
        order, seen = [], set()
        for o in self.outs:
            if not o.emit or o.spec.name == "/DISCARD/":
                continue
            for sec in o.inputs:
                if id(sec.obj) not in seen and sec.obj in self.objs:
                    seen.add(id(sec.obj))
                    order.append(sec.obj)
        for obj in self.objs:
            if id(obj) not in seen:
                order.append(obj)
        for obj in order:
            locs = [sym for sym in obj.symbols[1:] if sym.bind == elf.STB_LOCAL and self.keep_local(obj, sym)]
            has_file = any(sym.type == elf.STT_FILE for sym in locs)
            contributes = any(sec.live and not sec.discarded and sec.out is not None for sec in obj.sections.values())
            if not (any(sym.type != elf.STT_FILE for sym in locs) or (has_file and contributes)):
                continue                 # nothing of the file survives
            if not has_file:
                ents.append((obj.name, 0, 0, (elf.STB_LOCAL << 4) | elf.STT_FILE, 0, elf.SHN_ABS))
            for sym in locs:
                if sym.type == elf.STT_FILE:
                    ents.append((sym.name, 0, 0, (elf.STB_LOCAL << 4) | elf.STT_FILE, 0, elf.SHN_ABS))
                elif sym.shndx == elf.SHN_ABS:
                    ents.append((sym.name, sym.value, sym.size, (elf.STB_LOCAL << 4) | sym.type, sym.other, elf.SHN_ABS))
                else:
                    value, out = self.laddr(sym.sec, sym.value)
                    ents.append((sym.name, value, sym.size, (elf.STB_LOCAL << 4) | sym.type, sym.other, index_of[out]))
        gl = [g for g in self.globals.values() if self.emit_global(g)]
        gl.sort(key=lambda g: (hash_name(g.name) % HASH_SIZE, -g.order))
        # with --gc-sections a symbol the script defines inside an output section and only the script (or dead
        # code) refers to is written as a local symbol
        loc = [g for g in gl if self.o.gc and g.kind == "script" and g.in_sec and not g.live_ref and (g.top_ref or g.refs)]
        gl = loc + [g for g in gl if g not in loc]
        if loc:                          # they follow a file symbol with no name (the script's own "file")
            ents.append(("", 0, 0, (elf.STB_LOCAL << 4) | elf.STT_FILE, 0, elf.SHN_ABS))
        nlocal = len(ents) + len(loc) + 1
        for g in gl:
            value, out = self.gaddr(g)
            if g.kind == "def":
                sym = g.sym
                typ, size, other, bind = sym.type, sym.size, sym.other, sym.bind
                shndx = elf.SHN_ABS if (out is None or sym.shndx == elf.SHN_ABS) else index_of[out]
            elif g.kind == "common":
                typ, size, other, bind, shndx = elf.STT_OBJECT, g.common_size, 0, elf.STB_GLOBAL, index_of[out]
            elif g.kind == "script":
                typ, size, other, bind = elf.STT_NOTYPE, 0, 2 if g.hidden else 0, elf.STB_GLOBAL
                shndx = index_of.get(out, elf.SHN_ABS) if out is not None else elf.SHN_ABS
            else:       # undefined weak
                typ, size, other, bind, shndx, value = elf.STT_NOTYPE, 0, 0, elf.STB_WEAK, 0, 0
            if g in loc:
                bind = elf.STB_LOCAL
            ents.append((g.name, value, size, (bind << 4) | typ, other, shndx))
        strtab, off = string_table([e[0] for e in ents])
        data = bytearray(16)
        for name, value, size, info, other, shndx in ents:
            data += struct.pack("<IIIBBH", off[name], value & 0xFFFFFFFF, size, info, other, shndx)
        return bytes(data), strtab, nlocal

    def emit_global(self, g):
        if g.kind == "def":
            sec = g.sym.sec
            if g.sym.shndx == elf.SHN_ABS:
                return True
            return sec is not None and sec.live and not sec.discarded and sec.out is not None and sec.out.emit
        if g.kind == "common":
            return g.defsym_sec is not None
        if g.kind == "script":
            return not g.hidden or True
        return g.kind == "undef" and g.refs and g.weakref and False

    def set_entry(self):
        name = self.o.entry or self.script.entry or "_start"
        self.entry_name = name
        try:
            self.entry_value = int(name, 0)
            return
        except ValueError:
            pass
        g = self.globals.get(name)
        if g is not None and g.kind != "undef":
            self.entry_value = self.gaddr(g)[0] & 0xFFFFFFFF
        else:
            first = next((o for o in self.emitted if o.flags & SHF_EXEC), None) or (self.emitted[0] if self.emitted else None)
            self.entry_value = first.vma if first else 0
            self.warn(f"ld: warning: cannot find entry symbol {name}; defaulting to {self.entry_value:08x}")

    def write(self):
        self.emitted = [o for o in self.outs if o.emit and o.spec.name != "/DISCARD/"]
        for k, o in enumerate(self.emitted):
            o.index = k + 1
        segs = self.segments()
        pos = self.assign_offsets(segs)
        # non-alloc sections follow the loaded contents
        for o in self.emitted:
            if not o.alloc:
                pos = align_up(pos, o.align)
                o.offset = pos
                pos += o.size
        symdata, strtab, nlocal = self.build_symtab()
        shstr, shname = string_table([".symtab", ".strtab", ".shstrtab"] + [o.name for o in self.emitted])
        nsec = len(self.emitted) + 4
        sym_off = align_up(pos, 4)
        str_off = sym_off + len(symdata)
        shstr_off = str_off + len(strtab)
        shoff = align_up(shstr_off + len(shstr), 4)
        out = bytearray(shoff + 40 * nsec)
        for o in self.emitted:
            if not o.nobits or not o.alloc:
                out[o.offset:o.offset + o.size] = o.data
        out[sym_off:sym_off + len(symdata)] = symdata
        out[str_off:str_off + len(strtab)] = strtab
        out[shstr_off:shstr_off + len(shstr)] = shstr
        for k, ph in enumerate(self.phdrs):
            struct.pack_into("<8I", out, 52 + 32 * k, *ph)
        ident = b"\x7fELF" + bytes([1, 1, 1, 0]) + bytes(8)
        hdr = ident + struct.pack("<HHIIIIIHHHHHH", 2, elf.EM_PI32V2, 1, self.entry_value, 52, shoff, 0, 52, 32,
                                  len(self.phdrs), 40, nsec, len(self.emitted) + 1)
        out[:52] = hdr
        sh = shoff + 40
        for o in self.emitted:
            typ = o.type
            struct.pack_into("<10I", out, sh, shname[o.name], typ, o.flags, o.vma, o.offset, o.size, 0, 0,
                             o.align, 0)
            sh += 40
        struct.pack_into("<10I", out, sh, shname[".shstrtab"], elf.SHT_STRTAB, 0, 0, shstr_off, len(shstr), 0, 0, 1, 0)
        sh += 40
        struct.pack_into("<10I", out, sh, shname[".symtab"], elf.SHT_SYMTAB, 0, 0, sym_off, len(symdata), nsec - 1, nlocal,
                         4, 16)
        sh += 40
        struct.pack_into("<10I", out, sh, shname[".strtab"], elf.SHT_STRTAB, 0, 0, str_off, len(strtab), 0, 0, 1, 0)
        return bytes(out)

    # ======================================================================================================
    # 10. map file
    # ======================================================================================================
    def map_text(self):
        lines = ["", "Memory Configuration", "", f"{'Name':<16} {'Origin':<18} {'Length':<18} Attributes"]
        for r in self.script.regions:
            reg = self.regions[r.name]
            lines.append(f"{r.name:<16} 0x{reg.origin:016x} 0x{reg.length:016x} {r.attrs}")
        if not self.script.regions:
            lines.append(f"{'*default*':<16} 0x{0:016x} 0x{MASK64:016x}")
        lines += ["", "Linker script and memory map", ""]
        for obj in self.objs:
            lines.append(f"LOAD {obj.name}")
        for o in self.outs:
            if o.spec.name == "/DISCARD/" or not o.emit:
                continue
            nm = o.name
            head = f"{nm:<15}" if len(nm) < 15 else nm + "\n" + " " * 16
            lines.append(f"{head} 0x{o.vma:016x} {'0x%x' % o.size:>10}" + (f" load address 0x{o.lma:016x}" if o.lma != o.vma else ""))
            for sec in o.inputs:
                if sec.size == 0 and not sec.keep:
                    continue
                nm2 = " " + sec.name
                if len(nm2) >= 16:
                    lines.append(nm2)
                    nm2 = " " * 16
                lines.append(f"{nm2:<16} 0x{o.vma + sec.offset:016x} {'0x%x' % sec.size:>10} {sec.obj.name}")
        lines.append("")
        return "\n".join(lines) + "\n"

    # ======================================================================================================
    def run(self):
        self.read_script()
        self.read_inputs()
        for name, text in self.o.defsyms:
            pass
        self.alloc_commons()
        self.build_outs()
        self.match()
        self.outs_by_spec = {id(o.spec): o for o in self.outs}
        if self.o.gc:
            self.gc()
        self.layout_commons()
        self.merge_sections()
        # --defsym: assignments evaluated before the script's
        for name, text in reversed(self.o.defsyms):
            lx = S.Lexer(text)
            self.script.top.insert(0, S.Assign(name, "=", S.parse_expr(lx)))
        self.layout()
        self.check_undefined()
        self.finish_commons()
        self.set_entry()
        self.emitted = [o for o in self.outs if o.emit and o.spec.name != "/DISCARD/"]
        for o in self.emitted:
            o.data = bytearray(o.size)
        self.build_data()
        self.apply_relocs()
        if self.errors and not self.o.noinhibit:
            return None
        return self.write()

    def finish_commons(self):
        pass


def link(opts):
    """Link; returns (output bytes or None, messages). Raises LinkError for fatal problems."""
    ld = Linker(opts)
    data = ld.run()
    return ld, data


# --- command line ------------------------------------------------------------------------------------------------

def parse_args(argv):
    o = Options()
    it = iter(range(len(argv)))
    i = 0
    n = len(argv)

    def value(opt, form_long=None):
        nonlocal i
        a = argv[i]
        if "=" in a and a.startswith("--"):
            return a.split("=", 1)[1]
        if len(a) > len(opt) and not a.startswith("--"):
            return a[len(opt):]
        i += 1
        if i >= n:
            raise LinkError(f"{a}: missing argument")
        return argv[i]

    ignored_with_arg = {"-m", "-z", "--plugin", "-plugin", "-plugin-opt", "--plugin-opt", "-b", "--format", "-A",
                        "--sysroot", "-rpath", "--hash-style", "--build-id", "-soname", "-h", "--dynamic-linker",
                        "-I", "-y", "--trace-symbol", "-Y", "--gpsize", "-G", "-assert", "--architecture"}
    while i < n:
        a = argv[i]
        if a in ("-o", "--output") or (a.startswith("--output=")):
            o.output = value("-o")
        elif a == "-T" or a == "--script" or a.startswith("--script=") or (a.startswith("-T") and not a.startswith(
                ("-Ttext", "-Tdata", "-Tbss"))):
            o.scripts.append(value("-T"))
        elif a.startswith(("-Ttext", "--Ttext")):
            v = a.split("=", 1)[1] if "=" in a else (argv[i + 1] if len(a) in (6, 7) else a[6:])
            if "=" not in a and len(a) in (6, 7):
                i += 1
            o.ttext = int(v, 0)
        elif a.startswith(("-Tdata", "--Tdata", "-Tbss", "--Tbss")):
            if "=" not in a:
                i += 1
        elif a == "-e" or a == "--entry" or a.startswith("--entry="):
            o.entry = value("-e")
        elif a == "--gc-sections":
            o.gc = True
        elif a == "--no-gc-sections":
            o.gc = False
        elif a in ("-Map", "--Map") or a.startswith(("-Map=", "--Map=")):
            o.map = value("-Map") if not a.startswith(("-Map=", "--Map=")) else a.split("=", 1)[1]
        elif a.startswith("--defsym"):
            v = value("--defsym")
            name, _, expr = v.partition("=")
            o.defsyms.append((name, expr))
        elif a == "-u" or a == "--undefined" or a.startswith("--undefined="):
            o.undefined.append(value("-u"))
        elif a.startswith("-L") or a == "--library-path" or a.startswith("--library-path="):
            o.libpaths.append(value("-L"))
        elif a == "-l" or a.startswith("-l") and not a.startswith("-learn"):
            o.inputs.append(("lib", value("-l")))
        elif a == "--library" or a.startswith("--library="):
            o.inputs.append(("lib", value("-l")))
        elif a in ("--start-group", "-("):
            o.inputs.append(("start-group",))
        elif a in ("--end-group", "-)"):
            o.inputs.append(("end-group",))
        elif a in ("-s", "--strip-all"):
            o.strip_all = True
        elif a in ("-S", "--strip-debug"):
            o.strip_debug = True
        elif a == "--allow-multiple-definition" or a == "-z" and False:
            o.allow_multiple = True
        elif a == "--noinhibit-exec":
            o.noinhibit = True
        elif a == "--print-gc-sections":
            o.print_gc = True
        elif a == "--fatal-warnings":
            o.fatal_warnings = True
        elif a in ignored_with_arg or a.split("=")[0] in ignored_with_arg:
            if "=" not in a:
                i += 1
        elif a.startswith("-") and a != "-":
            pass                          # --relax, -O, -static, -nostdlib, --no-undefined, ...: accepted and ignored
        else:
            o.inputs.append(("file", a))
        i += 1
    return o


def main(args):
    """Entry point of `python3 -m pi32v2isa ld` (args: an argparse namespace with .argv)."""
    argv = list(args.argv)
    try:
        opts = parse_args(argv)
        if not opts.inputs and not opts.scripts:
            print("ld: no input files", file=sys.stderr)
            return 1
        ld, data = link(opts)
    except (LinkError, ScriptError) as e:
        print(f"ld: {e}", file=sys.stderr)
        return 1
    for w in ld.warnings:
        print(w, file=sys.stderr)
    for e in ld.errors:
        print(e, file=sys.stderr)
    if opts.map:
        Path(opts.map).write_text(ld.map_text())
    if data is None:
        return 1
    out = Path(opts.output)
    out.write_bytes(data)
    out.chmod(0o755)
    return 0
