# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0

import copy
import tempfile
import unittest
from pathlib import Path

from pi32v2isa import oracle, table

SMALL = '''format = 1

[[insn]]
id = "call.r"
syntax = "call {x}"
encoding = ["000000001100xxxx"]
fields = { x = "gpr" }
summary = "s"
status = "documented"
sources = ["kagaimiq-jielie"]

# ---- next ----

[[insn]]
id = "rts"
syntax = "rts"
encoding = ["0000000010000000"]
summary = "s"
status = "documented"
sources = ["kagaimiq-jielie"]
'''


class Recording(unittest.TestCase):
    def test_record_confirmation(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.toml"
            p.write_text(SMALL)
            ex = [(bytes.fromhex("c0 00"), "call r0", "oracle:objdump+clang:x"),
                  (bytes.fromhex("cf 00"), "call r15", "oracle:objdump+clang:x")]
            table.record_confirmation(p, "call.r", ex)
            table.record_confirmation(p, "call.r", ex)          # a second run adds nothing
            text = p.read_text()
            t = table.load(p)
            c = t.by_id("call.r")
            self.assertEqual(c.status, "confirmed")
            self.assertEqual(c.sources, ["kagaimiq-jielie", "oracle"])
            self.assertEqual([x.text for x in c.examples], ["call r0", "call r15"])
            self.assertEqual(t.by_id("rts").status, "documented")
            # the group comment stays in front of the next entry, after the new examples
            self.assertLess(text.index('text = "call r15"'), text.index("# ---- next ----"))
            self.assertLess(text.index("# ---- next ----"), text.index('id = "rts"'))
            self.assertEqual(table.check(t, sources={"kagaimiq-jielie", "oracle"}), [])


class Aliases(unittest.TestCase):
    def test_other_encoding_of_the_same_entry_with_the_same_text_is_no_disagreement(self):
        """A modimm has several raw values for 0; the assembler writes the first, which must not count as a mismatch."""
        from pi32v2isa import codec
        i = table.Insn(id="m", syntax="m {n}", words=["0000000000000000", "0000nnnnnnnnnnnn"], fields={"n": table.Field("modimm", "n")},
                       summary="s", status="guessed", sources=["x"], notes="n")
        t = table.Table(format=1, insns=[i])

        class Fake:
            def decode(self, probes, features=()):
                return [(p, codec.format(i, codec.fields_of(i, p))) for p in probes]

            def encode(self, texts, features=()):
                out = []
                for text in texts:
                    value = int(text.split()[1], 0)
                    raw = next(r for r in range(4096) if codec.modimm(r) == value)    # the first raw value for it
                    out.append(codec.encode(i, {"n": raw}))
                return out

            def origin(self, tool):
                return "oracle:fake"

        problems, _, _, preferred = oracle.confirm(Fake(), t, i)
        self.assertEqual(problems, [])
        self.assertEqual(preferred, {})


class BlockEncoding(unittest.TestCase):
    def test_block_opener_gets_body_and_brace(self):
        """`if (r0 == r1) {` is assembled with a nop body and a closing brace, and the body is dropped from the answer."""
        seen = []

        class Fake(oracle.Oracle):
            def __init__(self):
                pass

            def _assemble(self, source, features=()):
                seen.append(source)
                return ("   0:  10 e8 00 01  \tif (r0 == r1) {\n   4:  00 00  \t\tnop\n"
                        "                  \t}\n   6:  00 00  \tnop\n"), ""

        got = Fake().encode(["if (r0 == r1) {", "nop"])
        self.assertEqual(got, [bytes.fromhex("10 e8 00 01"), bytes.fromhex("00 00")])
        self.assertIn("\tif (r0 == r1) {\n\tnop\n\t}\n\tnop\n", seen[0])


class Probes(unittest.TestCase):
    def setUp(self):
        self.t = table.load()

    def test_exhaustive_when_small(self):
        self.assertEqual(len(oracle.probe_values(self.t.by_id("mov.rr"))), 256)

    def test_reduced_when_large(self):
        i = table.Insn(id="w", syntax="w {a} {b}", words=["aaaaaaaabbbbbbbb"],
                       fields={"a": table.Field("uimm", "a"), "b": table.Field("uimm", "b")},
                       summary="s", status="documented", sources=["x"])
        values = oracle.probe_values(i, limit=100)
        self.assertLess(len(values), 256 * 256)
        for f in ("a", "b"):
            seen = {v[f] for v in values}
            self.assertTrue({0, 255, 1, 2, 4, 8, 16, 32, 64, 128} <= seen)

    def test_wide_entries_stay_small(self):
        """Nine register fields would give millions of combinations; they are sampled, ends first and last."""
        letters = "abcdefghi"
        i = table.Insn(id="w", syntax="w " + " ".join("{%s}" % c for c in letters), words=["aaaabbbbccccdddd", "eeeeffffgggghhhh", "iiii000000000000"],
                       fields={c: table.Field("gpr", c) for c in letters}, summary="s", status="documented", sources=["x"])
        values = oracle.probe_values(i)
        self.assertLess(len(values), 7000)
        self.assertEqual(values[0], {c: 0 for c in letters})
        self.assertEqual(values[-1], {c: 15 for c in letters})
        for c in letters:
            self.assertTrue({0, 1, 2, 4, 8, 15} <= {v[c] for v in values})

    def test_examples_tell_fields_apart(self):
        i = self.t.by_id("mov.rr")
        picks = oracle.chosen_examples(i, oracle.probe_values(i))
        self.assertIn({"x": 15, "y": 0}, picks)
        self.assertIn({"x": 0, "y": 15}, picks)


def _toolchain():
    try:
        return oracle.Oracle()
    except oracle.OracleError:
        return None


@unittest.skipUnless(_toolchain(), "JieLi toolchain not under oracle/ (python3 -m pi32v2isa oracle fetch)")
class Live(unittest.TestCase):
    """Against JieLi's toolchain: every confirmed entry still agrees, and a wrong one is caught."""

    def setUp(self):
        self.o, self.t = _toolchain(), table.load()

    def test_confirmed_entries_agree(self):
        for i in self.t.insns:
            if i.status == "confirmed":
                problems, _, _, _ = oracle.confirm(self.o, self.t, i)
                self.assertEqual(problems, [], i.id)

    def test_swapped_fields_are_caught(self):
        wrong = copy.deepcopy(self.t.by_id("mov.rr"))
        wrong.syntax = "{y} = {x}"
        problems, _, _, _ = oracle.confirm(self.o, self.t, wrong)
        self.assertTrue(any("objdump prints 'r0 = r1'" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
