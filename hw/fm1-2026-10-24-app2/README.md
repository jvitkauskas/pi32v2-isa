# FM-1 test application, steps 3–4: handlers, watchdog and interrupt delivery

Continuation of [steps 1–2](../fm1-2026-10-24-app/README.md), using the same AC791N FM-1 and m-bootloader
1.2-22e2559. Five applications were assembled/linked with this repository and installed with M-Flasher over
the application area only. No bootloader command, --with-bootloader, or settings wipe was used. The
pre-test backup and requested restoration image are identified by hashes in [backup.json](backup.json).
No vendor binary, flash image or RAM dump is committed.

## Attempts and recovery

**32 batches were attempted: 31 completed, one deliberately unfinished across a watchdog restart.** There
were no unexpected resets, manual recoveries or USB hangs. The intentional stall is a setup test: its csync
probe was not reached and has no invented instruction result. On restart the app marked it unfinished,
skipped it, ran the next batch and returned to download mode. Header starts = 2; the other four applications
each started once. The watchdog uses timeout code 0xB (nominal 2 s in the sources), reset mode, and is
rearmed before each batch and stopped before handover. Its precise timeout was not calibrated.

| Wave / run id | Modes | Completed / attempted | Purpose |
| --- | --- | --- | --- |
| watchdog / 0x2001 | deliberate stall, normal | 1 / 2 | Retained progress and skip/restart |
| traps / 0x2002 | timer for wfe/idle, otherwise normal | 8 / 8 | Trap/event recording handlers |
| controls / 0x2003 | timer throughout | 9 / 9 | Global gates, register variants, priorities |
| pending / 0x2004 | timer, then stopped with pending flag | 4 / 4 | Retention through masking |
| soft / 0x2005 | normal; timer for final wfe | 9 / 9 | All software numbers, event-drain follow-up |

Each batch has two calibration nops and one probe; all 62 calibration records preserve their inputs.
[results.jsonl](results.jsonl) holds 93 records and [patterns.json](patterns.json) their scratch patterns.
[observations.json](observations.json) contains retained headers, completion statuses and last-entry snapshots
with handler counts, vector, EMU_MSG, DBG_MSG, return registers, psr/icfg, entry sp and GPRs.
[attempts.json](attempts.json) keeps exact batch manifests, plan modes/priorities, package/dump SHA-256 values
and host logs. A snapshot is the handler entry state, which can be later than the tested instruction.

The reset plug-in normally disconnects its USB command: the first start returned ENODEV rather than a timeout.
The initial host script stopped at that expected disconnect; execution was not repeated. A successful USB
check and RAM read recovered that run's journal. The corrected script accepts that reset disconnection,
waits for the app's own handover, and checks download mode before uploading the reader. All five apps
returned on their own. A failed handover would stop for operator recovery, not trigger blind upload retries.

## Independent implementation and source facts

The optional [experiment.S](../../tools/hwtest/app/experiment.S) profile includes the existing batch driver
and new [platform.S](../../tools/hwtest/app/platform.S). It owns main/supervisor stacks at 0x01C0D000 and
0x01C0F000, installs all 128 RAM vector pointers, clears old causes, and configures only the interrupt/timer,
debug-reporting and watchdog facilities needed here. No second-core program is started.

Facts were taken from fm1-base's MPL-2.0 chip headers (P33, IRQ fields and TIMER5), the Apache-2.0 AC79 SDK
headers and debug.c (EMU bit 1's illegal-instruction label), and the MIT m-bootloader SPEC (entry, reset,
packaging and retained RAM). Nothing from those implementations was copied. The assembly and Python tools
were written for this repository. SDK libraries, vendor firmware and toolchain binary internals were not used.

TIMER5 is source 63, CON/CNT/PRD at 0x10900/+4/+8. The configuration uses oscillator /4 and period 60000;
no calibrated IRQ latency or exact event count per unit time is claimed. Per-source priority/enable fields
are programmed in the CPU0 ICFG words. Software sources 120..127 are enabled at priority 3. Debug 0,
exception 1 and syscall 2 have recording handlers. Debug returns use an explicit rete/rte continuation,
following the [run-5 lesson](../fm1-2026-10-24-v5/README.md); asynchronous handlers preserve reti, acknowledge
their timer/software cause and use rti. Syscall/exception probes resume at their planned instruction end.

## Trap and event results

| Probe | Observation |
| --- | --- |
| syscall | One vector-2 entry; reti = instruction end; returned normally |
| bkpt | One vector-0 entry; rete = instruction end; rete/rte continuation worked |
| hbkpt | One vector-0 entry; rete = instruction address; explicit skip with rete/rte worked |
| btbclr | One vector-1 entry, EMU_MSG 0x2, DBG_MSG 0: illegal-instruction cause in this context |
| sevg | Completed with no handler entry |
| wfe | Completed with no handler entry despite an armed timer |
| idle | Completed with one TIMER5/vector-63 entry, no restart |
| swi 0..7 | Each delivered exactly one entry at vector 120+n; ILAT_CLR bit n acknowledged it |

All completed probes above preserve GPRs, low flags, sp and rets in this recording-handler environment.
The debug handler leaves two scratch words below the exit frame (saved flags/r0); the other trap/event cases
leave case scratch unchanged. The numerical model is named `app2.trap`: it describes this handler context,
not a claim that a trapping instruction is a bare nop. Vector/cause assertions are checked independently.

