# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0

import copy
import os
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
            def decode(self, probes, features=(), pad=oracle.PAD):
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


class NoAssemblerSyntax(unittest.TestCase):
    def setUp(self):
        from pi32v2isa import codec
        self.i = table.Insn(id="unknown", syntax="unknown {n}", words=["000000000000000n"],
                            fields={"n": table.Field("uimm", "n")}, summary="s", status="confirmed",
                            sources=["oracle"], asm_no_syntax=True,
                            examples=[table.Example(bytes((n, 0)), f"unknown {n}",
                                                    "oracle:objdump+clang-reject:fake") for n in range(2)])
        self.t = table.Table(format=1, insns=[self.i])
        outer = self

        class Fake:
            accepts = False
            wrong_decode = False

            def decode(self, probes, features=(), pad=oracle.PAD):
                return [(p, "wrong" if self.wrong_decode else codec.format(outer.i, codec.fields_of(outer.i, p)))
                        for p in probes]

            def encode(self, texts, features=()):
                return [bytes(2) if self.accepts else "refused" for _ in texts]

            def origin(self, tool):
                return f"oracle:{tool}:fake"

        self.o = Fake()

    def test_confirmation_checks_decode_and_rejection(self):
        problems, examples, count, _ = oracle.confirm(self.o, self.t, self.i)
        self.assertEqual(problems, [])
        self.assertEqual(count, 2)
        self.assertTrue(all(x[2] == "oracle:objdump+clang-reject:fake" for x in examples))
        self.o.accepts = True
        self.assertTrue(any("asm_no_syntax" in p for p in oracle.confirm(self.o, self.t, self.i)[0]))
        self.o.accepts = False
        self.o.wrong_decode = True
        self.assertTrue(any("objdump prints" in p for p in oracle.confirm(self.o, self.t, self.i)[0]))

    def test_recorded_examples_keep_checking_rejection(self):
        self.assertEqual(oracle.check_examples(self.o, self.t), [])
        self.o.accepts = True
        self.assertTrue(any("asm_no_syntax" in p for p in oracle.check_examples(self.o, self.t)))


class AlwaysPreferredAlias(unittest.TestCase):
    def test_every_probe_may_choose_an_equivalent_entry(self):
        from pi32v2isa import codec
        base = table.Insn(id="base", syntax="t {n}", words=["000000000000000n"],
                          fields={"n": table.Field("uimm", "n")}, summary="s", status="guessed", sources=["oracle"])
        alias = copy.deepcopy(base)
        alias.id, alias.words = "alias", ["100000000000000n"]
        t = table.Table(format=1, insns=[base, alias])

        class Fake:
            wrong = False

            def decode(self, probes, features=(), pad=oracle.PAD):
                return [(p, codec.format(alias, codec.fields_of(alias, p))) for p in probes]

            def encode(self, texts, features=()):
                return [codec.encode(base, {"n": int(text.split()[1]) ^ self.wrong}) for text in texts]

            def origin(self, tool):
                return "oracle:fake"

        o = Fake()
        problems, _, count, preferred = oracle.confirm(o, t, alias)
        self.assertEqual(problems, [])
        self.assertEqual(preferred, {"base": count})
        o.wrong = True
        self.assertTrue(any("assembler gives" in p for p in oracle.confirm(o, t, alias)[0]))


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


    def test_multi_line_text_returns_its_first_instruction(self):
        """A text with a body (`rep r1 {` + nops + `}`) yields only the opener's bytes."""
        class Fake(oracle.Oracle):
            def __init__(self):
                pass

            def _assemble(self, source, features=()):
                return ("   0:  11 03  \trep 4 r1 {\n   2:  00 00  \t\tnop\n   4:  00 00  \t\tnop\n"
                        "              \t}\n   6:  80 00  \trts\n"), ""

        got = Fake().encode(["rep r1 {\nnop\nnop\n}", "rts"])
        self.assertEqual(got, [bytes.fromhex("11 03"), bytes.fromhex("80 00")])


class Meaning(unittest.TestCase):
    def test_equivalent_spellings(self):
        same = [("r1 += r2", "r1 = r1 + r2"), ("r8 += r0  #", "r8 = r0 + r8  #"), ("r0 <<= r0  #", "r0 = r0 << r0  #"),
                ("r1 = 0xFF", "r1 = 255"), ("r1 |= r2", "r1 = r2 | r1"), ("r1 = -1", "r1 = 0xFFFFFFFF")]
        differ = [("r1 = r2 - r3", "r1 = r3 - r2"), ("r1 -= r2", "r1 = r2 - r1"), ("r1 = r2 << r3", "r1 = r3 << r2"),
                  ("r1 += r2", "r1 += r2  #")]
        for a, b in same:
            self.assertTrue(oracle.same_meaning(a, b), (a, b))
        for a, b in differ:
            self.assertFalse(oracle.same_meaning(a, b), (a, b))


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

    def test_examples_still_agree(self):
        """Every confirmed entry's examples, both ways (seconds)."""
        self.assertEqual(oracle.check_examples(self.o, self.t), [])

    @unittest.skipUnless(os.environ.get("PI32V2_LIVE_ALL"), "full confirm of every entry takes about an hour; set PI32V2_LIVE_ALL=1")
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
