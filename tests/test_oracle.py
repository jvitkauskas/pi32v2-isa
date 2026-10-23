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
