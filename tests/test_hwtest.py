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
import fm1app  # noqa: E402
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


@unittest.skipUnless(shutil.which("cpp"), "needs GNU cpp")
class Application(unittest.TestCase):
    """The test application (tools/hwtest/APP.md): package format, batch table, results from a RAM dump."""

    def unweave(self, raw):
        image = b"".join(raw[i * 48:i * 48 + 47] for i in range(20)) + raw[20 * 48:]
        identity = "".join(chr((raw[i * 48 + 47] - i - 1) & 0xFF) for i in range(20) if raw[i * 48 + 47] != 0x7D)
        return identity, image

    def test_enc_matches_the_spec_vectors(self):
        # m-bootloader docs/SPEC.md 5.1: 32 zero bytes
        self.assertEqual(fm1app.enc(bytes(32), 0xFFFF).hex(),
                         "ffdf9f1f1f3e7cf8f0c1a367cebd5b970f1e3c78d183274e9c1913264c983060")
        self.assertEqual(fm1app.enc(bytes(32), 0x980F).hex(),
                         "0f3f7efcd9b264c8b162c48810012346ad5a950b162c79d3a66dfbf6ecf9d3a6")
        self.assertEqual(fm1app.crc16(b"123456789"), 0x31C3)

    def test_package_holds_a_valid_application_area(self):
        d = Path(tempfile.mkdtemp())
        out = d / "probe.fwsc"
        subprocess.run([sys.executable, str(HW / "fm1app.py"), str(out), str(HW / "app" / "probe.S")],
                       check=True, capture_output=True)
        identity, image = self.unweave(out.read_bytes())
        self.assertEqual(identity, "FM-1_901")
        head = fm1app.enc(image[:64], 0xFFFF)
        self.assertEqual(fm1app.crc16(head[2:]), struct.unpack_from("<H", head)[0])
        lst_crc, total, count = struct.unpack_from("<HIH", head, 2)
        self.assertEqual((total, count), (len(image), 1))
        self.assertEqual(fm1app.crc16(image[64:144]), lst_crc)
        entry = fm1app.enc(image[64:144], 0xFFFF)
        _, _, dcrc, _, off, size = struct.unpack_from("<HHHHII", entry)
        flash = image[off:off + size]
        self.assertEqual(entry[64:73], b"flash.bin")
        self.assertEqual(fm1app.crc16(flash), dcrc)
        self.assertEqual(len(flash) % fm1app.SECTOR, 0)
        self.assertEqual(set(flash[:fm1app.BOOT_AREA]), {0xFF})        # M-Flasher leaves the boot area alone
        area = fm1app.area_crypt(flash[fm1app.BOOT_AREA:], 0x980F)
        recs = []
        for k in range(3):
            r = area[32 * k:32 * k + 32]
            recs.append((fm1app.crc16(r[2:]) == struct.unpack_from("<H", r)[0],) + struct.unpack_from("<HIIB", r, 2)
                        + (r[16:].split(b"\0")[0],))
        self.assertEqual((recs[0][2],) + recs[0][4:], (0x02000120, 0x83, b"app_area_head"))   # entry address
        self.assertTrue(recs[0][0] and recs[1][0] and not recs[2][0])  # the table ends after app.bin
        app = (d / "probe.bin").read_bytes()
        self.assertEqual(recs[1][1:6], (fm1app.crc16(app), 0x120, len(app), 0x82, b"app.bin"))
        self.assertEqual(area[0x120:0x120 + len(app)], app)

    def test_app_batches_and_ram_results(self):
        d = Path(tempfile.mkdtemp())
        subprocess.run([sys.executable, str(HW / "gen.py"), str(d), "--wave", "selftest", "--batch", "10", "--app"],
                       check=True, capture_output=True)
        manifests = [json.loads(p.read_text()) for p in sorted(d.glob("batch-*.json"))]
        self.assertGreater(len(manifests), 1)
        self.assertEqual([m["base"] for m in manifests], list(gen.APP_BASES[:len(manifests)]))
        self.assertFalse((d / "run-selftest.sh").exists())
        out = d / "app.fwsc"
        subprocess.run([sys.executable, str(HW / "fm1app.py"), str(out), str(HW / "app" / "driver.S"), str(d / "app.S")],
                       check=True, capture_output=True)
        app = (d / "app.bin").read_bytes()
        exe = fm1app.read_exec((d / "app.elf").read_bytes())
        at = {n: v for n, v, *_ in exe["symbols"] if n}["app_batches"] - 0x02000120
        self.assertEqual(struct.unpack_from("<I", app, at)[0], len(manifests))
        for k, m in enumerate(manifests):
            src, length, base = struct.unpack_from("<III", app, at + 4 + 12 * k)
            image = (d / f"batch-selftest-{k:03d}.bin").read_bytes()
            self.assertEqual((length, base), (len(image), m["base"]))
            self.assertEqual(app[src - 0x02000120:src - 0x02000120 + length], image)
        # results taken from a RAM dump as from .out files: nop cases give back their inputs
        ram = bytearray(0x48000)
        for m in manifests:
            words = []
            for c in m["cases"]:
                words += [*c["in_values"], c["flags"], c["sp_in"], 0, c["rets_in"], 0, *[0] * 32]
            struct.pack_into(f"<{len(words)}I", ram, m["results"] - 0x01C30000, *words)
        records, problems, summary = analyze.analyse(d, (bytes(ram), 0x01C30000))
        self.assertEqual(len(summary), len(manifests))
        self.assertEqual(sum(len(m["cases"]) for m in manifests), len(records))


