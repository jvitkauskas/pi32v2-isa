# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""An objdump for pi32v2 ELF files whose text matches JieLi's objdump (docs/OBJDUMP.md).

    python3 -m pi32v2isa objdump [-d] [-D] [-h] [-t] [-r] [-s] [-j SECTION]... [-mcpu=r3] FILE...

Disassembly goes through the instruction table (codec.decode / codec.format); everything else (headers,
labels, spacing, annotations, symbol and section tables) follows what JieLi's objdump prints, found by
comparing the two (`python3 -m pi32v2isa oracle objdumpcompare`)."""

import re
import struct
import sys
from pathlib import Path

from . import codec, elf, table as tablemod

OPTIONS_HELP = """usage: objdump [options] FILE...
  -d, -disassemble          disassemble the code sections
  -D, -disassemble-all      disassemble every section
  -h, -section-headers      print the section headers
  -t                        print the symbol table
  -r                        print the relocation records
  -s                        print the contents of the sections
  -j NAME, -section=NAME    only these sections (repeatable)
  -mcpu=r3                  CPU (r3 and r4 enable the floating-point forms; default and r2 do not)
  -mattr=+fprev1            enable the floating-point forms
  -no-show-raw-insn         leave out the instruction bytes
  -no-leading-addr          leave out the addresses
  -start-address=A, -stop-address=A
