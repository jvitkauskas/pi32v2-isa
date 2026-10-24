# FM-1 application run 3: waits, software IRQ nesting and a second core

Continuation of [app2](../fm1-2026-10-24-app2/README.md), on the same AC791N FM-1 and m-bootloader
1.2-22e2559. Eight own applications were built with this repository's assembler/linker and installed
with M-Flasher over the application area only. The initial full-flash backup matches the requested
restoration image; [backup.json](backup.json) identifies both. No bootloader command, --with-bootloader,
settings wipe, or write outside the application area was requested. No firmware, RAM dump or vendor
binary is committed.

## Attempts and evidence

**60 batches were attempted: 59 completed, one was unfinished across a watchdog restart.** There were no
USB hangs or manual recoveries. The unfinished batch is synchronized 008: idle with both global IRQ
gates disabled. The watchdog restarted the app, which marked that batch unfinished, skipped it and
returned to download mode. It has no instruction outputs, including no calibration outputs. All other
applications started once; synchronized started twice. A watchdog reset is a bounded failure to complete,
not evidence that idle intrinsically resets the chip.

| Wave / run id | Completed / attempted | Purpose |
| --- | --- | --- |
| events / 0x3001 | 9 / 9 | WFE sequences, initial timing, masked software requests |
| nesting / 0x3002 | 9 / 9 | Two software sources, priority/gate combinations and entry/exit order |
| cores / 0x3003 | 8 / 8 | First CPU1 startup and attempted per-batch restarts |
| synchronized / 0x3004 | 8 / 9 | Independent counter, barriers, IDLE and WFE controls |
| cores-restart / 0x3005 | 8 / 8 | Separate CPU1 control writes; restarts still unreliable |
| core-sequence / 0x3006 | 1 / 1 | Eight commands after one successful CPU1 startup |
| copex-app / 0x3007 | 8 / 8 | Controlled prior modes in an owned application context |
| copex-repeat / 0x3008 | 8 / 8 | Repeat the complete copex sequence after software reset |

“Completed” means the main batch returned and its journal reached status 2. It does **not** imply that a
second-core setup succeeded. Of 17 attempted CPU1 releases, four reached its ready marker and thirteen
bounded startup polls expired. Those failures and one unexpected handler entry are described below;
they are not positive event-delivery observations.

[results.jsonl](results.jsonl) has 177 format-2 records: 59 probes and 118 calibration nops. All calibration
nops preserve their inputs. [patterns.json](patterns.json) holds their scratch patterns.
[observations.json](observations.json) retains the header and per-batch journal, including unfinished status,
handler counts, causes and last-entry frames. [attempts.json](attempts.json) contains every attempted
manifest, image/package/dump SHA-256, plan, own profile source snapshot and install/start/read/USB logs.
The snapshots preserve the profile revisions used during the run; rebuilding every wave with only the
final profile would not reproduce every image. The desktop working directory is ~/pi32v2-hw-app3;
binaries and dumps stay there and under /tmp/fm1-app3, outside the repo.

The reset plug-in uses RAM slot 0x01C28000 and normally disconnects its USB command. Each start was
followed by a successful bounded USB download-mode check before the retained-RAM reader was uploaded.
The reader also occupies 0x01C28000; M-Flasher's native install/backup loader uses 0x01C20000. LASTSLOT
was tracked for these uploads and cleared after confirmed resets. No failed handover was retried.

## Own implementation and source facts

The original experiment profile remains available. [advanced.S](../../tools/hwtest/app/advanced.S)
adds [advanced-platform.S](../../tools/hwtest/app/advanced-platform.S) through optional hooks in platform.S.
Its software handlers save reti and entry icfg before opening interrupt gates, acknowledge the request,
record depth and entry/exit tokens, restore the outer state, and return through rti. The ordinary app2
profile is unchanged when the hooks are disabled. Main/supervisor stacks remain 0x01C0D000/0x01C0F000;
the CPU1 experiment uses 0x01C12000/0x01C14000 and keeps interrupts disabled on that core.

