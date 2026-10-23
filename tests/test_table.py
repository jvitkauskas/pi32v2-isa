# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0

import copy
import unittest

from pi32v2isa import codec, table
from pi32v2isa.table import Example, Insn, Table

SOURCES = {"kagaimiq-jielie", "oracle"}


def insn(**kw):
    base = dict(id="t", syntax="t", words=["0000000000000000"], fields={}, summary="s",
                status="documented", sources=["kagaimiq-jielie"])
    base.update(kw)
    return Insn(**base)


def problems(*insns):
    return table.check(Table(format=1, insns=list(insns)), sources=SOURCES)


class RealTable(unittest.TestCase):
    def setUp(self):
        self.t = table.load()

    def test_consistent(self):
        self.assertEqual(table.check(self.t), [])

    def test_round_trip(self):
        """Every entry encodes and decodes back to itself, at the extremes of each field."""
        for i in self.t.insns:
            widths = {f: len(i.field_bits(f)) for f in i.fields}
            for pick in (lambda w: 0, lambda w: (1 << w) - 1, lambda w: (1 << w) // 3):
                values = {f: pick(w) for f, w in widths.items()}
                data = codec.encode(i, values)
                got = codec.decode(self.t, data)
                self.assertIsNotNone(got, i.id)
                self.assertIs(got[0], i)
                self.assertEqual(got[1], values, i.id)
                self.assertEqual(got[2], len(data))
                self.assertNotIn("{", codec.format(i, values))

    def test_known_encodings(self):
        """Byte order and field placement, worked by hand from the documented patterns."""
        call = self.t.by_id("call.r")
        self.assertEqual(codec.encode(call, {"x": 5}), bytes.fromhex("c5 00"))
        self.assertEqual(codec.format(call, {"x": 5}), "call r5")
        mov = self.t.by_id("mov.rr")
        self.assertEqual(codec.encode(mov, {"x": 1, "y": 2}), bytes.fromhex("21 16"))
        self.assertEqual(codec.format(mov, {"x": 1, "y": 2}), "r1 = r2")


class Checks(unittest.TestCase):
    def test_overlap(self):
        a = insn(id="a", words=["000000001100xxxx"], fields={"x": "gpr"}, syntax="a {x}")
        b = insn(id="b", words=["0000000011000101"])
        self.assertIn("a and b: encodings overlap", problems(a, b))

    def test_prefix_overlap_across_lengths(self):
        a = insn(id="a", words=["0000000000000000"])
        b = insn(id="b", words=["0000000000000000", "xxxxxxxxxxxxxxxx"], fields={"x": "uimm"}, syntax="b {x}")
        self.assertIn("a and b: encodings overlap", problems(a, b))

    def test_field_width(self):
        e = insn(words=["0000000000000xxx"], fields={"x": "gpr"}, syntax="t {x}")
        self.assertTrue(any("needs [4]" in p for p in problems(e)))

    def test_field_without_kind_or_syntax(self):
        e = insn(words=["000000000000xxxx"], fields={}, syntax="t")
        self.assertTrue(any("has no kind" in p for p in problems(e)))
        e = insn(words=["000000000000xxxx"], fields={"x": "gpr"}, syntax="t")
        self.assertTrue(any("never appears in syntax" in p for p in problems(e)))

    def test_unknown_source_and_status(self):
        e = insn(sources=["nowhere"], status="maybe")
        p = problems(e)
        self.assertTrue(any("unknown source" in x for x in p))
        self.assertTrue(any("unknown status" in x for x in p))

    def test_confirmed_needs_observations(self):
        e = insn(status="confirmed", sources=["kagaimiq-jielie"])
        self.assertTrue(any("confirmed, but no oracle" in p for p in problems(e)))

    def test_confirmed_needs_field_coverage(self):
        e = insn(status="confirmed", sources=["oracle"], words=["000000001100xxxx"], fields={"x": "gpr"},
                 syntax="call {x}", examples=[Example(bytes.fromhex("c5 00"), "call r5", "oracle:objdump:x")])
        self.assertTrue(any("fewer than 2 values" in p for p in problems(e)))
        e2 = copy.deepcopy(e)
        e2.examples.append(Example(bytes.fromhex("c0 00"), "call r0", "oracle:objdump:x"))
        self.assertEqual(problems(e2), [])

    def test_example_text_must_match(self):
        e = insn(words=["000000001100xxxx"], fields={"x": "gpr"}, syntax="call {x}",
                 examples=[Example(bytes.fromhex("c5 00"), "call (r5)", "oracle:objdump:x")])
        self.assertTrue(any("prints 'call r5'" in p for p in problems(e)))


if __name__ == "__main__":
    unittest.main()
