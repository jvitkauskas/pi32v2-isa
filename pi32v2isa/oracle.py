# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""JieLi's toolchain as a black-box oracle (docs/ORACLE.md): feed it bytes or text, read what it does."""

import hashlib
import itertools
import os
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
LINE = re.compile(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*\t(.*)$")


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
        r = subprocess.run([str(a) for a in args], capture_output=True, text=True)
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
                out[int(m.group(1), 16)] = (bytes.fromhex(m.group(2)), m.group(3).strip())
        return out

    def decode(self, probes, features=()):
        """For each byte string, (bytes objdump took as the instruction, its text), or None."""
        blob = b"".join(p + PAD for p in probes)
        source = "\t.text\n" + "".join(f"\t.byte {', '.join(f'0x{b:02x}' for b in blob[i:i + 16])}\n"
                                       for i in range(0, len(blob), 16))
        listing, err = self._assemble(source, features)
        if listing is None:
            raise OracleError(f"could not assemble probe bytes: {err}")
        lines, out, addr = self._lines(listing), [], 0
        for p in probes:
            out.append(lines.get(addr))
            addr += len(p) + len(PAD)
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
        """For each assembly line, the bytes JieLi's assembler produced, or an error message (str)."""
        listing, err = self._assemble("\t.text\n" + "".join(f"\t{t}\n" for t in texts), features)
        if listing is not None:
            lines = sorted(self._lines(listing).items())
            if len(lines) == len(texts):
                return [b for _, (b, _) in lines]
        if len(texts) == 1:
            return [err or "assembler output did not match the input"]
        return [r for t in texts for r in self.encode([t], features)]   # find which line failed


def probe_values(insn, limit=4096):
    """Field-value combinations to check: every combination when that is at most `limit`, else the
    extremes, a middle value and each single bit of every field."""
    widths = {f: len(insn.field_bits(f)) for f in sorted(insn.fields)}
    total = 1
    for w in widths.values():
        total *= 1 << w
    if total <= limit:
        ranges = [range(1 << w) for w in widths.values()]
    else:
        ranges = [sorted({0, (1 << w) - 1, (1 << w) // 3, *(1 << b for b in range(w))}) for w in widths.values()]
    return [dict(zip(widths, combo)) for combo in itertools.product(*ranges)]


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


def confirm(oracle, table, insn):
    """Check one entry both ways. Returns (problems, examples) where examples are (bytes, text, origin)."""
    values_list = probe_values(insn)
    encodings = [codec.encode(insn, v) for v in values_list]
    texts = [codec.format(insn, v) for v in values_list]
    problems = []
    decoded = oracle.decode(encodings, insn.requires)
    for data, text, got in zip(encodings, texts, decoded):
        if got is None:
            problems.append(f"decode {data.hex(' ')}: objdump printed nothing at this address")
        elif got[0] != data:
            problems.append(f"decode {data.hex(' ')}: objdump took {got[0].hex(' ')} as one instruction ({got[1]!r})")
        elif got[1] != text:
            problems.append(f"decode {data.hex(' ')}: objdump prints {got[1]!r}, table says {text!r}")
    assembled = oracle.encode(texts, insn.requires)
    for data, text, got in zip(encodings, texts, assembled):
        if isinstance(got, str):
            problems.append(f"encode {text!r}: assembler error: {got.splitlines()[0] if got else '?'}")
        elif got != data:
            problems.append(f"encode {text!r}: assembler gives {got.hex(' ')}, table says {data.hex(' ')}")
    examples = []
    for v in chosen_examples(insn, values_list):
        examples.append((codec.encode(insn, v), codec.format(insn, v), oracle.origin("objdump+clang")))
    return problems, examples, len(values_list)
