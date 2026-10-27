#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""The tools of the drop-in toolchain (docs/DROPIN.md): one script, started under the name of the tool it
stands for (a symlink in common/bin or pi32v2/bin), that turns the command line JieLi's tool takes into the one
of the LLVM fork's tool and runs that.

    clang clang++ cc cxx        clang, without the options only JieLi's compiler has
    ld lto-wrapper              ld.lld (its LTO replaces LLVMgold.so)
    lto-ar                      llvm-ar
    objdump                     pi32v2isa's objdump (JieLi's text)
    objsizedump                 the symbol size listing
    llvm-read-version link-version

Set PI32V2_DROPIN_VERBOSE=1 to see each command run. The tool's own directory decides where everything is:
<root>/{common,pi32v2}/bin/NAME, LLVM's tools in <root>/llvm/bin."""

import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0]))))
LLVM = os.path.join(ROOT, "llvm", "bin")
VERBOSE = bool(os.environ.get("PI32V2_DROPIN_VERBOSE"))


def run(argv, replace=True):
    if VERBOSE:
        sys.stderr.write("dropin: " + " ".join(argv) + "\n")
    sys.stdout.flush()
    if replace:
        os.execv(argv[0], argv)
    return subprocess.call(argv)


def die(msg):
    sys.stderr.write(f"{os.path.basename(sys.argv[0])}: {msg}\n")
    sys.exit(1)


# ---- clang -------------------------------------------------------------------------------------------------

# -mllvm options of JieLi's code generator that ours does not have (none yet: -pi32v2-large-program, which the
# SDK passes, exists and is passed on; calls between flash and RAM code are then 6 bytes, tail calls stay calls)
MLLVM_DROPPED = set()

# Mistakes clang 4 only warned about and the fork's clang reports as errors; the SDK's sources have them
DOWNGRADED = ["implicit-function-declaration", "implicit-int", "int-conversion", "incompatible-function-pointer-types",
              "incompatible-pointer-types", "return-mismatch", "incompatible-pointer-types-discards-qualifiers"]


def clang_args(argv):
    out = []
    it = iter(range(len(argv)))
    i = 0
    has_std = False
    c_input = False
    while i < len(argv):
        a = argv[i]
        if a == "-mfprev1":
            # the floating-point forms; -mcpu=r3 (all the SDK's) has them already, other cpus get the feature
            out += ["-Xclang", "-target-feature", "-Xclang", "+fprev1"]
        elif a == "-fallow-pointer-null":
            # a load or store at address 0 is a real access (clang 4's flag): the IR attribute that says so
            out.append("-fno-delete-null-pointer-checks")
        elif a == "-fno-allow-pointer-null":
            out.append("-fdelete-null-pointer-checks")
        elif a == "-fprefer-gnu-section":
            # a function's __attribute__((section)) over #pragma code_seg: no difference in section names
            # or flags was found against JieLi's compiler (docs/DROPIN.md)
            pass
        elif a == "-mllvm" and i + 1 < len(argv) and argv[i + 1].split("=")[0] in MLLVM_DROPPED:
            i += 1
        else:
            if a.startswith(("-std=", "--std=")):
                has_std = True
            elif a == "-std":
                has_std = True
            elif a.endswith(".c") and not a.startswith("-"):
                c_input = True
            elif a == "-x" and i + 1 < len(argv) and argv[i + 1] in ("c", "c-header"):
                c_input = True
            out.append(a)
        i += 1
    out = ["-Wno-unknown-warning-option"] + ["-Wno-error=" + w for w in DOWNGRADED] + out
    if "-g" in out and not any(a.startswith(("-gdwarf", "-gstrict-dwarf")) for a in out):
        # the SDK's libraries carry DWARF 4 (clang 4); one version in the program
        out.append("-gdwarf-4")
    if c_input and not has_std:
        # clang 4 compiled C as gnu11; the fork's default is newer
        out.insert(0, "-std=gnu11")
    return out


def tool_clang(name):
    args = sys.argv[1:]
    pre = []
    if name in ("cc", "cxx"):
        pre = ["-target", "pi32v2"]
    exe = "clang++" if name in ("clang++", "cxx") else "clang"
    run([os.path.join(LLVM, exe)] + pre + clang_args(args))


# ---- ld / lto-wrapper --------------------------------------------------------------------------------------

