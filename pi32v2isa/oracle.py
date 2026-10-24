# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""JieLi's toolchain as a black-box oracle (docs/ORACLE.md): feed it bytes or text, read what it does."""

import collections
import hashlib
import itertools
import os
import random
import re
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from . import codec
from .table import ROOT

ORACLE_DIR = ROOT / "oracle"
RELEASES = {   # release -> SHA-256 of jieli-linux-toolchains-<release>.tar.xz (docs/ORACLE.md)
    "20250324.1": "f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958",
    "20260730.1": "a1545cddbc451a06bac43eb5cd96d831470c42a97c5c0b1f98879a20fc7647bd",
}
DEFAULT_RELEASE = "20260730.1"
URL = "https://jl-update.oss-cn-shenzhen.aliyuncs.com/jieli-linux-toolchains-{}.tar.xz"
CPU = "r3"
PAD = b"\x00\x00\x00\x00"   # two nops after each probe: a probe misread as longer cannot swallow the next one
LINE = re.compile(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*)$")
ANNOTATION = re.compile(r"\s+<[^<>]*>$")      # objdump's "<symbol+offset : address >" after a branch target
UNKNOWN = "<unknown instruction>"


class OracleError(Exception):
    pass


def fetch(release=DEFAULT_RELEASE):
    """Download, verify and unpack a toolchain release under oracle/ (git ignores it). Returns its path."""
    if release not in RELEASES:
        raise OracleError(f"unknown release {release}; known: {', '.join(RELEASES)}")
    dest = ORACLE_DIR / f"jieli-linux-toolchains-{release}"
    if dest.is_dir():
        return dest
    ORACLE_DIR.mkdir(exist_ok=True)
    archive = ORACLE_DIR / f"jieli-linux-toolchains-{release}.tar.xz"
    if not archive.exists():
        urllib.request.urlretrieve(URL.format(release), archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != RELEASES[release]:
        archive.unlink()
        raise OracleError(f"{archive.name}: SHA-256 {digest}, expected {RELEASES[release]}")
    with tarfile.open(archive) as tar:
        tar.extractall(ORACLE_DIR, filter="data")
    return dest


class Oracle:
    def __init__(self, release=DEFAULT_RELEASE, path=None):
        self.release = release
        self.path = Path(path or os.environ.get("PI32V2_TOOLCHAIN") or
                         ORACLE_DIR / f"jieli-linux-toolchains-{release}")
        self.clang = self.path / "common" / "bin" / "clang"
        self.objdump = self.path / "common" / "bin" / "objdump"
        if not self.clang.exists():
            raise OracleError(f"no toolchain at {self.path}; run: python3 -m pi32v2isa oracle fetch {release}")

    def origin(self, tool):
        return f"oracle:{tool}:{self.release}"

    def _run(self, args):
        try:
            r = subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:      # the assembler loops on some malformed input
            return 124, "", "timed out after 120 s"
        return r.returncode, r.stdout, r.stderr

    def _assemble(self, source, features=()):
        with tempfile.TemporaryDirectory() as d:
            s, o = Path(d) / "probe.s", Path(d) / "probe.o"
            s.write_text(source)
            flags = [f"-m{f}" for f in features]
            code, _, err = self._run([self.clang, "-target", "pi32v2", f"-mcpu={CPU}", *flags, "-c", s, "-o", o])
            if code:
                return None, err.strip()
            code, out, err = self._run([self.objdump, "-d", f"-mcpu={CPU}", o])
            if code:
                raise OracleError(f"objdump failed: {err.strip()}")
            return out, ""

    @staticmethod
    def _lines(listing):
        """{address: (bytes, text)} from objdump -d output."""
        out = {}
        for ln in listing.splitlines():
            m = LINE.match(ln)
            if m:
                text = m.group(3).strip()
                if text != UNKNOWN:
                    text = ANNOTATION.sub("", text)
                out[int(m.group(1), 16)] = (bytes.fromhex(m.group(2)), text)
        return out

    def decode(self, probes, features=(), pad=PAD):
        """For each byte string, (bytes objdump took as the instruction, its text), or None. Each probe is
        followed by `pad` (nops), so one probe read as longer than it is cannot swallow the next."""
        blob = b"".join(p + pad for p in probes)
        source = "\t.text\n" + "".join(f"\t.byte {', '.join(f'0x{b:02x}' for b in blob[i:i + 16])}\n"
                                       for i in range(0, len(blob), 16))
        listing, err = self._assemble(source, features)
        if listing is None:
            raise OracleError(f"could not assemble probe bytes: {err}")
        lines, out, addr = self._lines(listing), [], 0
        for p in probes:
            out.append(lines.get(addr))
            addr += len(p) + len(pad)
        return out

    def listing(self, data, features=()):
        """objdump's reading of a byte string: [(address, bytes, text)] for every instruction in it."""
        source = "\t.text\n" + "".join(f"\t.byte {', '.join(f'0x{b:02x}' for b in data[i:i + 16])}\n"
                                       for i in range(0, len(data), 16))
        listing, err = self._assemble(source, features)
        if listing is None:
            raise OracleError(f"could not assemble probe bytes: {err}")
        return [(a, b, t) for a, (b, t) in sorted(self._lines(listing).items())]

    def encode(self, texts, features=()):
        """For each assembly text, the bytes JieLi's assembler produced for its first instruction, or an error
        message (str). A text may span several lines (a block with its body); a single line that opens a
        block (`if (r0 == r1) {`) gets a `nop` body and a closing brace, since the assembler fails or never
        returns without one. Only the first instruction's bytes are returned; `}` emits no bytes."""
        blocks = []
        for t in texts:
            lines = t.split("\n")
            if len(lines) == 1 and t.rstrip().endswith("{"):
                lines = [t, "nop", "}"]
            blocks.append(lines)
        source = "\t.text\n" + "".join(f"\t{ln}\n" for b in blocks for ln in b)
        listing, err = self._assemble(source, features)
        if listing is not None:
            got = [b for _, (b, _) in sorted(self._lines(listing).items())]
            counts = [sum(1 for ln in b if ln.strip() != "}") for b in blocks]
            if len(got) == sum(counts):
                out, k = [], 0
                for c in counts:
                    out.append(got[k])
                    k += c
                return out
        if len(texts) == 1:
            return [err or "assembler output did not match the input"]
        return [r for t in texts for r in self.encode([t], features)]   # find which line failed


def compile_c(oracle, source, flags=(), features=()):
    """Compile C source with JieLi's clang for pi32v2 and return objdump's listing of the object, with
    relocations (-r). Black box: C in, the compiler's choice of instructions out. `flags` are extra clang
    flags (e.g. -O2, -Os); `features` become -m<feature>."""
    with tempfile.TemporaryDirectory() as d:
        c, obj = Path(d) / "probe.c", Path(d) / "probe.o"
        c.write_text(source)
        code, _, err = oracle._run([oracle.clang, "-target", "pi32v2", f"-mcpu={CPU}", *flags,
                                    *[f"-m{f}" for f in features], "-c", c, "-o", obj])
        if code:
            raise OracleError(f"compile failed: {err.strip()}")
        code, out, err = oracle._run([oracle.objdump, "-d", "-r", f"-mcpu={CPU}", obj])
        if code:
            raise OracleError(f"objdump failed: {err.strip()}")
        return out


def parse_values(spec):
    """'0,1,4' or '0..15' or '-8..8/4' -> list of ints; other words (register names) are kept as text."""
    out = []
    for part in spec.split(","):
        if ".." in part:
            lo, _, rest = part.partition("..")
            hi, _, step = rest.partition("/")
            out += list(range(int(lo, 0), int(hi, 0) + 1, int(step or "1", 0)))
        else:
            try:
                out.append(int(part, 0))
            except ValueError:
                out.append(part)
    return out


def vary(oracle, template, values, features=()):
    """Assemble a template such as 'r{x} = [r{y}+{n}]' for every combination of the given values.
    Returns [(text, bytes or error message)]. This is how a field's bit positions are found."""
    names = list(values)
    texts = [template.format(**dict(zip(names, combo))) for combo in itertools.product(*values.values())]
    return list(zip(texts, oracle.encode(texts, features)))


def bits(data):
    """'1110000001100100 0001111000000000': the 16-bit words of data, most significant bit first."""
    return " ".join(f"{data[k] | data[k + 1] << 8:016b}" for k in range(0, len(data) - 1, 2))


NUMBER = re.compile(r"(?<![\w])(-?(?:0x[0-9A-Fa-f]+|\d+))(?![\w])")


COMPOUND = re.compile(r"^(\S+) (<<<|>>>|<<|>>|[-+*|^&])= (\S+)(\s+#)?$")
SUB_CONST = re.compile(r"^(\S+) = (\S+) - (\d+)(\s+#)?$")
COMMUTATIVE = re.compile(r"^(\S+) = (\S+) ([+*|^&]) (\S+)(\s+#)?$")


def _canonical(text):
    """A text with its numbers as 32-bit values, `x op= y` written `x = x op y`, and the operands of a
    commutative operation (+ * | ^ &) in sorted order."""
    t = NUMBER.sub(lambda m: str(int(m.group(1), 0) & 0xFFFFFFFF), text)
    m = COMPOUND.match(t)
    if m:
        t = f"{m.group(1)} = {m.group(1)} {m.group(2)} {m.group(3)}{m.group(4) or ''}"
    m = SUB_CONST.match(t)              # x = a - N is x = a + (-N)
    if m:
        t = f"{m.group(1)} = {m.group(2)} + {-int(m.group(3)) & 0xFFFFFFFF}{m.group(4) or ''}"
    m = COMMUTATIVE.match(t)
    if m:
        a, b = sorted((m.group(2), m.group(4)))
        t = f"{m.group(1)} = {a} {m.group(3)} {b}{m.group(5) or ''}"
    return re.sub(r"\s+#$", "  #", t)


def same_meaning(a, b):
    """Texts that say the same thing: numbers compared by their 32-bit value (0xFF and 255, -1 and
    0xFFFFFFFF), `x op= y` the same as `x = x op y`, and `a op b` the same as `b op a` for + * | ^ &."""
    return _canonical(a) == _canonical(b)


def probe_values(insn, limit=4096, wide=6000):
    """Field-value combinations to check: every combination when that is at most `limit`, else the
    extremes, a middle value, each single bit and three irregular values of every field (irregular so that
    a wide constant does not also fit a shorter form). When the product of those candidates is more than
    `wide` (entries with many fields), the candidates are tried one field at a time and in seeded random
    combinations instead. The first combination is all minimum and the last all maximum."""
    widths = {f: len(insn.field_bits(f)) for f in sorted(insn.fields)}
    total = 1
    for w in widths.values():
        total *= 1 << w
    if total <= limit:
        return [dict(zip(widths, combo)) for combo in itertools.product(*[range(1 << w) for w in widths.values()])]
    ranges = [sorted({0, (1 << w) - 1, (1 << w) // 3, *(1 << b for b in range(w)),
                      *((0x9E3779B9 * k) & ((1 << w) - 1) for k in (1, 2, 3))}) for w in widths.values()]
    size = 1
    for r in ranges:
        size *= len(r)
    if size <= wide:
        return [dict(zip(widths, combo)) for combo in itertools.product(*ranges)]
    rng = random.Random(7)
    lo = {f: 0 for f in widths}
    hi = {f: (1 << w) - 1 for f, w in widths.items()}
    picks = [lo] + [{**lo, f: v} for f, r in zip(widths, ranges) for v in r]
    picks += [{f: rng.choice(r) for f, r in zip(widths, ranges)} for _ in range(wide // 2)]
    out, seen = [], set()
    for d in [d for d in picks if d != hi] + [hi]:
        key = tuple(d.items())
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def chosen_examples(insn, values_list):
    """Combinations to record as examples: every field at its minimum, then each field alone at its maximum
    (so swapped or misplaced fields would show), then every field at its maximum."""
    if not insn.fields:
        return values_list[:1]
    lo, hi = values_list[0], values_list[-1]     # probe_values lists ranges in ascending order
    picks = [lo] + [{**lo, f: hi[f]} for f in sorted(insn.fields)] + [hi]
    out = []
    for v in picks:
        if v not in out:
            out.append(v)
    return out


SELF = "(this entry)"


def confirm(oracle, table, insn):
    """Check one entry both ways. Returns (problems, examples, encodings checked, preferred) where examples
    are (bytes, text, origin) and preferred counts the other entries the assembler chose for the same text."""
    values_list = probe_values(insn)
    encodings = [codec.encode(insn, v) for v in values_list]
    texts = [codec.format(insn, v) for v in values_list]
    problems = []
    # a block opener's body is the words after it: pad with more than the longest body (16 words), so the
    # next probe is never inside it
    decoded = oracle.decode(encodings, insn.requires, pad=bytes(34) if insn.body else PAD)
    for data, text, got in zip(encodings, texts, decoded):
        if got is None:
            problems.append(f"decode {data.hex(' ')}: objdump printed nothing at this address")
        elif got[0] != data:
            problems.append(f"decode {data.hex(' ')}: objdump took {got[0].hex(' ')} as one instruction ({got[1]!r})")
        elif got[1] != text:
            problems.append(f"decode {data.hex(' ')}: objdump prints {got[1]!r}, table says {text!r}")
    asm_texts = [codec.format(insn, v, insn.asm_syntax or None) for v in values_list]
    if insn.body:                       # a block whose body length is a field: give it that many nop bytes
        field = insn.fields[insn.body]
        sizes = [codec.value(field, v[insn.body], len(insn.field_bits(insn.body))) for v in values_list]
        asm_texts = [t + "\n" + "nop\n" * (n // 2) + "}" for t, n in zip(asm_texts, sizes)]
    assembled = oracle.encode(asm_texts, insn.requires)
    preferred = collections.Counter()   # other entries the assembler chose for the same text
    out_of_range = []                   # probes with a value the assembler is known to refuse (asm_range)
    for v in values_list:
        bad = False
        for name, f in insn.fields.items():
            if f.asm_range:
                n = codec.value(f, v[name], len(insn.field_bits(name)))
                bad = bad or not f.asm_range[0] <= n <= f.asm_range[1]
        out_of_range.append(bad)
    for data, text, got, refused in zip(encodings, texts, assembled, out_of_range):
        if text in insn.asm_wrong:
            # a known mis-assembly: the bytes must mean something else than the text (an encoding of the
            # same meaning, even a different one, would be right)
            other = None if isinstance(got, str) else codec.decode(table, got)
            if got == data or (other and other[2] == len(got)
                               and same_meaning(codec.format(other[0], other[1]), text)):
                problems.append(f"encode {text!r}: listed in asm_wrong, but the assembler now gets it right")
        elif refused:
            if not isinstance(got, str):
                problems.append(f"encode {text!r}: outside asm_range, but the assembler gives {got.hex(' ')}")
        elif insn.asm_no_syntax or text in insn.asm_rejects:
            if not isinstance(got, str):
                reason = "asm_no_syntax" if insn.asm_no_syntax else "asm_rejects"
                problems.append(f"encode {text!r}: listed in {reason}, but the assembler gives {got.hex(' ')}")
        elif isinstance(got, str):
            problems.append(f"encode {text!r}: assembler error: {got.splitlines()[0] if got else '?'}")
        elif got != data:
            other = codec.decode(table, got)
            if (other and other[2] == len(got) and same_meaning(codec.format(other[0], other[1]), text)):
                if other[0] is not insn:
                    preferred[other[0].id] += 1     # a shorter or equivalent form the table already has
                # else: another encoding of this entry that prints the same text (a modimm has several
                # for one value); the assembler picks one, which is no disagreement
            else:
                problems.append(f"encode {text!r}: assembler gives {got.hex(' ')}, table says {data.hex(' ')}")
    # how often the assembler chose this very entry (informational: an entry it never picks is still
    # checked in the decode direction, and its texts mean the same as what the assembler chose)
    preferred[SELF] = sum(1 for data, got in zip(encodings, assembled) if got == data)
    examples = []
    for v in chosen_examples(insn, values_list):
        tool = "objdump+clang-reject" if insn.asm_no_syntax else "objdump+clang"
        examples.append((codec.encode(insn, v), codec.format(insn, v), oracle.origin(tool)))
    return problems, examples, len(values_list), dict(preferred)


def sweep(oracle, first=None, features=("fprev1",)):
    """Decode every 16-bit word, or every second word after `first`. Returns {word: (length, text)}."""
    words = range(65536)
    if first is None:
        probes = [bytes((w & 0xFF, w >> 8)) for w in words]
    else:
        probes = [bytes((first & 0xFF, first >> 8, w & 0xFF, w >> 8)) for w in words]
    out = {}
    for start in range(0, 65536, 8192):
        for w, got in zip(words[start:start + 8192], oracle.decode(probes[start:start + 8192], features)):
            out[w] = (len(got[0]), got[1]) if got else (0, "")
    return out


def shapes(decoded):
    """Group a sweep by instruction shape (registers -> R, numbers -> N): [(shape, length, words, pattern)],
    largest first. The pattern shows the bits common to all the words ('.' where they differ)."""
    groups = collections.defaultdict(list)
    for w, (n, text) in decoded.items():
        shape = re.sub(r"(?<![\w])-?(?:0x[0-9A-Fa-f]+|\d+)(?![\w])", "N", re.sub(r"\br\d+\b", "R", text))
        groups[(shape, n)].append(w)
    out = []
    for (shape, n), ws in groups.items():
        same, ones = 0xFFFF, 0xFFFF
        for w in ws:
            same &= ~(w ^ ws[0])
            ones &= w
        pattern = "".join(("1" if ones >> b & 1 else "0") if same >> b & 1 else "." for b in range(15, -1, -1))
        out.append((shape, n, ws, pattern))
    return sorted(out, key=lambda x: -len(x[2]))


def compare(oracle, table, obj):
    """Disassemble an object's code sections with the table and with JieLi's objdump, instruction by
    instruction. Needs a stock readelf and objcopy. Returns (counts, differences)."""
    counts, diffs = collections.Counter(), []
    sections = subprocess.run(["readelf", "-SW", str(obj)], capture_output=True, text=True, check=True).stdout
    names = [m.group(1) for ln in sections.splitlines()
             if (m := re.match(r"\s*\[\s*\d+\]\s+(\S+)", ln)) and " AX " in ln]
    _, listing, _ = oracle._run([oracle.objdump, "-d", f"-mcpu={CPU}", obj])
    for name in names:
        part = listing.split(f"Disassembly of section {name}:", 1)
        if len(part) < 2:
            continue
        lines = oracle._lines(part[1].split("Disassembly of section", 1)[0])
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "section.bin"
            subprocess.run(["objcopy", "-I", "elf32-little", "-O", "binary", "-j", name, str(obj), str(out)],
                           check=True)
            data = out.read_bytes()
        for addr, (expect, text) in sorted(lines.items()):
            if text == UNKNOWN:
                counts["unknown to objdump"] += 1
                continue
            got = codec.decode(table, data, addr)
            mine = codec.format(got[0], got[1]) if got else None
            if got and got[2] == len(expect) and mine == text:
                counts["identical"] += 1
            else:
                counts["different" if got else "not in table"] += 1
                diffs.append(f"{obj}:{name}+{addr:x}: {expect.hex(' ')}  objdump {text!r}, table {mine!r}")
    return counts, diffs


def _operand_value(text):
    text = text.strip()
    if text == "":
        return 0
    if re.fullmatch(r"r\d+", text):
        return int(text[1:])
    if text in codec.SR_NAMES:
        return codec.SR_NAMES.index(text)
    return int(text, 0)


def fit(decoded, pattern, split=0):
    """For the words whose text fully matches `pattern` (a regex whose groups are operands: registers,
    numbers or special-register names), group them by the bits in `split` and, per group, report which
    word bits carry which operand. Returns [(pattern, words, complete, [(bit, [(delta, count)])])]:
    flipping `bit` from 0 to 1 changes the operands by `delta` (one number per operand). A group is
    complete when every combination of its varying bits decodes to this shape (no holes)."""
    rx = re.compile(pattern)
    hits = {}
    for w, (n, text) in decoded.items():
        m = rx.fullmatch(text)
        if m:
            try:
                hits[w] = [_operand_value(g or "") for g in m.groups()]
            except ValueError:
                continue
    groups = collections.defaultdict(dict)
    for w, ops in hits.items():
        groups[w & split][w] = ops
    out = []
    for _, ws in sorted(groups.items()):
        first = next(iter(ws))
        same, ones = 0xFFFF, 0xFFFF
        for w in ws:
            same &= ~(w ^ first)
            ones &= w
        pat = "".join(("1" if ones >> b & 1 else "0") if same >> b & 1 else "." for b in range(15, -1, -1))
        roles = []
        for b in range(15, -1, -1):
            if same >> b & 1:
                continue
            deltas = collections.Counter()
            for w, ops in ws.items():
                if not w >> b & 1 and (w | 1 << b) in ws:
                    deltas[tuple(x - y for x, y in zip(ws[w | 1 << b], ops))] += 1
            roles.append((b, deltas.most_common(3)))
        complete = len(ws) == 1 << (16 - bin(same & 0xFFFF).count("1"))
        out.append((pat, len(ws), complete, roles))
    return out


def coverage(oracle, table, lo=0, hi=0xFFFF):
    """Words lo..hi that objdump decodes and the table does not, grouped by shape. Each word is checked
    followed by zero words, so a 32- or 48-bit first word counts as covered when the table decodes it with
    a zero second (and third) word. Returns (decoded by objdump, covered by the table, missing shapes)."""
    decoded = sweep(oracle)
    missing, total, covered = {}, 0, 0
    for w in range(lo, hi + 1):
        n, text = decoded[w]
        if text == UNKNOWN or not n:
            continue
        total += 1
        got = codec.decode(table, bytes((w & 0xFF, w >> 8)) + bytes(4))
        if got and got[2] == n:
            covered += 1
        else:
            missing[w] = (n, text)
    return total, covered, shapes(missing)


def check_examples(oracle, table):
    """A quick regression check: every confirmed entry's recorded examples still decode to their text with
    JieLi's objdump, and their text still assembles to the same bytes (or to another table entry that means
    the same). Much faster than confirming every entry; `confirm` remains the full check."""
    problems = []
    by_features = collections.defaultdict(list)
    for i in table.insns:
        if i.status == "confirmed":
            for x in i.examples:
                by_features[tuple(i.requires)].append((i, x))
    for features, items in by_features.items():
        pad = bytes(34)                 # room for the longest block body
        decoded = oracle.decode([x.bytes for _, x in items], features, pad=pad)
        for (i, x), got in zip(items, decoded):
            if got is None or got[0] != x.bytes or got[1] != x.text:
                problems.append(f"{i.id}: {x.bytes.hex(' ')} now decodes as {got}, example says {x.text!r}")
        unavailable = [(i, x) for i, x in items if i.asm_no_syntax]
        for (i, x), got in zip(unavailable, oracle.encode([x.text for _, x in unavailable], features)):
            if not isinstance(got, str):
                problems.append(f"{i.id}: {x.text!r} now assembles despite asm_no_syntax: {got.hex(' ')}")
        plain = [(i, x) for i, x in items
                 if not i.asm_no_syntax and not i.asm_syntax and not i.body
                 and x.text not in i.asm_rejects and x.text not in i.asm_wrong]
        for (i, x), got in zip(plain, oracle.encode([x.text for _, x in plain], features)):
            if isinstance(got, str):
                problems.append(f"{i.id}: {x.text!r} no longer assembles: {got.splitlines()[0] if got else '?'}")
            elif got != x.bytes:
                other = codec.decode(table, got)
                if not (other and other[2] == len(got) and same_meaning(codec.format(other[0], other[1]), x.text)):
                    problems.append(f"{i.id}: {x.text!r} assembles to {got.hex(' ')}, example says {x.bytes.hex(' ')}")
    return problems