The additional facts came from fm1-base's MPL-2.0 fm1_cpu1.h/.S and fm1_time.h, and the Apache-2.0 AC79
SDK csfr.h and debug.c: CPU1's entry word is 0x01C7FFF8; SYS_DIV bit 3 participates in starting it;
C1_CON is at 0x01EEE004; the existing stop path clears bit 3 and sets bit 1, and startup sets bit 3 then
clears bit 1. These are source facts, not proof that our per-batch restart sequence is sufficient.
TIMER4 is at 0x10800, independent of TIMER5 at 0x10900. No code or source wording was copied. The entry,
retained-RAM, download marker, package and reset facts remain those of the MIT m-bootloader SPEC;
watchdog, timer and IRQ facts used in app2 remain in effect. SDK libraries and toolchain binary internals
were not consulted.

Journal words +112/+116/+120/+124 are nesting-gate selection, current depth, maximum depth and trace
length. +128..188 hold up to sixteen tokens: vector on entry, vector+256 on exit. A depth-2 nesting is
therefore independently visible as 120,121,377,376. A deferred child gives 120,376,121,377.

The CPU1 mailbox is 0x01C7CE00, within the already validated retained area. Its sixteen words are ready,
command, acknowledged command, completed-command count, reserved, saved SYS_DIV, sampled old C1_CON,
cnum, wait-entered marker, completion marker, and six caller-owned samples. After applying the CPU1 stop controls the
advanced profile copies these words into that batch's journal +112..175. A failed startup leaves no such
snapshot; the main case's r8=0 records the missing ready marker. Zero in the cnum mailbox after a failed
start is not a measured core number. Core restart remains experimental; the successful event sequence
uses one startup, not a restart between commands.

## Waits: WFE is nonblocking here, IDLE has a measurable wait

The initial events wave times with TIMER5 itself. Immediate readback following idle gives r10=0 while
the final journal counts one timer handler. This is insufficient to order the wait and that readback.
The follow-up uses an independent, long-period TIMER4, csync around the interval, and 32 nops before
reading the end counter. TIMER5, when enabled, has period 60000; both counters use CON=0x4019.
Only counter ticks and relative intervals are claimed, not calibrated microseconds or IRQ latency.

| Synchronized case | Configuration | TIMER4 end minus start | Handler count |
| --- | --- | ---: | ---: |
| 000 | csync control, no IRQ, gates off | 1 | 0 |
| 001 | 128 WFE, no IRQ, gates off | 3 | 0 |
| 002 | SEVL then 128 WFE, no IRQ, gates off | 3 | 0 |
| 003 | SEVG then 128 WFE, no IRQ, gates off | 3 | 0 |
| 004 | one WFE, TIMER5 IRQ enabled, gates on | 1 | 0 |
| 005 | one IDLE, same IRQ/gates | 60034 | 1, vector 63 |
| 006 | 128 WFE, TIMER5 configured, only gate 9 on | 3 | 0 |
| 007 | 128 WFE, TIMER5 configured, only gate 8 on | 3 | 0 |
| 008 | IDLE, TIMER5 configured, both gates off | no result; watchdog restart | 0 recorded |

Thus WFE does not wait for this timer, nor block after the first of 128 executions, in the tested
application configurations. The initial wave also completes 128 WFE with both gates enabled. The
single-core tests do not justify hw=nop in every context: an untested event-enable or power mode could
matter. Event-latch consumption remains unestablished because no blocking state was found. Enabled
IDLE has a working wait/wakeup control; the masked case failed to complete before watchdog recovery.

## Software pending retention and nesting

In events 007, cli masks delivery, swi 0 raises the request, and a bounded loop gives counter 0 before
and after the masked interval. Setting icfg=0x300 then gives exactly one vector-120 handler. Events 008
instead keeps bit 9 enabled but bit 8 disabled and raises swi 7: counts are again 0,0,1, at vector 127.
These software requests remain pending through either tested global mask, matching app2's timer result.
The handler acknowledges ILAT_CLR bit n.

The nested test raises swi 0 at vector 120. That handler acknowledges itself, raises swi 1, optionally
opens gates during a bounded window, then closes them, restores its return state and returns. Exactly two
handlers complete in every case; all visible GPR/scratch/stack effects match the app3.nesting model.