`btbclr`'s entry is delayed into the runner exit, consistent with run 5's delayed exception. The recorded
cause now identifies an illegal instruction; it does not demonstrate a branch-buffer operation or exclude
an untested enabling mode. Its table encoding, syntax and status are unchanged. No `hw = resets` is added:
the application handler successfully acknowledges the cause and continues.

The second wfe case explicitly executes sevl then wfe before the main wfe. It also completes with zero
handler entries. Blocking, consumption and global/other-core event delivery remain open; these observations
do not justify classifying wfe as a nop in every context. `idle` now has a successful interrupt-enabled
capture, so 774 of 803 non-parallel forms have results across the runs; 29 retain only failure observations.

## Timer gates and priorities

The case programs sample the retained handler counter. Wait loops bound the observation periods but do not
claim exact elapsed microseconds. Values below are the captured counts, not predictions from loop timing.

| Case | Before / held / released counts | Result |
| --- | --- | --- |
| cli | 0 / 0 / 3 | Bit 9 off blocks delivery; sti releases it |
| cli.r | 0 / 0 / 3 | Same; r12 receives old icfg with both enable bits set |
| sti | 0 / — / 3 | Releases the previously held source |
| sti.r, bit 9 set | 0 / — / 3 | Enables delivery |
| sti.r, operand zero | 0 / 0 / 3 | Keeps delivery blocked until explicit enable |
| icfg bit 8 cleared, bit 9 set | 0 / 0 / 3 | Independent gate; setting bit 8 releases delivery |
| sti with bit 8 clear | 0 / 0 / 3 | Setting bit 9 alone does not bypass bit 8 |
| priority 0 / priority 7 | 0 → 1 each | Both deliver in the tested main context |

Priority-3 entries record icfg 0x033F0208; priorities 0 and 7 record 0x003F0201 and 0x073F0280. These are
measured contexts, not a general formula for every icfg field. Nested IRQs, masked software interrupts and
other current-context priority combinations were not tested.

The follow-up removes the ambiguity of future timer periods: while delivery is masked, read CON = 0x8019
(pending), stop the timer by writing 0x18 without acknowledgement, then enable both global bits. For cli,
cli.r, sti.r with zero, and bit-8 clearing, counts are **0 / 0 / 1**. The one serviced pending interrupt
clears the flag; the sampled stopped CON is 0x18. Thus both gates hold an asserted timer pending rather than
discarding it. Multiple future periods cannot explain that final entry because the timer was stopped.

## Reproduction and checking

For example, before installing anything, generate and package the pending wave:

```sh
python3 tools/hwtest/gen.py DIR --cases hw/fm1-2026-10-24-app2/pending.json --batch 1 --app
python3 tools/hwtest/appplan.py DIR --run-id 0x2006 --modes 2,2,2,2 --priority 3
python3 tools/hwtest/fm1app.py DIR/app.fwsc tools/hwtest/app/experiment.S DIR/app.S DIR/plan.S
```

Use a fresh run id for every new attempt. Stage reset.bin and reader.bin at 0x01C28000, as described in
[APP.md](../../tools/hwtest/APP.md); runapp.sh's flash loader occupies 0x01C20000. The reader fetches
0x01C30000..0x01C7CFFF, including journals. The full dump remains outside the repo. Collect it with:

```sh
python3 tools/hwtest/appcollect.py DIR RAM.bin RESULTS_DIR --run-id 0x2006
python3 tools/hwtest/appverify.py hw/fm1-2026-10-24-app2
python3 tools/hwtest/check.py hw/fm1-2026-10-24-app2/results.jsonl --missing
```

appcollect rejects an unrelated run id and excludes every unfinished batch before calibrating/analyzing.
appverify checks 32 per-batch expectations: status, tags/causes, relative counter samples, pending bits and
handover completeness. Numeric single-instruction checking deliberately leaves the timing-dependent control
programs unmodeled; their masking/pending relations are validated by appverify rather than exact timing fits.

Validation passed: `python3 -m pi32v2isa check` reports 1,165 entries and zero problems;
`python3 -m unittest discover -s tests` runs 136 tests successfully (one skipped); `check.py` passes on all
21 `hw/*/*.jsonl` files. `appverify.py` checks 32 batches with zero problems. The evidence audit matches
31 completed batches, 93 records and every scratch pattern; the one unfinished batch has no outputs.
A table-field audit permits only behavior summaries/notes/sources/hw and confirms that no encoding, syntax,
field, example or encoding status changed. No hw key was changed by this run.

## Firmware restoration

The specified backup is `/home/julius/backups/hwapp/fm1-20261025-005103.bin`, SHA-256
`852607102a3a867d1afe4eb20d969c1c323a1c4ef908eb5b823e9ffb870b7f73`.
The pre-test backup has identical bytes outside the application area. A package made from the requested
backup was installed after the test commit. The first package used the stock 0x93000 boundary and
M-Flasher refused it before writing: the requested backup has three application files ending at physical
0xA8071. Their file CRCs were checked, and the complete application was repackaged through sector boundary
0xA9000. Its allowed range is 0x4000..0xA8FFF; actual writes were 19 sectors, 0x04000..0x16FFF, all verified
by M-Flasher. Both restore attempts and logs are recorded in backup.json. A full flash readback
(`/home/julius/backups/hwapp/fm1-20261025-013934.bin`) is byte-for-byte identical to the requested backup,
including the bootloader and every byte outside the application area. The restored application was then
started successfully: USB `4c4a:c755` (FM-1). `/tmp/hw/LASTSLOT` was cleared after that confirmed reset.
The test-application commit preceded restoration; this final metadata update records its verification.
