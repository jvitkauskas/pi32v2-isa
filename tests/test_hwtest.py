# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""The hardware-test pipeline without hardware: a batch builds, and simulated device output analyses back."""

import json
import os
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
import check  # noqa: E402
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
            regs = list(c["in_values"])
            e = analyze.expected(c["text"], c["in_values"])
            if e and e != ("nop",):
                regs[e[0]] = e[1]
            if corrupt and c["id"] == "add.rrr":
                regs[0] ^= 1
            out += struct.pack("<53I", *[regs[15 - slot] for slot in range(16)], c["flags"], c["sp_in"], 0,
                               c["rets_in"], 0, *[0] * 32)
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

    def test_nop_cases_check_sp_and_scratch(self):
        self.simulate()
        records, _, _ = analyze.analyse(self.d)
        nop = records[0]
        self.assertEqual((nop["exit"], nop["sp_out"]), (0, nop["sp_in"]))
        self.assertEqual(nop["mem"], {})

    def test_analysis_keeps_setup_and_readback(self):
        self.simulate()
        c = self.manifest["cases"][-1]
        c.update(before=[{"id": "mov.r_sr", "values": {"s": 3, "r": 8}}], after=[], entry=c["stub"] - 4,
                 model="test.context")
        (self.d / "batch-selftest-000.json").write_text(json.dumps(self.manifest))
        records, problems, _ = analyze.analyse(self.d)
        self.assertFalse(problems)
        for key in ("before", "after", "entry", "model"):
            self.assertEqual(records[-1][key], c[key])

    def test_context_model_overrides_single_instruction_model(self):
        self.simulate()
        records, _, _ = analyze.analyse(self.d)
        rec = records[0]
        rec['model'] = 'test.context'
        def wrong(R, flags, op):
            return {0: R[0] ^ 1}, flags
        def context(R, flags, op):
            return {}, flags
        tab = gen.table.load()
        pats = {rec['batch']: self.manifest['pattern']}
        self.assertEqual(check.check([rec], tab, {'nop': wrong}, pats=pats), {})
        result = check.check([rec], tab, {'nop': wrong, 'test.context': context}, pats=pats)
        self.assertEqual(result['nop']['ok'], 1)

    def test_special_waves_build(self):
        d = Path(tempfile.mkdtemp())
        for wave in ("mem", "stack", "branch", "misc"):
            subprocess.run([sys.executable, str(HW / "gen.py"), str(d), "--wave", wave, "--per-entry", "1"],
                           check=True, capture_output=True)
        self.assertTrue(list(d.glob("batch-branch-*.json")))

    def test_wave_one_selection_is_register_only(self):
        from pi32v2isa import table
        for i in gen.select(table.load(), "1"):
            self.assertFalse(gen.UNSAFE.search(gen.literal(i.syntax)), i.id)
            self.assertNotIn(i.group, {"memory", "stack", "branches", "control", "jumps", "returns", "cache"})


@unittest.skipUnless(shutil.which("cpp"), "needs GNU cpp")
class CustomCases(unittest.TestCase):
    def test_setup_entry_alignment_and_recorded_context(self):
        from pi32v2isa import codec, table
        tab = table.load()
        read = {"id": "mov.r_sr", "values": {"r": 8, "s": 3}}
        setup = {"id": "li.u32", "values": {"r": 0, "n": 0x12345678}}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "custom.json"
            source = [{"id": "mov.sr_r", "values": {"r": 0, "s": 3}, "in": list(range(16)),
                       "force": True, "before": [setup], "after": [read], "misalign": misalign,
                       "model": "test.context"}
                      for misalign in (False, True)]
            path.write_text(json.dumps(source))
            cases = gen.cases_from_file(tab, path)
            image, syms = gen.build_batch(cases, d)
            for n, case in enumerate(cases):
                self.assertEqual(case["model"], "test.context")
                stub, entry = syms[f"hw_stub_{n}"], syms[f"hw_entry_{n}"]
                self.assertEqual(stub % 4, 2 if source[n]["misalign"] else 0)
                self.assertEqual(stub - entry, 6)
                self.assertEqual(image[entry - gen.BASE:stub - gen.BASE], codec.encode(tab.by_id("li.u32"), setup["values"]))
                self.assertEqual(image[stub - gen.BASE + 4:stub - gen.BASE + 8],
                                 codec.encode(tab.by_id("mov.r_sr"), read["values"]))
                rec = {"sp_in": 0x1100, "rets_in": 0, "stub": stub, "entry": entry, "bytes": case["bytes"],
                       "hw_taken": 0, "scratch": 0x1000, "batch": "custom"}
                state = check.State(rec, [0] * 256)
                self.assertEqual(state.load(0x10FC), entry)

    def test_forced_cases_require_single_case_batches(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "forced.json"
            path.write_text(json.dumps([{"id": "ssync", "values": {}, "in": [0] * 16, "force": True}]))
            p = subprocess.run([sys.executable, str(HW / "gen.py"), d, "--cases", str(path)],
                               capture_output=True, text=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("requires --batch 1", p.stderr)
            self.assertFalse(list(Path(d).glob("*.bin")))


class BatchSafety(unittest.TestCase):
    def run_helper(self, mode, last=None):
        """Fake only USB/privileged commands; never invoke a real flasher or sudo in a test."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            state = d / "state"
            state.mkdir()
            if last is not None:
                (state / "LASTSLOT").write_text(last)
            scripts = {
                "lsusb": "exit 0" if mode == "absent" else "echo 'ID 4c4a:8057'",
                "timeout": 'shift 3; exec "$@"',
                "sudo": 'echo called >> "$HWTEST_STATE_DIR/calls"; exit 23',
                "sleep": "exit 0",
            }
            for name, body in scripts.items():
                p = d / name
                p.write_text("#!/bin/sh\n" + body + "\n")
                p.chmod(0o755)
            (d / "run-test.sh").write_text('m-flasher run-ram "one.bin" --addr 0x1c20000\n'
                                           'm-flasher run-ram "two.bin" --addr 0x1c28000\n')
            env = dict(os.environ, PATH=str(d) + os.pathsep + os.environ["PATH"], HWTEST_STATE_DIR=str(state))
            p = subprocess.run(["sh", str(HW / "runstep.sh"), str(d), "test"], env=env,
                               capture_output=True, text=True)
            calls = (state / "calls").read_text().splitlines() if (state / "calls").exists() else []
            return p, calls

    def test_slot_collision_checks_numeric_address(self):
        p, calls = self.run_helper("present", "0x01C20000")
        self.assertEqual(p.returncode, 5)
        self.assertIn("SLOT COLLISION", p.stdout)
        self.assertEqual(calls, [])

    def test_missing_usb_stops_before_upload(self):
        p, calls = self.run_helper("absent")
        self.assertEqual(p.returncode, 4)
        self.assertIn("USB NOT READY", p.stdout)
        self.assertEqual(calls, [])

    def test_hang_stops_before_the_next_batch(self):
        p, calls = self.run_helper("present")
        self.assertEqual(p.returncode, 2)
        self.assertIn("one: HANG", p.stdout)
        self.assertNotIn("two:", p.stdout)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