# --plugin-opt=-X options (JieLi's LLVMgold.so passes them on to LLVM) that are generic LLVM options in the
# fork as well, and those that have another name there
LD_PASS = {"enable-ipra", "global-merge-on-const", "emulated-tls", "pi32v2-large-program"}
LD_RENAME = {"inline-max-allocated-size": "inline-max-stacksize"}
# JieLi-only code generation and link-time options, with what each stood for. None of them changes what the
# program does; the first group changes how big or how fast it is.
LD_DROPPED = {
    "pi32v2-always-use-itblock",      # prefer if blocks for any short conditional code: ours has its own pass
    "pi32v2-merge-max-offset",        # reach of the merged-globals base register
    "pi32v2-enable-simd",             # the SIMD forms: not in ours
    "pi32v2-enable-rep-memop",        # inline memcpy/memset as rep loops
    "inline-normal-into-special-section",
    "dont-used-symbol-list",          # names the optimizer must not turn calls into (printf -> puts)
    "mattr",                          # +fprev1: part of -mcpu=r3
    "inline-threshold",               # 5 in the SDK; the fork's cost model sets the size thresholds itself
                                      # (adjustInliningThreshold takes 40 off) and asserts if the base is below 40
}
# GNU ld takes a symbol from the archive that is scanned when it is first undefined, and scans an archive until
# nothing more is extracted before the next: a function the SDK's libraries define themselves (ecvtbuf, itoa,
# strtod, ...) comes from them, not from the C library listed before them. ld.lld takes the first archive on the
# command line, so the toolchain's own libraries go last in the group.
SYSTEM_LIBS = {"libc.a", "libm.a", "libg.a", "libcompiler_rt.a", "libcompiler-rt.a"}
MOVABLE_PREFIXES = ("movable-region", "enable-movable-region")


def read_lines(path):
    with open(path, errors="replace") as f:
        return [ln.strip() for ln in f if ln.strip()]


def expand(argv):
    """@file response files, as ld reads them: one level, whitespace separated."""
    out = []
    for a in argv:
        if a.startswith("@") and os.path.isfile(a[1:]):
            with open(a[1:], errors="replace") as f:
                out += f.read().split()
        else:
            out.append(a)
    return out


def ld_args(argv, defer=True):
    out = []
    movable_maps = []
    i = 0
    relocatable = False
    depth = 0
    deferred = []
    while i < len(argv):
        a = argv[i]
        if a in ("--start-group", "-(", "--end-group", "-)"):
            # the SDK's link line nests groups, which JieLi's ld takes; ld.lld does not: the outermost pair
            # rescans everything inside it, as the inner one would
            if a in ("--start-group", "-("):
                depth += 1
                if depth == 1:
                    out.append(a)
            else:
                depth -= 1
                if depth == 0:
                    out += deferred + [a]
                    deferred = []
        elif defer and depth > 0 and os.path.basename(a) in SYSTEM_LIBS:
            deferred.append(a)
        elif a == "--plugin":
            i += 1                      # LLVMgold.so: ld.lld has the LTO built in
        elif a.startswith("--plugin="):
            pass
        elif a == "-M" or a.startswith("-M="):
            out.append("-Map=" + a[3:] if a.startswith("-M=") else "-M")
        elif a.startswith("--plugin-opt="):
            o = a[len("--plugin-opt="):]
            if o.startswith("-"):
                name, _, val = o[1:].partition("=")
                if name == "used-symbol-file":
                    # symbols the program needs although nothing refers to them (tables found by section)
                    out += ["--undefined-glob=" + s for s in read_lines(val)]
                elif name.startswith(MOVABLE_PREFIXES):
                    if name.endswith("-file-list"):
                        movable_maps.append(val)
                elif name in LD_DROPPED:
                    pass
                elif name in LD_RENAME:
                    out.append("-mllvm=-" + LD_RENAME[name] + ("=" + val if val else ""))
                elif name in LD_PASS:
                    out.append("-mllvm=" + o)
                else:
                    out.append("-mllvm=" + o)
            elif o == "save-temps":
                out.append("--save-temps")
            else:
                out.append(a)           # mcpu=r3, O2, ...: ld.lld takes these
        else:
            if a == "-r":
                relocatable = True
            out.append(a)
        i += 1
    for m in movable_maps:
        # the movable regions (code the program moves into RAM by name) are made by JieLi's code generator
        if os.path.isfile(m) and read_lines(m):
            sys.stderr.write(f"{os.path.basename(sys.argv[0])}: warning: {m} lists code for movable regions, "
                             "which this toolchain does not make; the code stays where the linker script puts it\n")
    return out, relocatable


