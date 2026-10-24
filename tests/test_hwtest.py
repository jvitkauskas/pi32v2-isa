# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""The hardware-test pipeline without hardware: a batch builds, and simulated device output analyses back."""

import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HW = Path(__file__).resolve().parent.parent / "tools" / "hwtest"
sys.path.insert(0, str(HW))
import analyze  # noqa: E402
import gen  # noqa: E402


@unittest.skipUnless(shutil.which("cpp"), "needs GNU cpp")
class Pipeline(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        subprocess.run([sys.executable, str(HW / "gen.py"), str(self.d), "--wave", "selftest", "--per-entry", "4"],
                       check=True, capture_output=True)
        self.manifest = json.loads((self.d / "batch-selftest-000.json").read_text())

    def simulate(self, corrupt=False):
        """Write the .out the runner would produce, with the registers in reversed stack order (slot 0 holds r15),
        so the analysis has to find the order from the nop cases."""
        out = bytearray()
        for c in self.manifest["cases"]:
            regs = list(c["in"])
            e = analyze.expected(c["text"], c["in"])
            if e and e != ("nop",):
                regs[e[0]] = e[1]
            if corrupt and c["id"] == "add.rrr":
                regs[0] ^= 1
            out += struct.pack("<17I", *[regs[15 - slot] for slot in range(16)], c["flags"])
        (self.d / "batch-selftest-000.out").write_bytes(bytes(out))

    def test_image_fits_and_starts_with_the_entry(self):
        image = (self.d / "batch-selftest-000.bin").read_bytes()
        base = self.manifest["base"]
        self.assertIn(base, gen.SLOTS)
        self.assertLess(base + len(image), base + gen.SLOT_SIZE)
        self.assertLessEqual(self.manifest["results"] + self.manifest["length"], base + gen.SLOT_SIZE)
        self.assertEqual(self.manifest["cases"][0]["id"], "nop")
        self.assertIn("run-ram", (self.d / "run-selftest.sh").read_text())

    def test_simulated_results_analyse(self):
        self.simulate()
        records, problems, summary = analyze.analyse(self.d)
        self.assertEqual(problems, [])
        self.assertEqual(len(records), len(self.manifest["cases"]))
        self.assertIn("as expected", summary[0])
        self.assertIn(str(list(range(15, -1, -1))), summary[0])          # the order the nop cases revealed

    def test_a_wrong_result_is_reported(self):
        self.simulate(corrupt=True)
        _, problems, _ = analyze.analyse(self.d)
        self.assertTrue(problems)

    def test_wave_one_selection_is_register_only(self):
        from pi32v2isa import table
        for i in gen.select(table.load(), "1"):
            self.assertFalse(gen.UNSAFE.search(gen.literal(i.syntax)), i.id)
            self.assertNotIn(i.group, {"memory", "stack", "branches", "control", "jumps", "returns", "cache"})


if __name__ == "__main__":
    unittest.main()