@unittest.skipUnless(shutil.which('cpp'), 'needs GNU cpp')
class AppExperiments(unittest.TestCase):
    def test_plan_build_and_failed_batch_filter(self):
        import appplan
        import appcollect
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory)
            cases=d/'probe.json'
            cases.write_text(json.dumps([{'id':'csync','values':{},'in':list(range(16)),'force':True}]*2))
            subprocess.run([sys.executable,str(HW/'gen.py'),str(d),'--cases',str(cases),'--batch','1','--app'],
                           check=True,capture_output=True)
            (d/'plan.S').write_text(appplan.plan(d,12345,[1,0],3))
            with self.assertRaises(ValueError):
                appplan.plan(d,12345,[0],3)
            subprocess.run([sys.executable,str(HW/'fm1app.py'),str(d/'app.fwsc'),str(HW/'app/experiment.S'),
                            str(d/'app.S'),str(d/'plan.S')],check=True,capture_output=True)
            exe=fm1app.read_exec((d/'app.elf').read_bytes())
            symbols={n:v for n,v,*_ in exe['symbols'] if n}
            self.assertEqual(symbols['app_entry'],0x02000120)
            self.assertIn('app_vec_127',symbols)
            self.assertLess(len((d/'app.bin').read_bytes()),fm1app.APP_MAX)
            manifests=[json.loads(p.read_text()) for p in sorted(d.glob('batch-*.json'))]
            ram=bytearray(0x4d000)
            struct.pack_into('<12I',ram,0x4c000,0x32504148,2,2,0,0,0,0,0,12345,0,0,0)
            struct.pack_into('<I',ram,0x4c100,3)   # first batch was unfinished at a restart
            struct.pack_into('<I',ram,0x4c200,2)
            m=manifests[1]
            for k,c in enumerate(m['cases']):
                struct.pack_into('<53I',ram,m['results']-0x1c30000+k*212,*c['in_values'],c['flags'],
                                 c['sp_in'],0,c['rets_in'],0,*[0]*32)
            struct.pack_into('<I',ram,0x4c200+252,0x12345678)
            _,extended,_,_=appcollect.collect(d,bytes(ram),12345,64)
            self.assertEqual(extended[1]['samples'][-1],0x12345678)
            self.assertEqual(len(extended[1]['samples']),36)
            _,obs,pats,records=appcollect.collect(d,bytes(ram),12345)
            self.assertEqual([o['status'] for o in obs],[3,2])
            self.assertEqual(len(records),3)
            self.assertEqual(set(pats),{'batch-probe-001'})
            self.assertEqual({r['batch'] for r in records},{'batch-probe-001'})
            with self.assertRaises(ValueError):
                appcollect.collect(d,bytes(ram),99999)

    def test_advanced_profile_builds_with_core_entry(self):
        import appplan
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory)
            cases=d/'probe.json'
            cases.write_text(json.dumps([{'id':'wfe','values':{},'in':list(range(16)),'force':True}]))
            subprocess.run([sys.executable,str(HW/'gen.py'),str(d),'--cases',str(cases),'--batch','1','--app'],
                           check=True,capture_output=True)
            (d/'plan.S').write_text(appplan.plan(d,0x3006,[3],3))
            subprocess.run([sys.executable,str(HW/'fm1app.py'),str(d/'app.fwsc'),str(HW/'app/advanced.S'),
                            str(d/'app.S'),str(d/'plan.S')],check=True,capture_output=True)
            exe=fm1app.read_exec((d/'app.elf').read_bytes())
            symbols={n:v for n,v,*_ in exe['symbols'] if n}
            for name in ('app3_cpu1_entry','app3_cpu1_main','app3_soft','app3_trace'):
                self.assertTrue(0x02000120<=symbols[name]<0x02000120+len((d/'app.bin').read_bytes()))

    def test_dual_profile_links_worker_and_lifecycle_hooks(self):
        import appplan
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory)
            cases=d/'probe.json'
            cases.write_text(json.dumps([{'id':'csync','values':{},'in':list(range(16)),'force':True}]))
            subprocess.run([sys.executable,str(HW/'gen.py'),str(d),'--cases',str(cases),'--batch','1','--app'],
                           check=True,capture_output=True)
            (d/'plan.S').write_text(appplan.plan(d,0x4000,[3],3))
            worker,*_=fm1app.build([HW/'app/peer.S'],d,0x1c78000,0x1c10000)
            worker+=b'\0'*(-len(worker)%4)
            (d/'worker.bin').write_bytes(worker)
            (d/'blob.S').write_text('.section .rodata\n.globl app4_worker_blob\napp4_worker_blob:\n.4byte '+
                                   str(len(worker))+'\n.incbin "'+str(d/'worker.bin')+'"\n')
            for profile in ('dual','dual-persist','dual-reboot'):
                image,entry,*_=fm1app.build([HW/('app/'+profile+'.S'),d/'app.S',d/'plan.S',d/'blob.S'],d,0x1c78000)
                self.assertEqual(entry,0x02000120)
                self.assertIn(worker,image)

    def test_temporal_verifier_rejects_wrong_nesting_and_ack(self):
        import appverify
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory)
            record=dict(batch='probe',id='swi',**{'in':[0]*16},out=[0xfffffff0,0x10,9]+[0]*13,
                        psr_out=6,sp_in=100,sp_out=100,rets_in=200,rets_out=200,exit=0,mem_count=0)
            journal=dict(batch='probe',status=2,handler_count=2,vector=121,emu=0,
                         samples=[1,0,2,4,120,121,377,376]+[0]*12)
            header=[0]*12
            header[2]=1
            (d/'observations.json').write_text(json.dumps([dict(header=header,batches=[journal])]))
            exp={'probe':dict(handler_count=2,trace=[120,121,377,376],samples=[[2,2]],
                              out_values=[[2,9]],delta=[[0,1,30,34]],flags=6,unchanged_frame=True)}
            (d/'expectations.json').write_text(json.dumps(exp))
            def save():
                (d/'results.jsonl').write_text(json.dumps(record)+'\n')
            save()
            self.assertEqual(appverify.verify(d),(1,[]))
            journal['samples'][4:8]=[120,376,121,377]
            (d/'observations.json').write_text(json.dumps([dict(header=header,batches=[journal])]))
            self.assertTrue(any('order' in e for e in appverify.verify(d)[1]))
            record['out'][2]=8
            save()
            self.assertTrue(any('r2:' in e for e in appverify.verify(d)[1]))