"""

# Instruction forms JieLi's objdump decodes only when told the CPU has them (found with `oracle` probes of every
# table example, docs/OBJDUMP.md): -mcpu=r3 / -mcpu=r4 / -mattr=+fprev1 enable the floating-point ones; -mcpu=r2
# and r3 also enable the three SIMD-shift / copex forms.
FPU_IDS = frozenset("""
add.f.rrr add.f.rrr.p bfeq.rr bfeq.rr.l bfge.rr bfge.rr.l bfgt.rr bfgt.rr.l bfle.rr bfle.rr.l bflt.rr
bflt.rr.l bfne.rr.l bford.rr.l bfueq.rr.l bfuge.rr bfuge.rr.l bfugt.rr bfugt.rr.l bfule.rr bfule.rr.l bfult.rr
bfult.rr.l bfune.rr bfune.rr.l bfunknown.rr.l bfuno.rr.l div.f.rrr div.f.rrr.p fcmp.rr fcmp.rr.p fmax.rrr
fmax.rrr.p fmin.rrr fmin.rrr.p ftof.ceil.rr ftof.ceil.rr.p ftof.even.rr ftof.even.rr.p ftof.floor.rr
ftof.floor.rr.p ftof.full.rr ftof.full.rr.p ftof.half.rr ftof.half.rr.p ftof.trunc.rr ftof.trunc.rr.p
ftoi.ceil.rr ftoi.ceil.rr.p ftoi.even.rr ftoi.even.rr.p ftoi.floor.rr ftoi.floor.rr.p ftoi.trunc.rr
ftoi.trunc.rr.p ftou.ceil.rr ftou.ceil.rr.p ftou.even.rr ftou.even.rr.p ftou.floor.rr ftou.floor.rr.p
ftou.trunc.rr ftou.trunc.rr.p iff.eq.rr iff.ge.rr iff.gt.rr iff.le.rr iff.lt.rr iff.ne.rr.1 iff.ne.rr.2
iff.ne.rr.3 iff.ne.rr.4 iff.ne.rr.5 iff.ne.rr.6 iff.uge.rr iff.ugt.rr iff.ule.rr iff.ult.rr iff.une.rr itof.rr
itof.rr.p madd.f.rrr madd.f.rrr.p msub.f.rrr msub.f.rrr.p mul.f.rrr mul.f.rrr.p sub.f.rrr sub.f.rrr.p utof.rr
utof.rr.p
""".split())
R2_IDS = frozenset("copex.ppi copex.ppi.p shiftr.rpi.mode shiftr.rpi.mode.p shiftr.rpr.mode shiftr.rpr.mode.p".split())


class ObjdumpError(Exception):
    pass


# --- decoding ------------------------------------------------------------------------------------------------

class Decoder:
    """Instruction lookup by the first word, first matching table entry, with entries switched off by CPU."""

    def __init__(self, tab, disabled=frozenset()):
        self.tab = tab
        self.disabled = disabled
        self.by_mask = {}      # first-word mask -> {first-word value -> [(index, insn)]}
        for n, insn in enumerate(tab.insns):
            if insn.id in disabled:
                continue
            shift = 16 * (len(insn.words) - 1)
            m, v = insn.mask >> shift, insn.value >> shift
            self.by_mask.setdefault(m, {}).setdefault(v, []).append((n, insn))
        self.cache = {}

    def candidates(self, word):
        got = self.cache.get(word)
        if got is None:
            found = []
            for m, values in self.by_mask.items():
                found += values.get(word & m, ())
            got = self.cache[word] = [i for _, i in sorted(found, key=lambda x: x[0])]
        return got

    def length_of(self, word):
        """Bytes the instruction starting with this first word needs (2, 4 or 6), as the first word decides."""
        if word < 0xE000:
            return 2
        if 0xFF00 <= word <= 0xFFEF:
            return 6
        return 4

    def decode(self, data, off):
        """(insn, values, length) for the instruction at data[off:], or None."""
        if off + 2 > len(data):
            return None
        word = data[off] | (data[off + 1] << 8)
        for insn in self.candidates(word):
            n = len(insn.words)
            if off + 2 * n > len(data):
                continue
            value = 0
            for k in range(n):
                value = (value << 16) | data[off + 2 * k] | (data[off + 2 * k + 1] << 8)
            if value & insn.mask == insn.value:
                return insn, codec.fields_of(insn, data, off), 2 * n
        return None


def decoder_for(tab, mcpu=None, mattr=()):
    """The decoder for a CPU choice: no -mcpu leaves out the floating-point and r2 forms."""
    off = FPU_IDS | R2_IDS
    cpu = (mcpu or "").lower()
    if cpu in ("r3", "r4"):
        off = frozenset()
    elif cpu == "r2":
        off = FPU_IDS
    elif cpu not in ("", "r2", "r3", "r4"):
        raise ObjdumpError(f"unsupported -mcpu={mcpu}")
    if any(a.lstrip("+") == "fprev1" for a in mattr):
        off = off - FPU_IDS
    return Decoder(tab, off)


# --- reading the file ------------------------------------------------------------------------------------------

class File:
    def __init__(self, path):
        self.path = str(path)
        self.data = Path(path).read_bytes()
        if self.data[:4] != b"\x7fELF":
            raise ObjdumpError(f"{path}: file format not recognized")
        self.obj = elf.read(self.data)
        self.sections = self.obj.sections
        self.symbols = self.obj.symbols
        self.machine = self.obj.e_machine


def format_name(f):
    return "ELF32-pi32v2" if f.machine == elf.EM_PI32V2 else "ELF32-unknown"


def section_kinds(s):
    """('TEXT'|'DATA'|'BSS' words as the section table prints them)."""
    text = bool(s.flags & elf.SHF_EXECINSTR)
    loaded = bool(s.flags & (elf.SHF_ALLOC | elf.SHF_WRITE))
    data = s.type == elf.SHT_PROGBITS and loaded
    bss = s.type == elf.SHT_NOBITS and loaded
    return text, data, bss


# --- output pieces -----------------------------------------------------------------------------------------------

def header(f):
    return f"\n{f.path}:\tfile format {format_name(f)}\n\n"


def section_headers(f):
    out = ["Sections:", "Idx Name          Size      Address          Type"]
    for s in f.sections:
        text, data, bss = section_kinds(s)
        kinds = ("TEXT " if text else "") + ("DATA " if data else "") + ("BSS" if bss else "")
        out.append(f"{s.index:3d} {s.name:<13} {s.length:08x} {s.addr:016x} {kinds}")
    return "\n".join(out) + "\n"


def symbol_line(f, sym):
    t = sym.type
    glob = " " if t == elf.STT_NOTYPE else ("g" if sym.bind != elf.STB_LOCAL else "l")
    weak = "w" if sym.bind == elf.STB_WEAK else " "
    debug = "d" if t in (elf.STT_SECTION, elf.STT_FILE) else " "
    kind = "f" if t == elf.STT_FILE else ("F" if t == elf.STT_FUNC else " ")
    value, size = sym.value, sym.size
    if sym.shndx == elf.SHN_UNDEF:
        where = "*UND*"
    elif sym.shndx == elf.SHN_ABS:
        where = "*ABS*"
    elif sym.shndx == elf.SHN_COMMON:
        where, value, size = "*COM*", sym.size, sym.value
    elif isinstance(sym.shndx, int) and sym.shndx < len(f.sections):
        where = f.sections[sym.shndx].name
    else:
        where = "*UND*"
    return f"{value:08x} {glob}{weak}   {debug}{kind} {where}\t\t {size:08x} {sym.name}"


def symbol_table(f):
    return "SYMBOL TABLE:\n" + "".join(symbol_line(f, s) + "\n" for s in f.symbols)


def reloc_records(f):
    out = []
    for s in f.sections:
        if s.type != elf.SHT_RELA:
            continue
        out.append(f"RELOCATION RECORDS FOR [{s.name}]:")
        for k in range(len(s.data) // 12):
            off, info, _ = struct.unpack_from("<IIi", s.data, 12 * k)
            name = elf.RELOCS.get(info & 0xFF, f"Unknown")
            out.append(f"{off:08x} {name} Unknown")
        out.append("")
    return "\n".join(out) + "\n" if out else ""


# --- disassembly -----------------------------------------------------------------------------------------------

# Forms whose printed text carries a `<symbol+offset : address >` annotation: the branches and calls (the
# address is the end of the instruction plus the printed offset) and the immediate loads (the address is the
# value with its low bit cleared). Found by probing every table example (docs/OBJDUMP.md).
ANNOTATED_IMM = frozenset(("li.s16", "li.s16.p", "li.u32"))
ANNOTATED_BRANCH = frozenset("""
bc.cc bc.cs bc.eq bc.ge bc.gt bc.hi bc.le bc.ls bc.lt bc.ne beq.and.modimm.ri.l beq.and.ri beq.and.rr beq.ri
beq.ri.l beq.ri.l.modimm beq.rr beq.rr.l beqz bfeq.rr bfeq.rr.l bfge.rr bfge.rr.l bfgt.rr bfgt.rr.l bfle.rr
bfle.rr.l bflt.rr bflt.rr.l bfne.rr.l bford.rr.l bfueq.rr.l bfuge.rr bfuge.rr.l bfugt.rr bfugt.rr.l bfule.rr
bfule.rr.l bfult.rr bfult.rr.l bfune.rr bfune.rr.l bfunknown.rr.l bfuno.rr.l bge.ri bge.ri.l bge.ri.l.modimm
bge.rr bge.rr.l bges.ri bges.ri.l bges.ri.l.modimm bges.rr bges.rr.l bgt.ri bgt.ri.l bgt.ri.l.modimm bgt.rr
bgt.rr.l bgts.ri bgts.ri.l bgts.ri.l.modimm bgts.rr bgts.rr.l ble.ri ble.ri.l ble.ri.l.modimm ble.rr ble.rr.l
bles.ri bles.ri.l bles.ri.l.modimm bles.rr bles.rr.l blt.ri blt.ri.l blt.ri.l.modimm blt.rr blt.rr.l blts.ri
blts.ri.l blts.ri.l.modimm blts.rr blts.rr.l bne.and.modimm.ri.l bne.and.ri bne.and.rr bne.ri bne.ri.l
bne.ri.l.modimm bne.rr bne.rr.l bnez bunknown.ri.l.14to15 bunknown.ri.l.14to15.modimm bunknown.ri.l.4to7
bunknown.ri.l.4to7.modimm bunknown.rr.l.14to15 bunknown.rr.l.4to7 call.l call.s call.xl dbnz.r goto.l goto.s
gotoss.xl
""".split())
BRANCH_FIELD = re.compile(r"(?:goto|gotoss|call) \{(\w)\}")
TRAILING_SPACE = frozenset(("ld.w", "ld.w.pi", "ld.w.pin"))   # `r1 = [r1+0] `: the text keeps a space after `]`
HEX_BYTES = 18
M64 = 0xFFFFFFFFFFFFFFFF
BRACE_PAD = " " * 31


class Block:
    """An open `rep` or `if` block: how much of its body is left (rep: bytes; if: instructions)."""
    __slots__ = ("kind", "left", "else_left", "in_else")

    def __init__(self, kind, left, else_left=0):
        self.kind, self.left, self.else_left, self.in_else = kind, left, else_left, False


class Symbols:
    """The symbols an address is named by: `name+offset`, as the nearest symbol at or below it."""

    def __init__(self, f):
        self.rel = f.obj.e_type == 1
        pairs = []
        for x in f.symbols[1:]:
            if not x.name or x.name.startswith(".L") or x.shndx == elf.SHN_UNDEF or x.shndx == elf.SHN_COMMON:
                continue
            pairs.append((x.value, x.name, x.shndx))
        self.all = sorted(pairs, key=lambda p: (p[0], p[1]))
        self.addrs = [p[0] for p in self.all]
        self.by_section = {}
        self.section_addrs = {}

    def set_section(self, index, pairs):
        """The names an address in section `index` is looked up in (relocatable files): its own symbols."""
        self.by_section[index] = [(a, n, index) for a, n, _ in pairs]
        self.section_addrs[index] = [a for a, _, _ in pairs]

    def lookup(self, target, section):
        import bisect
        if self.rel:
            lst = self.by_section.get(section, [])
            addrs = self.section_addrs[section]
        else:
            lst, addrs = self.all, self.addrs
        k = bisect.bisect_right(addrs, target) - 1
        if k < 0:
            return None
        return lst[k]

    def annotation(self, target, section):
        target &= M64
        got = self.lookup(target, section)
        if got is None:
            return ""
        off = target - got[0]
        return f" <{got[1]}{'+0x%X' % off if off else ''} : {target:x} >"


class Disassembler:
    def __init__(self, f, dec, opts):
        self.f = f
        self.dec = dec
        self.opts = opts
        self.size = 1                 # the length the decoder last reported: it stays when a decode fails early
        self.out = []
        self.syms = Symbols(f)

    def run(self, sections):
        for s in sections:
            self.section(s)
        return "".join(self.out)

    def section(self, s):
        f = self.f
        w = self.out.append
        if s.length == 0 or s.type == elf.SHT_NOBITS:
            return
        w(f"Disassembly of section {s.name}:\n")
        syms = [x for x in f.symbols if x.shndx == s.index and x.type != elf.STT_FILE and not x.name.startswith(".L")]
        pairs = sorted(((x.value, x.name, x.type) for x in syms), key=lambda p: (p[0], p[1]))
        start = s.addr
        if not pairs or pairs[0][0] != start:
            pairs.insert(0, (start, s.name, elf.STT_NOTYPE))
        self.syms.set_section(s.index, pairs)
        data = bytes(s.data)
        size = s.length
        first = True
        for k, (addr, name, typ) in enumerate(pairs):
            lo = addr - s.addr
            hi = size if k + 1 == len(pairs) else pairs[k + 1][0] - s.addr
            hi = min(hi, size)
            if lo >= hi:
                continue
            table_entry = 0                        # compiler jump tables: .GJTIS (bytes), .GJTIL.. (halfwords)
            if name.startswith(".GJTI") and len(name) > 5 and name[5] != "E":
                table_entry = 1 if name[5] == "S" else 2
            if name.startswith(".GJTIE"):
                pass                               # the end of a table: code goes on with no label
            else:
                w(("" if first else "\n") + f"{name}:\n")
            first = False
            if table_entry:
                self.table(s, lo, hi, table_entry)
            else:
                if typ in (elf.STT_OBJECT, elf.STT_COMMON):
                    self.hexdump(s, data, lo, hi)
                else:
                    self.code(s, data, lo, hi)
                w("\n")
            if self.opts.get("r"):
                for off, rtype, _, _ in sorted(s.relocs):
                    if lo <= off < hi:
                        w(f"\t\t\t{off:08x}:  {elf.RELOCS.get(rtype, 'Unknown')}\tUnknown\n")

    def table(self, s, lo, hi, step):
        w = self.out.append
        for a in range(lo, hi, step):
            raw = self.raw(s, a, step)
            v = int.from_bytes(raw, "little")
            w(f"{s.addr + a:8x}:    {' '.join(f'{b:02x}' for b in raw)}     < {v} : 0x{v:X} >\n")

    def hexdump(self, s, data, lo, hi):
        w = self.out.append
        for a in range(lo, hi, 8):
            chunk = data[a:min(a + 8, hi)]
            hexs = "".join(f" {b:02x}" for b in chunk)
            asc = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in chunk)
            w(f"{s.addr + a:8x}:\t{hexs:<33}{asc}\n")

    def raw(self, s, off, n):
        """n bytes at section offset off, taken from the file (so also past the section's end)."""
        base = s.offset + off
        return self.f.data[base:base + n]

    @staticmethod
    def hexb(raw):
        return "".join(f"{b:02x} " for b in raw)

    def code(self, s, data, lo, hi):
        w = self.out.append
        stack = []
        index = lo
        second = False            # the previous line ended with `#`: this one issues in parallel with it
        while index < hi:
            addr = s.addr + index
            got = self.dec.decode(data, index)
            if got is None:
                if index + 2 <= len(data) and index + self.dec.length_of(data[index] | (data[index + 1] << 8)) <= len(data):
                    self.size = 2
                n = self.size
                w(f"{addr:8x}:    {self.hexb(self.raw(s, index, n)):<{HEX_BYTES}} <unknown instruction>\n")
                index += n
                continue
            insn, values, n = got
            self.size = n
            text = codec.format(insn, values)
            if insn.id in TRAILING_SPACE:
                text += " "
            depth = len(stack)
            if second:
                pad = "\t\t " if depth == 0 else "\t" * (depth + 1) + "  "
            else:
                pad = "\t" * (depth + 1)
            closers = self.advance(stack, insn, values, n, second)
            ann = ""
            if insn.id in ANNOTATED_BRANCH:
                m = BRANCH_FIELD.search(insn.syntax)
                ann = self.syms.annotation(addr + n + codec.value(insn.fields[m.group(1)], values[m.group(1)],
                                           len(insn.field_bits(m.group(1)))), s.index)
            elif insn.id in ANNOTATED_IMM:
                v = int(re.search(r"= (-?\d+)", text).group(1))
                ann = self.syms.annotation(v & ~1, s.index)
            w(f"{addr:8x}:    {self.hexb(data[index:index + n]):<{HEX_BYTES}}{pad}{text}")
            for c in closers:
                w(f"\n{BRACE_PAD}\t{c}")
            w(ann + "\n")
            second = text.rstrip().endswith("#")
            index += n

    def advance(self, stack, insn, values, n, second):
        """Account for one printed instruction in the open blocks; return the brace lines it closes."""
        for b in stack:
            if b.kind == "rep":
                b.left -= n
            elif not second:
                if b.in_else:
                    b.else_left -= 1
                else:
                    b.left -= 1
        closers = []
        while stack:
            b = stack[-1]
            if b.kind == "if" and not b.in_else and b.left <= 0:
                if b.else_left > 0:
                    b.in_else = True
                    closers.append("} else {")
                    break
                stack.pop()
                closers.append("}")
            elif (b.kind == "if" and b.in_else and b.else_left <= 0) or (b.kind == "rep" and b.left <= 0):
                stack.pop()
                closers.append("}")
            else:
                break
        if insn.body:
            f = insn.fields[insn.body]
            stack.append(Block("rep", codec.value(f, values[insn.body], len(insn.field_bits(insn.body)))))
        elif insn.block:
            def cnt(key):
                f = insn.fields[insn.block[key]]
                return codec.value(f, values[insn.block[key]], len(insn.field_bits(insn.block[key])))
            stack.append(Block("if", cnt("then"), cnt("else")))
        return closers


def run_file(f, opts, tab):
    out = [header(f)]
    wanted = opts.get("sections")
    secs = [s for s in f.sections if not wanted or s.name in wanted]
    if opts.get("d") or opts.get("D"):
        dec = decoder_for(tab, opts.get("mcpu"), opts.get("mattr", ()))
        code = [s for s in secs if opts.get("D") or s.flags & elf.SHF_EXECINSTR]
        out.append(Disassembler(f, dec, opts).run(code))
    if opts.get("r") and not (opts.get("d") or opts.get("D")):
        out.append(reloc_records(f))
    if opts.get("h"):
        out.append(section_headers(f))
    if opts.get("t"):
        out.append(symbol_table(f))
    return "".join(out)


def parse_args(argv):
    opts = {"files": [], "sections": [], "mattr": []}
    it = iter(argv)
    for a in it:
        if a in ("-d", "-disassemble", "--disassemble"):
            opts["d"] = True
        elif a in ("-D", "-disassemble-all", "--disassemble-all"):
            opts["D"] = True
        elif a in ("-h", "-section-headers", "--section-headers", "-headers"):
            opts["h"] = True
        elif a in ("-t", "--syms"):
            opts["t"] = True
        elif a in ("-r", "--reloc"):
            opts["r"] = True
        elif a in ("-s", "--full-contents"):
            opts["s"] = True
        elif a == "-j" or a == "-section":
            opts["sections"].append(next(it))
        elif a.startswith("-j") and len(a) > 2:
            opts["sections"].append(a[2:])
        elif a.startswith(("-section=", "--section=")):
            opts["sections"].append(a.split("=", 1)[1])
        elif a.startswith("-mcpu="):
            opts["mcpu"] = a.split("=", 1)[1]
        elif a.startswith("-mattr="):
            opts["mattr"] += a.split("=", 1)[1].split(",")
        elif a.startswith("-"):
            raise ObjdumpError(f"unsupported option {a}")
        else:
            opts["files"].append(a)
    return opts


def main(argv=None, tab=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    try:
        opts = parse_args(argv)
        if not opts["files"]:
            sys.stderr.write(OPTIONS_HELP)
            return 1
        tab = tab or tablemod.load()
        for path in opts["files"]:
            sys.stdout.write(run_file(File(path), opts, tab))
    except ObjdumpError as e:
        sys.stderr.write(f"objdump: {e}\n")
        return 1
    return 0
