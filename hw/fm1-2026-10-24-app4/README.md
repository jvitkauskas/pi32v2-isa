# FM-1 application run 4: CPU1 boot, events and shared memory

Continuation of [app3](../fm1-2026-10-24-app3/README.md), on the same AC791N FM-1 and m-bootloader
1.2-22e2559. Own applications were assembled and linked with this repo, then installed over the application
area with M-Flasher. The pre-test full backup matches the requested restoration image; [backup.json](backup.json)
identifies both. No bootloader command, --with-bootloader, settings wipe or write outside the application
area was requested. No flash image, RAM dump, executable or external implementation is committed.

## Source comparison before hardware

The fetched fm1-base origin/main is aa2b3bc8f7900cd1820947cb93ca0e8ecc4189e7, including include/plat.h,
device/cpu2.c, device/main_fm1.c and DESIGN.md; the loom-hooks merge is e35f7e2c6904ff1a3eed10035474c8cf089c0b88.
Its felucca-bsp pin, fetched from hugelton/felucca-bsp, is d6b8f771795be04d77e15d72a79f474a723796d7.
The reviewed BSP files are chip/fm1_cpu1.h, fm1_cpu1_stop.h, fm1_cpu1.S, fm1_guard.h and fm1_irq.h (MPL-2.0).
AC79 SDK csfr.h (Apache-2.0) supplies register facts only. No source wording or implementation was copied.
[CPU1.md](../../docs/CPU1.md) links these exact sources and describes the independently written sequence.

Compared with app3, the community lifecycle holds CPU1 before clearing shared RAM; stops it by setting
C1_CON bit 1 **before** clearing bit 3; temporarily masks and later clears bus-debug causes during that
stop; clears CPU1 IRQ sources; permits ROM traversal through PC guards and entry publication through the
top-RAM write guard; and initializes its supervisor stack explicitly. Its high-level start API is restricted
to application initialization before audio/timers. The loom hook provides early stop and core-aware fault
handling. App3 stopped in the reverse bit order, without bus-cause handling, and attempted late releases
between batches. These differences guided a new experiment, not a claim that each is independently necessary.

The dual profile now implements those facts with an owned RAM worker at 0x01C10000, user/supervisor stacks
0x01C12000/0x01C14000, a per-start nonce, and separate CPU0 request / CPU1 reply lines. DBG_WR_EN is checked
before writing the toggling access value. Guards and SYS_DIV are restored after entry. The worker reports
cnum and all three stack pointers; a Boolean ready alone is insufficient. A per-core fault handler parks a
faulting peer instead of resuming it through CPU0's continuation. Fault records in the captured attempts are
zero; a failed handover with no dump says nothing about its faults.

## Attempts and evidence

**32 applications were uploaded: 31 returned captures, one required manual recovery.** Captures contain
71 batch journals: 58 completed and 13 status-3 batches (five startup watchdog recoveries, eight
intentional-reset journal errors). The failed handover planned seven further batches, whose reachability
is unknown; they are not counted as seven observed executions. There are 174 instruction records
(58 probes, 116 calibration nops). Six peer-IDLE commands stay incomplete while their CPU0 batches
complete and capture that fact.

| Wave / run id | Completed / captured batch journals | Purpose |
| --- | --- | --- |
| lifecycle / 0x4001 | 5 / 9 | Initial entry versus late stop/release; four watchdog recoveries |
| hold-diagnostic / 0x4002 | 1 / 2 | Sample the failed late-entry ROM PC; one watchdog recovery |
| boot-starts / 0x4003 | 1 / 9 | Intentional resets; eight journal-marker errors |
| persistent-cycles / 0x4004 | 9 / 9 | One initial entry, eight live reuses |
| boot-verified / 0x4005 | 9 / 9 | Nine successful whole-chip software-reset starts |
| peer-waits / 0x4006 | 8 / 8 | WFE gate/prime/count cases |
| cross-events / 0x4007 | no capture | Seven planned cases; reachability unknown, manual recovery |
| isolated cross cases / 0x4010..0x4016 | 7 / 7 | Main/peer waits and delayed SEVG |
| isolated locks/counters / 0x4020..0x4024 | 5 / 5 | Directed exclusion, unlocked/locked counters |
| isolated ordering / 0x4030..0x4033 | 4 / 4 | Message passing and store buffering |
| main IDLE / 0x4040..0x4042 | 3 / 3 | Peer no-event/SEVL/SEVG versus TIMER5 wake |
| peer IDLE / 0x4043..0x4048 | 6 / 6 | CPU0 captures incomplete peer commands at both gate settings |

The complete attempt ledger is [attempts.json](attempts.json): run ids, package/worker/RAM hashes,
worker placement, every manifest, plan, exact own profile source revision and install/start/USB/read logs.
[observations.json](observations.json) retains journals, including failed and invalidated batches.
[results.jsonl](results.jsonl) contains only status-2 batches, each one probe plus two calibration nops;
[patterns.json](patterns.json) supplies their scratch patterns. Results never stand in for failed peer setup.