# ---- GNU ld's choice of archive members ---------------------------------------------------------------------------
#
# ld.lld takes a symbol from the first archive on the command line that defines it, and the members in the order
# it needs them; GNU ld, which the SDK's link line and linker scripts were written for, scans each archive to a
# fixpoint, in order, and the members' order in the output is the order they were loaded (the order of the tables
# the scripts collect: initcalls, event handlers). So the members GNU ld would load are worked out here, from
# the archives' symbol tables, and given to ld.lld as the objects they are, in that order; the archives stay on the
# line, after them, for what the code generator asks for (memcpy, ...).

def ar_members(path):
    """[(offset, name, data_offset, size)], and the symbol table [(symbol, member offset)] of a GNU archive."""
    with open(path, "rb") as f:
        d = f.read()
    if d[:8] != b"!<arch>\n":
        raise ValueError("not an archive")
    pos, members, longnames, armap = 8, {}, b"", []
    while pos + 60 <= len(d):
        name = d[pos:pos + 16].decode("latin-1").strip()
        size = int(d[pos + 48:pos + 58])
        body = pos + 60
        if name == "/":
            if not armap:
                n = struct.unpack(">I", d[body:body + 4])[0]
                offs = struct.unpack(">%dI" % n, d[body + 4:body + 4 + 4 * n])
                names = d[body + 4 + 4 * n:body + size].split(b"\0")
                armap = [(names[i].decode("latin-1"), offs[i]) for i in range(n)]
        elif name == "//":
            longnames = d[body:body + size]
        elif name.startswith("/") and name != "/SYM64/" and name[1:].isdigit():
            k = int(name[1:])
            members[pos] = (longnames[k:longnames.index(b"/\n", k)].decode("latin-1"), body, size)
        elif name in ("/SYM64/",) or name.startswith("#1/"):
            raise ValueError("unsupported archive format")
        else:
            members[pos] = (name.rstrip("/"), body, size)
        pos = body + size + (size & 1)
    return members, armap, d


SYM_RE = r"\s+(?:[0-9a-fA-F-]{8}\s+)?(\S)\s+(.+)$"


def nm_objects(files):
    """{file: [(type, symbol)]} for objects."""
    out = {f: [] for f in files}
    nm = os.path.join(LLVM, "llvm-nm")
    for k in range(0, len(files), 200):
        r = subprocess.run([nm, "-A", "-g"] + files[k:k + 200], capture_output=True, text=True)
        for ln in r.stdout.splitlines():
            m = re.match(r"^(.*?):" + SYM_RE, ln)
            if m and m.group(1) in out:
                out[m.group(1)].append((m.group(2), m.group(3)))
    return out


def nm_archive(path, names):
    """The global symbols of each member of an archive, in member order: [[(type, symbol)]]. llvm-nm prints the
    members in order and says nothing on its standard output about those without symbols, so the blocks are
    matched to the members by name, forward; None where that fails."""
    r = subprocess.run([os.path.join(LLVM, "llvm-nm"), "-A", "-g", path], capture_output=True, text=True)
    blocks = []
    prefix = path + ":"
    for ln in r.stdout.splitlines():
        if not ln.startswith(prefix):
            continue
        m = re.match(r"^(.+?):" + SYM_RE, ln[len(prefix):])
        if not m:
            return None
        name, sym = m.group(1), (m.group(2), m.group(3))
        if blocks and blocks[-1][0] == name:
            blocks[-1][1].append(sym)
        else:
            blocks.append((name, [sym]))
    out = [[] for _ in names]
    k = 0
    for name, syms in blocks:
        while k < len(names) and names[k] != name:
            k += 1
        if k == len(names):
            return None
        out[k] = syms
        k += 1
    return out


def script_undefined(scripts):
    names = []
    for sc in scripts:
        try:
            text = open(sc, errors="replace").read()
        except OSError:
            continue
        for m in re.finditer(r"\b(?:EXTERN|ENTRY)\s*\(([^)]*)\)", text):
            names += m.group(1).replace(",", " ").split()
    return names


