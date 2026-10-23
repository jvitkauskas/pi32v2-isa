# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0

import copy
import re
import unittest

from pi32v2isa import codec, table
from pi32v2isa.table import Example, Insn, Table

SOURCES = {"kagaimiq-jielie", "oracle"}


def insn(**kw):
    base = dict(id="t", syntax="t", words=["0000000000000000"], fields={}, summary="s",
                status="documented", sources=["kagaimiq-jielie"])
    base.update(kw)
    base["fields"] = {k: table._field(k, v) for k, v in base["fields"].items()}
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
                self.assertIsNone(re.search(r"\{\+?[a-z]\}", codec.format(i, values)), i.id)

    def test_known_encodings(self):
        """Byte order and field placement, worked by hand from the documented patterns."""
        call = self.t.by_id("call.r")
        self.assertEqual(codec.encode(call, {"x": 5}), bytes.fromhex("c5 00"))
        self.assertEqual(codec.format(call, {"x": 5}), "call r5")
        mov = self.t.by_id("mov.rr")
        self.assertEqual(codec.encode(mov, {"x": 1, "y": 2}), bytes.fromhex("21 16"))
        self.assertEqual(codec.format(mov, {"x": 1, "y": 2}), "r1 = r2")


    def test_kinds_print_like_objdump(self):
        """Each kind's printing, against texts JieLi's objdump printed in the sweeps."""
        t = self.t
        cases = [
            ("ld.w.sp", {"r": 1, "n": 0}, "r1 = [sp]"),                 # {+n} drops a zero offset
            ("ld.w.sp", {"r": 13, "n": 49}, "r13 = [sp+196]"),
            ("ld.bu", {"d": 4, "b": 4, "n": 21}, "r4 = b[r4+-11] (u)"),
            ("li.neg5", {"r": 1, "n": 0}, "r1 = -32"),
            ("li.modimm", {"r": 1, "n": 0x101}, "r1 = 0x10001"),
            ("li.modimm", {"r": 1, "n": 0xB80}, "r1 = 0x10000"),
            ("or.bit", {"r": 1, "b": 14}, "r1 |= 16384"),
            ("pop.rl", {"l": 2}, "{r3, r2} = [sp++]"),
            ("pop.rl", {"l": 6}, "{r6-r4} = [sp++]"),
            ("push.rmask", {"m": 0b110110}, "[--sp] = {r5, r4, r2, r1}"),
            ("push.rmask", {"m": 0x0F0F}, "[--sp] = {r11-r8, r3-r0}"),
            ("push.srmask", {"m": 0x782F}, "[--sp] = {sp, ssp, usp, icfg, psr, rets, retx, rete, reti}"),
            ("pop.srl", {"m": 0}, "{} = [sp++]"),
            ("mov.r_sr", {"r": 1, "s": 7}, "r1 = uspn"),
        ]
        for insn_id, values, text in cases:
            self.assertEqual(codec.format(t.by_id(insn_id), values), text)

    def test_split_field_order(self):
        """li.u32 keeps the low half first in memory."""
        i = self.t.by_id("li.u32")
        self.assertEqual(codec.encode(i, {"r": 3, "n": 0x01C07F00}), bytes.fromhex("c3 ff 00 7f c0 01"))


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
        self.assertTrue(any("belongs to no field" in p for p in problems(e)))
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