The initial lifecycle wave has nine batches: statuses 2,3,2,3,2,3,2,3,2 and five app boots. Each fresh boot
starts CPU1; each following late stop/release times out and watchdog-recovers. hold-diagnostic similarly
completes the first batch and watchdog-recovers the second. Its failed release has no nonce/heartbeat,
CPU1 CNUM=1 and PC=0x01E0005A in ROM at a 480001-tick timeout. This is evidence against the initial
hypothesis that a resumed old worker merely omitted its new ready flag. The late-ROM handshake remains unknown.

boot-starts deliberately resets the whole chip between nine batches. All nine have successful startup
samples, but the first eight journals become status 3: that revision forgot to clear the active-batch marker
before its intentional reset. They have **no instruction outputs**, and those eight software resets are not
watchdog failures. After fixing the journal marker, boot-verified completes nine of nine across nine boots.
persistent-cycles completes nine of nine in one boot, with live heartbeat checks between batches and a
stable heartbeat only after the final hold. This establishes boot-time start and persistent dispatch,
not reliable stop/restart in one boot. Five genuine startup watchdog recoveries occurred in total.

cross-events (0x4007), a seven-batch package, failed to return to download mode after its reset/start.
There is no RAM capture and no evidence which, if any, probe it reached. Testing stopped; the user recovered
the desktop/unit and confirmed download mode. A bounded USB check succeeded before another upload.
The seven cases were then split into separate single-probe applications, all of which completed. This
failed handover remains unexplained; successful isolated tests do not erase it. No blind upload retry was made.

The other waves are peer-waits (eight cases), the five isolated lock/counter cases, four isolated ordering
cases and the isolated IDLE/event controls listed below. Aggregate locks.json/ordering.json are generation
inputs, not additional uploads. active-watchdog.json was prepared but not uploaded. A mistyped local build
name was rejected before upload; it produced no hardware attempt.

The reset and retained-RAM reader occupy slot 0x01C28000; native install/backup uses 0x01C20000. LASTSLOT
is tracked, cleared after confirmed resets, and a successful bounded download-mode check precedes every
reader. The custom reader is in the other slot from the native loader. Binaries/dumps remain under
/tmp/fm1-app4 and ~/pi32v2-hw-app4, outside the repo.

## CPU1 lifecycle and journal

Use the [tested start/stop guide](../../docs/CPU1.md) for compiler/RTOS work. The worker stays alive between
commands, receives a new request sequence only after arguments are synchronized, and synchronizes its
samples before acknowledging. Phase samples have their own matching request sequence, avoiding a stale
ready phase. A missing ACK is explicitly incomplete peer work, even when CPU0's batch completes.

Journal +112..188 holds startup mode (initial 1, live 3, failed 0), elapsed ticks, held/released C1_CON,
nonce, CPU1 cnum/usp/ssp/sp, sampled PC, reserved, pre-hold heartbeat, two hold/live-window heartbeat samples,
two live-reuse heartbeat samples, startup DBG_MSG, reserved, stop flag and final sampled PC. Earlier source
revisions did not populate every field. +192..255 is mailbox +32..95. The mailbox at 0x01C7CE00 has request,
command, two arguments, nonce, go and payload in +0..31; CPU1 owns ready/ACK/identity/heartbeat/phase/timestamps/
observation/progress/request-phase-tag in +32..95. Litmus data occupies separate lines +128 and +160.
The sources in each attempt define exactly what was populated; zero is not automatically a measurement.

## Events and waits

peer-waits completes two unprimed WFE at each icfg 0/0x100/0x200/0x300, locally/globally primed waits,
and 128-WFE sequences. The first synchronized wait interval is 1–2 TIMER4 ticks; the 128-wait loop is about
88 ticks, including its loop and barriers. Every command has a matching ACK. The isolated main control,
SEVL, SEVG and WFE cases each complete alongside two peer 128-WFE commands. The independently timed main
WFE follow-ups return twice before CPU1 executes delayed SEVG, both unprimed and with SEVL/SEVG prefixes.
For the unprimed case, main timestamps are 1831,1832,1833, sender phase is still zero, and sender timestamps
are 468500,468502. These rule out waiting for that later event; they do not prove how an event latch is consumed.

The three isolated CPU0-IDLE controls arm TIMER5 at period 60000, with both CPU0 gates enabled.
CPU1 delays 10000 loop decrements, then executes no event, SEVL or SEVG and records before/after TIMER4
samples. All three CPU0 waits return after about 240000 TIMER4 ticks, with exactly one vector-63 timer
handler. The sender finishes around 6504..6509, far before the CPU0 end samples around 241837..241840.
Thus neither peer event gives a measurable early IDLE wake in these configurations. TIMER4 and TIMER5
have different counter configurations here; only measured ticks, not wall time or IRQ latency, are claimed.