| Cases | Outer / child priority | Gate action inside outer | Maximum depth / order |
| --- | --- | --- | --- |
| 000 | 3 / 7 | no gate write (entry bit 8 clear) | 1, deferred |
| 001, 008 | 3 / 7 | both (icfg=0x300) | 2, child completes inside outer |
| 002 | 3 / 7 | sti only (bit 9) | 1, deferred |
| 003 | 3 / 7 | bit 8 only | 1, deferred |
| 004 | 3 / 3 | both | 1, deferred |
| 005 | 7 / 3 | both | 1, deferred |
| 006 | 0 / 7 | both | 2, child completes inside outer |
| 007 | 7 / 0 | both | 1, deferred |

Higher numeric priority preempts the outer software handler when both gates are enabled. Equal/lower
priority waits, and opening only one gate does not permit the higher-priority child to nest. These are
software-source observations at the listed priorities, not an exhaustive model of every icfg field or
peripheral. The last-entry snapshots are distinct from the explicit trace and cannot alone prove nesting.

## Second core: a working sequence, and failed restart setups

Cores 000 reached ready=1, cnum=1 and acknowledged command 1. Cores 001..007 each expired the bounded
ready poll: none establishes that its requested peer operation ran. Cores-restart changes stop/release
into separate register writes and clears C1_CON bit 3 before setting bit 1. Batches 000 and 004 reach
ready/cnum=1; the other six do not. Batch 004 acknowledges command 5 after one WFE with no main-core
SEVL/SEVG command in that batch.

Cores-restart 002 also records one vector-1 entry, EMU_MSG=DBG_MSG=0, reti=0x01C0C98E, and saved
r1=0x01EEF288. That frame is outside the main probe and includes the other core's CSR bank address.
The shared handler did not tag cnum, so the executing core and cause are not established. It is a setup
failure observation, not evidence that SEVG traps. The app still returned on its own. No semantic claim
uses the failed-start batches; reproducing a reliable CPU1 restart needs further work.

Core-sequence avoids restarting CPU1 between commands. It reaches ready/cnum=1 and the mailbox records
all eight acknowledgements, in order: 1 (handshake), 2 (CPU1 SEVL), 3 (CPU1 SEVG), 4 (delayed CPU1 SEVG),
5 (one CPU1 WFE), 6 (128 CPU1 WFE), 8 (CPU1 WFE alongside main SEVL), 9 (128 CPU1 WFE alongside main SEVG).
CPU1 completes all eight, with no handler entry or watchdog restart. Its wait-entry and completion markers
are set. Both cores access the explicitly synchronized shared mailbox successfully in this sequence;
this is not a general memory-ordering proof.

For command 4, the main WFE interval is TIMER4 4000..4001; its immediate ack sample still says 3, and a
later bounded delay sees 4. Main WFE therefore returns **before** the delayed global-event sender completes.
The later CPU1 WFE commands also return without a demonstrated blocked interval. SEVL/SEVG execute on
both cores, but global delivery, local-versus-global routing and event consumption remain unobservable
by these tests. A nonblocking receiver cannot distinguish a delivered event from no event.

## Copex: reproducible history in the application, no numerical rule

Each copex application runs eight mode-15 targets on r5_r4=0x10000000/0x08000000, restoring old
r1_r0=0x12569ADE/0x13579BDF and all other captured inputs/flags to the same target values. The in-batch
prefix mode sequence is none,14,15,15,14,14,15,none; 32 nops follow each target. Prior-mode cases restore r0/r1
with immediate loads before the target. Flags are 15, and only the destination pair changes.

The destination even/odd pairs, by batch index, are:

    000  0D402406 / 06A01200
    001  0D402406 / 06A01200
    002  0D402406 / 06A01200
    003  0D402412 / 06A0121A
    004  0D4023FE / 06A011EC
    005  0D402412 / 06A0121A
    006  0D402412 / 06A0121A
    007  0D4023FE / 06A011EC

The entire sequence repeats exactly after the second application install/software-reset launch. Paired
batches have equal instruction bytes, target inputs, flags, stub, sp, rets and setup/readback programs.
The two applications differ in run identity. Reproducibility under this repeated launch sequence does
not prove that software reset initializes every hidden state. Even the immediate prior mode alone is
insufficient: targets after mode 14 differ among 001,004,005. This is stronger controlled-context evidence
for history/state dependence, not a formula, a random-number claim or an invented state machine.
The existing unpredictable hw key stays; no numerical model is registered for copex.

