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
            ("and.invbit", {"r": 0, "b": 0}, "r0 &= 4294967294"),
            ("and.invbit", {"r": 7, "b": 31}, "r7 &= 2147483647"),
            ("lsl.rri", {"d": 0, "s": 1, "n": 0}, "r0 = r1 << 32"),
            ("lsl.rri", {"d": 0, "s": 1, "n": 1}, "r0 = r1 << 1"),
            ("shr3.rri", {"d": 7, "s": 0, "n": 31}, "r7 = r0 >>> 31"),
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

    def test_non_linear_immediate_kinds(self):
        """The inverse-bit mask stays 32 bits; wrapped zero follows the field width."""
        invbit = table.Field(kind="invbit", letters="b")
        self.assertEqual(codec.operand(invbit, 14, 5), "4294950911")
        wrapped = table.Field(kind="uimm_zero_max", letters="n")
        self.assertEqual(codec.operand(wrapped, 0, 3), "8")
        self.assertEqual(codec.operand(wrapped, 1, 3), "1")
        self.assertEqual(codec.operand(wrapped, 7, 3), "7")

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

    def test_enum_values(self):
        e = insn(words=["000000000000000x"], fields={"x": {"kind": "enum", "values": [".l", ".h"]}}, syntax="t{x}")
        self.assertEqual(problems(e), [])
        self.assertEqual(codec.format(e, {"x": 1}), "t.h")
        bad = insn(words=["00000000000000xx"], fields={"x": {"kind": "enum", "values": ["a", "b", "c"]}}, syntax="t {x}")
        self.assertTrue(any("needs 4 values" in p for p in problems(bad)))
        stray = insn(words=["000000000000000x"], fields={"x": {"kind": "gpr_lo", "values": ["a"]}}, syntax="t {x}")
        self.assertTrue(any("values apply only to enum" in p for p in problems(stray)))

    def test_modimm_options(self):
        e = insn(words=["00000000nnnnnnnn", "0000nnnn00000000"],
                 fields={"n": {"kind": "modimm", "invert": True}}, syntax="t {n}")
        self.assertEqual(problems(e), [])
        self.assertEqual(codec.format(e, {"n": 0x1F}), "t 0xFFFFFFE0")
        d = insn(words=["000000000000nnnn", "nnnnnnnn00000000"], fields={"n": {"kind": "modimm", "decimal": True}}, syntax="t {n}")
        self.assertEqual(codec.format(d, {"n": 0xB80}), "t 65536")
        self.assertEqual(codec.format(d, {"n": 0xFF | 0x300}), "t 4294967295")
        bad = insn(words=["00000000000000xx"], fields={"x": {"kind": "gpr_lo", "invert": True}}, syntax="t {x}")
        self.assertTrue(any("apply only to modimm" in p for p in problems(bad)))

    def test_pair_regs(self):
        e = insn(words=["000000000000xxxx", "x000000000000000"], fields={"x": "pair_regs"}, syntax="t {x}")
        self.assertEqual(problems(e), [])
        self.assertEqual(codec.format(e, {"x": 0b00101}), "t r2,r3")
        self.assertEqual(codec.format(e, {"x": 0b11010}), "t r13,r12")
        self.assertEqual(codec.format(e, {"x": 0b00011}), "t r1,r1")

    def test_lead_and_zero_as(self):
        e = insn(words=["0000000000000000", "mmmmmmmmmmmmmmmm"],
                 fields={"m": {"kind": "rmask", "lead": "rets"}}, syntax="{{{m}}}")
        self.assertEqual(problems(e), [])
        self.assertEqual(codec.format(e, {"m": 0}), "{rets}")
        self.assertEqual(codec.format(e, {"m": 0x00FF}), "{rets, r7-r0}")
        z = insn(words=["000000000000nnnn"], fields={"n": {"kind": "uimm", "zero_as": 16}}, syntax="t {n}")
        self.assertEqual(problems(z), [])
        self.assertEqual(codec.format(z, {"n": 0}), "t 16")
        self.assertEqual(codec.format(z, {"n": 3}), "t 3")
        bad = insn(words=["00000000000000xx"], fields={"x": {"kind": "simm", "zero_as": 4}}, syntax="t {x}")
        self.assertTrue(any("zero_as applies only to uimm" in p for p in problems(bad)))

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