The reverse direction uses a peer command that records phase 1 and its start timestamp, then executes
IDLE. CPU0 waits for that request's phase, delays 10000 decrements, executes the control/SEVL/SEVG, and
polls the matching ACK for a bounded million iterations. Masked CPU1 remains at phase 1 with ACK 0,
no end timestamp, and sampled PC 0x01C10166 (the worker's IDLE opcode). CPU0's batch still completes,
holds the peer and returns to download mode; no peer completion is invented. All three repeats with CPU1 icfg=0x300 have the same
phase/ACK/end-timestamp/PC outcome. No CPU1 IRQ source is enabled by these event tests.

No blocking WFE receiver has been found on either core. The permitted source headers identify PMU_CON
but give no event-enable bit meaning used by this experiment; no undocumented power-control bit sweep
was attempted. These negative wake controls do not specify event routing or consumption in other
power/event-enable contexts. No hw=nop is assigned from these observations.

## Shared lock and finite ordering probes

| Probe | CPU0 sample while holding / final result | CPU1 result |
| --- | --- | --- |
| No CPU0 lock | phase 2 while owner=1 | entered and read owner=1 |
| CPU0 lockset, later lockclr | phase 1 while held, phase 2 after release | read owner=0 after release |
| Concurrent counters, no locks | 1455 total | completed 1000 iterations |
| Concurrent counters, locked | 2000 total | completed 1000 iterations |
| Locked repeat in another app | 2000 total | completed 1000 iterations |

Each core runs 1000 load/add/store increments with four nops between load and add. The locked versions
surround each update with lockset/csync and csync/lockclr. The directed probe publishes owner=1 and gives
CPU1 permission to acquire; after a 10000-decrement interval, CPU0 samples the peer phase, publishes
owner=0 with csync, and releases. The unlocked control reaches phase 2 during that interval. Together
these establish shared exclusion, rather than merely observing a lucky final count. Recursion, fairness,
release by a non-owner and implicit ordering without the explicit barriers remain open.

Message passing uses 1000 sequential payload/flag/acknowledgement handshakes on separate data lines.
Both variants report zero stale payloads: optional csync between CPU0's payload and flag and before CPU1's
payload load, or no barriers at those two positions. The phase/progress protocol itself uses csync.
Store buffering uses 1000 coordinated iterations: reset X/Y, release both cores, each stores its own word
then reads the other's. Both variants report zero both-zero outcomes, with or without a csync at each
store-to-load test position. The progress protocol again synchronizes. These finite results do not
identify an ordering guarantee or demonstrate the necessity/sufficiency of csync. No complete memory
model or cache maintenance rule follows. The cases, worker and assertions retain the exact tested programs.

## Reproduction, checks and remaining scope

`tools/hwtest/app4cases.py` regenerates the case programs. The current dual/persistent/reboot profiles
are in tools/hwtest/app; the earlier exact revisions remain in each attempt. Rebuilding the archived
worker and application package from those snapshots matches every recorded SHA-256. The independent
app4verify.py checks nonce, core/stack identity, initial versus live mode, heartbeat windows, exact
completion/result membership, zero captured core-fault records, and expectations.json's command/timing/
lock/counter/ordering assertions. The preservation model checks the lifecycle calibration's visible CPU0
state; timing and concurrent programs use explicit protocol assertions, not an invented opcode model.

Boot-time CPU1 and persistent dispatch, and shared lock exclusion, are now demonstrated on this unit.
Late CPU1 restart, event-enable/routing/latch consumption, CPU1 IRQ delivery, recursive/non-owner locks,
fairness, implicit lock ordering and a complete barrier/cache memory model remain open. Copex history,
privilege changes and unrelated gaps were not tested by this run. Nothing changes instruction encodings,
syntax, fields, examples or status; no new hw key is justified by these context-limited observations.

Validation passed: `python3 -m pi32v2isa check`; `python3 -m unittest discover -s tests`
(139 tests, one skipped); check.py on every hw/*/*.jsonl; app4verify.py; and app2/app3 appverify.py
regression checks (23 JSONL files; 71 app4 batch assertions). The end-of-run backup record identifies application-only restoration and full-flash
comparison to the user's requested image.

## Restored unit

After committing the experiment, the requested /home/julius/backups/hwapp/fm1-20261025-005103.bin was
packaged only through the original application extent 0xA9000. M-Flasher wrote eight sectors in
[0x4000,0xC000), CRC-verified them, and left the bootloader and other flash outside the application
untouched. A fresh full readback at fm1-20261025-031416.bin matches all 1048576 bytes of the requested
image, SHA-256 852607102a3a867d1afe4eb20d969c1c323a1c4ef908eb5b823e9ffb870b7f73. The RAM reset plug-in
then booted the restored application; bounded USB enumeration reports 4c4a:c755. LASTSLOT was cleared
after that confirmed reset. No test application is left installed; the user's restored firmware is running.
[backup.json](backup.json) preserves the install, full-readback, start and USB evidence.