## Reproduction and validation

[app3cases.py](../../tools/hwtest/app3cases.py) writes the case JSON files with this repo's assembler.
The exact cases and original plans are retained even for failed setup attempts. For example:

```sh
python3 tools/hwtest/gen.py DIR --cases hw/fm1-2026-10-24-app3/nesting.json --batch 1 --app
python3 tools/hwtest/appplan.py DIR --run-id 0x3010 --modes 0,0,0,0,0,0,0,0,0
python3 tools/hwtest/fm1app.py DIR/app.fwsc tools/hwtest/app/advanced.S DIR/app.S DIR/plan.S
# Stage reset.bin/reader.bin at 0x01C28000 and run runapp.sh after backing up.
python3 tools/hwtest/appcollect.py DIR RAM.bin hw/fm1-2026-10-24-app3 --run-id 0x3010
python3 tools/hwtest/appverify.py hw/fm1-2026-10-24-app3
python3 tools/hwtest/check.py hw/fm1-2026-10-24-app3/results.jsonl --missing
```

Use a fresh run identity, distinct batch filenames, and a fresh results directory for new experiments.
Mode 3 requires advanced.S; use one CPU1 startup per application until restart is understood.
appcollect filters unfinished batches before interpreting RAM. appverify checks cause/count, the
independent nesting trace/depth, bounded counter deltas, exact protocol acknowledgements, unaffected
registers/flags and stack/scratch preservation. Copex output numbers remain explicitly unmodeled.
M-Flasher SHA-256 is 1d8404c84febd3def6d8281aa279e59e20a488a36f16c3f2ac19b920dd67d5b8,
matching app2. The case generator reproduces all eight committed case files exactly. The evidence audit
matches all 60 unique manifests, 59 patterns and 177 records; no failed batch has instruction outputs.
Rebuilding all eight applications from the archived own-source snapshots, original plans and recorded
batch images reproduces every uploaded package byte for byte.
The table-field audit permits only summary/notes/sources/hw changes and finds changes only in behavior
notes and the WFE summary for ten entries. No hw key, encoding, syntax, field, example or status changed.

The required checks passed: python3 -m pi32v2isa check reports 1165 entries and zero problems;
python3 -m unittest discover -s tests passes 138 tests (one skipped). check.py passes on all 22
hw/*/*.jsonl files. appverify.py checks 60 app3 expectations and the 32 existing app2 expectations with
zero problems. New tests exercise advanced-profile linking and rejection of incorrect nesting traces
and protocol acknowledgements. [validation.json](validation.json) records these counts.

## Firmware restoration

The requested image is /home/julius/backups/hwapp/fm1-20261025-005103.bin, SHA-256
852607102a3a867d1afe4eb20d969c1c323a1c4ef908eb5b823e9ffb870b7f73. The fresh pre-test backup
fm1-20261025-015356.bin matches the entire 1 MiB image. The prepared restore package is the same
application-only package used successfully in app2: its member ends at 0xA9000, with permitted writes
[0x4000,0xA9000). It includes the original app.bin/cfg_tool.bin/DX7.bin application extent, rather than
the smaller stock 0x93000 boundary. No generic full-backup restore or bootloader-writing option is used.

After the test commit the package installed successfully, writing only eight differing application
sectors, 0x04000..0x0BFFF; M-Flasher verified the chip CRC32. A fresh full-flash backup at
/home/julius/backups/hwapp/fm1-20261025-021628.bin compares equal **byte for byte over all 1,048,576 bytes**
to the requested image, with the same SHA-256 above. This verifies the boot area, application, settings
and remaining flash as well as the written sectors.

The restored application was then started with the slot-0x01C28000 reset plug-in, after the native
loader in 0x01C20000. Its USB command disconnected as expected. A bounded USB check reports
4c4a:c755 FM-1 (Bus 007 Device 041); the unit is running the restored firmware. LASTSLOT was cleared
after that confirmed reset. backup.json retains the install/readback/start/USB logs and comparison
metadata. Restoration evidence was added to the test commit afterwards.