def gnu_members(args, scripts):
    """Rewrite args: archives replaced by the members GNU ld would load from them, as files in a new directory.
    Returns (args, directory) or None where the line is not one this handles."""
    toks = []                       # ("obj", path) ("ar", path) ("group", "(" / ")") ("other", arg)
    skip = {"-o", "-T", "-e", "-u", "--undefined", "-m", "-z", "-L", "-Map", "--script", "--entry"}
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--start-group", "-("):
            toks.append(("group", "("))
        elif a in ("--end-group", "-)"):
            toks.append(("group", ")"))
        elif a in skip and i + 1 < len(args):
            toks.append(("other", a))
            toks.append(("other", args[i + 1]))
            i += 1
        elif a.startswith("-"):
            toks.append(("other", a))
        elif a.endswith(".a"):
            toks.append(("ar", a))
        elif os.path.isfile(a):
            toks.append(("obj", a))
        else:
            toks.append(("other", a))
        i += 1
    ars = [t[1] for t in toks if t[0] == "ar"]
    objs = [t[1] for t in toks if t[0] == "obj"]
    if not ars:
        return None
    try:
        arinfo = {a: ar_members(a) for a in dict.fromkeys(ars)}
    except (OSError, ValueError, struct.error, UnicodeDecodeError):
        return None
    # symbols of the objects, and what the archive members need
    defs, undefs, strong = {}, {}, {}   # (file, member offset or None) -> set
    for f, syms in nm_objects(objs).items():
        for typ, sym in syms:
            if typ in "wv":
                continue
            (undefs if typ == "U" else defs).setdefault((f, None), set()).add(sym)
            if typ.isupper() and typ not in "UC":
                strong.setdefault((f, None), set()).add(sym)
    for a, (members, armap, _) in arinfo.items():
        names = [m[0] for m in members.values()]
        blocks = nm_archive(a, names)
        if blocks is None:
            return None
        for off, syms in zip(members, blocks):
            for typ, sym in syms:
                if typ == "U":
                    undefs.setdefault((a, off), set()).add(sym)
                elif typ.isupper() and typ != "C":
                    strong.setdefault((a, off), set()).add(sym)
    by_member = {}
    for a, (members, armap, _) in arinfo.items():
        d = by_member[a] = {}
        for sym, off in armap:
            d.setdefault(off, []).append(sym)
    defined = set()
    undefined = set(script_undefined(scripts))
    for k, a in enumerate(args):
        if a in ("-u", "--undefined") and k + 1 < len(args):
            undefined.add(args[k + 1])
    for o in objs:
        defined |= defs.get((o, None), set())
    for o in objs:
        undefined |= undefs.get((o, None), set())
    undefined -= defined
    loaded = []                     # (archive, member header offset), in the order loaded
    why = []                        # the symbol each was loaded for
    done = set()

    def scan(a):
        members, armap, _ = arinfo[a]
        any_loaded = False
        while True:
            again = False
            for sym, off in armap:
                if sym in undefined and (a, off) not in done and off in members:
                    done.add((a, off))
                    loaded.append((a, off))
                    why.append(sym)
                    defined.update(by_member[a].get(off, ()))
                    undefined.discard(sym)
                    undefined.update(undefs.get((a, off), set()) - defined)
                    undefined.difference_update(defined)
                    again = any_loaded = True
            if not again:
                return any_loaded

    group = []
    for kind, v in toks:
        if kind == "group" and v == "(":
            group = [[]]
        elif kind == "group" and v == ")":
            while True:
                if not any([scan(a) for a in group[0]]):
                    break
            group = []
        elif kind == "ar":
            if group:
                group[0].append(v)
            else:
                scan(v)
    # GNU ld lets a regular object's definition override one in bitcode (the SDK's strtod against the C library's);
    # ld.lld reports both. With the regular one first and -z muldefs the regular one is the one taken.
    order = [(o, None) for o in objs] + list(loaded)
    kinds = {}

    def is_ir(key):
        if key not in kinds:
            if key[1] is None:
                with open(key[0], "rb") as f:
                    head = f.read(4)
            else:
                m = arinfo[key[0]]
                head = m[2][m[0][key[1]][1]:m[0][key[1]][1] + 4]
            kinds[key] = head[:2] == b"BC" or head == b"\xde\xc0\x17\x0b"
        return kinds[key]

    owner = {}
    conflict_elf = set()
    for key in order:
        for sym in strong.get(key, ()):
            if sym in owner and is_ir(owner[sym]) != is_ir(key):
                conflict_elf.add(key if not is_ir(key) else owner[sym])
            owner.setdefault(sym, key)
    muldefs = bool(conflict_elf)
    if conflict_elf:
        moved = [k for k in loaded if k in conflict_elf]
        loaded = moved + [k for k in loaded if k not in conflict_elf]
        why = ["(moved)"] * len(moved) + [""] * (len(loaded) - len(moved))
    directory = tempfile.mkdtemp(prefix="dropin-members-")
    log = os.environ.get("PI32V2_DROPIN_MEMBERS_LOG")
    if log:
        with open(log, "w") as f:
            for (a, off), sym in zip(loaded, why):
                f.write("%s(%s)\t%s\n" % (a, arinfo[a][0][off][0], sym))
    files = []
    for n, (a, off) in enumerate(loaded):
        name, body, size = arinfo[a][0][off]
        sub = os.path.join(directory, str(n))
        os.mkdir(sub)
        path = os.path.join(sub, name)
        with open(path, "wb") as f:
            f.write(arinfo[a][2][body:body + size])
        files.append(path)
    # objects first, then the members in load order, then the archives (for what code generation asks for)
    out = [v for kind, v in toks if kind == "other" or kind == "obj"]
    out += files + ["--start-group"] + [a for a in dict.fromkeys(ars)] + ["--end-group"]
    if muldefs:
        out.append("-z")
        out.append("muldefs")
    return out, directory


def link(argv, version_out=None):
    if version_out:
        write_version_object(version_out, [a for a in argv if a.endswith((".a", ".o"))])
    emulate = not os.environ.get("PI32V2_DROPIN_NATIVE_ARCHIVES")
    args, relocatable = ld_args(expand(argv), defer=not emulate)
    scripts = []
    for k, a in enumerate(args):
        if a in ("-T", "--script") and k + 1 < len(args):
            scripts.append(args[k + 1])
        elif a.startswith("-T") and len(a) > 2:
            scripts.append(a[2:].lstrip("="))
    members_dir = None
    if emulate and not relocatable:
        res = gnu_members(args, scripts)
        if res:
            args, members_dir = res
        else:
            args, relocatable = ld_args(expand(argv), defer=True)
    cmd = [os.path.join(LLVM, "ld.lld")] + args + os.environ.get("PI32V2_DROPIN_LDFLAGS", "").split()
    if not relocatable and "--version" not in args and "-v" not in args:
        # the compiler's runtime last, as a compiler driver links it: only what is referenced is taken (a
        # 64-bit division the compiler could not prove fits the divide instruction)
        lib = os.path.join(ROOT, "pi32v2", "lib")
        for n in ("libclang_rt.builtins-pi32v2.a", "libpi32v2.a"):
            if os.path.isfile(os.path.join(lib, n)):
                cmd.append(os.path.join(lib, n))
    try:
        rc = run(cmd, replace=False)
    finally:
        if members_dir and not os.environ.get("PI32V2_DROPIN_KEEP_MEMBERS"):
            shutil.rmtree(members_dir, ignore_errors=True)
    sys.exit(rc)


def tool_ld():
    link(sys.argv[1:])


def tool_lto_wrapper():
    """--extra-arguments-from-file F (one argument a line) and --output-version-info F, then ld."""
    argv = sys.argv[1:]
    rest = []
    version_out = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--extra-arguments-from-file" and i + 1 < len(argv):
            rest += read_lines(argv[i + 1])
            i += 1
        elif a == "--output-version-info" and i + 1 < len(argv):
            version_out = argv[i + 1]
            i += 1
        else:
            rest.append(a)
        i += 1
    link(rest, version_out)


# ---- ar ----------------------------------------------------------------------------------------------------

def tool_lto_ar():
    argv = sys.argv[1:]
    out = []
    i = 0
    while i < len(argv):
        if argv[i] == "--plugin":
            i += 2
            continue
        if argv[i].startswith("--plugin="):
            i += 1
            continue
        out.append(argv[i])
        i += 1
    run([os.path.join(LLVM, "llvm-ar")] + out)


# ---- objdump -----------------------------------------------------------------------------------------------

INSN_LINE = re.compile(r"^ *([0-9a-f]+):    ")


def source_comments(path, text):
    """-print-dbg: each instruction line of the listing gets "\t\t\t  ## FILE:LINE:COLUMN" from the debug line
    table (llvm-symbolizer, the line-table row of its address); lines without one stay as they are."""
    lines = text.split("\n")
    addrs = []
    for k, ln in enumerate(lines):
        m = INSN_LINE.match(ln)
        if m:
            addrs.append((k, m.group(1)))
    sym = os.path.join(LLVM, "llvm-symbolizer")
    if not addrs or not os.path.isfile(sym):
        return text
    inp = "".join("CODE 0x%s\n" % a for _, a in addrs)
    r = subprocess.run([sym, "--obj=" + path, "--no-inlines", "--functions=none"], input=inp,
                       capture_output=True, text=True)
    blocks = r.stdout.split("\n\n")
    for (k, _), blk in zip(addrs, blocks):
        loc = blk.strip("\n")
        # no comment where the table has no line (line 0: code made by the compiler)
        if loc and not loc.startswith("??") and loc.split(":")[-2:-1] != ["0"]:
            # an instruction that opens a block ends its text with the line that closes it: the comment goes there
            while k + 1 < len(lines) and lines[k + 1].startswith(" " * 30) and not INSN_LINE.match(lines[k + 1]):
                k += 1
            lines[k] += "\t\t\t  ## " + loc
    return "\n".join(lines)


def tool_objdump():
    argv = []
    print_dbg = False
    for a in sys.argv[1:]:
        if a == "-print-dbg":
            print_dbg = True
        elif a.startswith("-address-mask="):
            # masks the addresses of the listing's targets; the listing reads the same without it
            continue
        else:
            argv.append(a)
    sys.path.insert(0, os.path.join(ROOT, "common", "lib", "pi32v2-isa"))
    from pi32v2isa import objdump
    files = [a for a in argv if not a.startswith("-") and os.path.isfile(a)]
    if print_dbg and len(files) == 1 and any(a in ("-d", "-D", "-disassemble", "-disassemble-all") for a in argv):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = objdump.main(argv)
        sys.stdout.write(source_comments(files[0], buf.getvalue()))
        sys.exit(rc)
    sys.exit(objdump.main(argv))


# ---- ELF reading (objsizedump, version strings) -------------------------------------------------------------

class Elf:
    def __init__(self, data):
        if data[:4] != b"\x7fELF" or data[4] != 1:
            raise ValueError("not an ELF32 file")
        self.d = data
        (_, _, _, _, _, shoff, _, _, _, _, shentsize, shnum, shstrndx) = struct.unpack_from(
            "<HHIIIIIHHHHHH", data, 16)
        self.sections = []
        for k in range(shnum):
            name, typ, flags, addr, off, size, link, info, align, entsize = struct.unpack_from(
                "<IIIIIIIIII", data, shoff + k * shentsize)
            self.sections.append(dict(name=name, type=typ, flags=flags, addr=addr, off=off, size=size,
                                      link=link, info=info, entsize=entsize))
        strtab = self.sections[shstrndx]
        for s in self.sections:
            s["name"] = self.cstr(strtab["off"] + s["name"])

    def cstr(self, off):
        end = self.d.index(b"\0", off)
        return self.d[off:end].decode("utf-8", "replace")

    def symbols(self):
        for s in self.sections:
            if s["type"] == 2:          # SHT_SYMTAB
                strtab = self.sections[s["link"]]
                for k in range(s["size"] // 16):
                    nm, val, size, info, other, shndx = struct.unpack_from("<IIIBBH", self.d, s["off"] + k * 16)
                    yield dict(name=self.cstr(strtab["off"] + nm), value=val, size=size, bind=info >> 4,
                               type=info & 15, shndx=shndx)

    def section_data(self, s):
        return self.d[s["off"]:s["off"] + s["size"]]


def tool_objsizedump():
    """objsizedump -lite -skip-zero [-enable-dbg-info] ELF: the sized functions and objects, one a line."""
    argv = sys.argv[1:]
    skip_zero = "-skip-zero" in argv
    dbg = "-enable-dbg-info" in argv
    files = [a for a in argv if not a.startswith("-")]
    if "-lite" not in argv:
        die("only -lite is supported")
    status = 0
    for path in files:
        try:
            with open(path, "rb") as f:
                e = Elf(f.read())
        except (OSError, ValueError) as ex:
            sys.stderr.write(f"objsizedump: '{path}': {ex}\n")
            status = 1
            continue
        syms = [s for s in e.symbols() if s["type"] in (1, 2) and 0 < s["shndx"] < 0xFF00
                and not (skip_zero and s["size"] == 0)]
        files_of = source_files(path, e, syms) if dbg else {}
        print("SYMBOL TABLE LITE:")
        for s in syms:
            sec = e.sections[s["shndx"]]["name"]
            line = "%08x %s%s   %s%s %s\t\t %08x %s" % (
                s["value"], "g" if s["bind"] else "l", "w" if s["bind"] == 2 else "-", "-",
                "F" if s["type"] == 2 else "O", sec, s["size"], s["name"])
            if dbg:
                line += " " + files_of.get(id(s), "<invalid>")
            print(line)
    sys.exit(status)


def source_files(path, e, syms):
    """The source file of each symbol (by object identity), from the debug line table: what llvm-symbolizer
    says about the symbol's address. Symbols it knows nothing about are left out."""
    res = {}
    sym = os.path.join(LLVM, "llvm-symbolizer")
    if not any(s["name"] == ".debug_line" for s in e.sections) or not os.path.isfile(sym) or not syms:
        return res
    inp = "".join(("CODE 0x%x\n" if s["type"] == 2 else "DATA 0x%x\n") % s["value"] for s in syms)
    r = subprocess.run([sym, "--obj=" + path, "--functions=none"], input=inp,
                       capture_output=True, text=True)
    blocks = r.stdout.split("\n\n")
    for s, blk in zip(syms, blocks):
        lines = blk.strip("\n").split("\n")
        loc = lines[-1] if lines else ""
        # file:line[:column] (a DATA answer has the name and the extent before it)
        parts = loc.rsplit(":", 2)
        while len(parts) > 1 and parts[-1].isdigit():
            parts.pop()
        f = ":".join(parts)
        if f and f != "??" and not f.startswith("??"):
            res[id(s)] = f
    return res


# ---- version strings -----------------------------------------------------------------------------------------

def version_strings(path):
    """The .sys.version strings of an object or of each member of an archive."""
    with open(path, "rb") as f:
        data = f.read()
    out = []
    if data[:8] == b"!<arch>\n":
        pos = 8
        names = None
        while pos + 60 <= len(data):
            hdr = data[pos:pos + 60]
            size = int(hdr[48:58])
            body = data[pos + 60:pos + 60 + size]
            if body[:4] == b"\x7fELF":
                out += elf_versions(body)
            pos += 60 + size + (size & 1)
    elif data[:4] == b"\x7fELF":
        out += elf_versions(data)
    return out


def elf_versions(data):
    try:
        e = Elf(data)
    except (ValueError, struct.error):
        return []
    out = []
    for s in e.sections:
        if s["name"] == ".sys.version":
            out += [x.decode("utf-8", "replace") for x in e.section_data(s).split(b"\0") if x]
    return out


def tool_read_version():
    for p in sys.argv[1:]:
        if not p.startswith("-"):
            for v in version_strings(p):
                print(v)


def write_version_object(out, inputs):
    # not used by the SDK's builds: the strings, one a line, in a plain file
    with open(out, "w") as f:
        for p in inputs:
            if os.path.isfile(p):
                for v in version_strings(p):
                    f.write(v + "\n")


def tool_link_version():
    argv = sys.argv[1:]
    out = None
    inputs = []
    i = 0
    while i < len(argv):
        if argv[i] == "--output-version-info" and i + 1 < len(argv):
            out = argv[i + 1]
            i += 1
        elif not argv[i].startswith("-"):
            inputs.append(argv[i])
        i += 1
    if out:
        write_version_object(out, inputs)


# ---- dispatch ------------------------------------------------------------------------------------------------

TOOLS = {
    "clang": lambda: tool_clang("clang"), "clang++": lambda: tool_clang("clang++"),
    "cc": lambda: tool_clang("cc"), "cxx": lambda: tool_clang("cxx"),
    "ld": tool_ld, "lto-wrapper": tool_lto_wrapper, "lto-ar": tool_lto_ar, "ar": tool_lto_ar,
    "objdump": tool_objdump, "objsizedump": tool_objsizedump,
    "llvm-read-version": tool_read_version, "link-version": tool_link_version,
}


def main():
    name = os.path.basename(sys.argv[0])
    if name not in TOOLS:
        die(f"unknown tool name (one of {', '.join(sorted(TOOLS))})")
    TOOLS[name]()


if __name__ == "__main__":
    main()
