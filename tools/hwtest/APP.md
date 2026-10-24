# Design: running test cases as an FM-1 application

Status: steps 1–4 have run. Steps 1–2 (`hw/fm1-2026-10-24-app`) verified retention and the batch harness.
Steps 3–4 (`hw/fm1-2026-10-24-app2`) verified watchdog skip/restart, recording handlers, software interrupts
0..7, timer masking/pending retention through icfg bits 8/9, and timer priorities 0/3/7. At that point event
blocking/consumption and other power modes remained open. Application run app3 then verified software pending
retention and selected priority-nesting combinations, and ran a single-start second-core sequence;
blocked-event reception and reliable CPU1 restart remain open (details below).

Tools: `fm1app.py` (assemble, link at `0x02000120`, pack a `.fwsc`; `--plugin` for RAM images),
`app/probe.S` (step 1), `app/driver.S` with `gen.py --app` (runs batches), `app/reset.S` (starts the installed
application from download mode), `analyze.py --ram` (results from a RAM dump). The optional experiment profile is `app/experiment.S`
with `app/platform.S`, `appplan.py` (plans and tagged vectors), `appcollect.py` (completion-aware extraction),
and `appverify.py` (counter/cause assertions); `runapp.sh` installs and captures it after a verified backup.

Run 5 (`hw/fm1-2026-10-24-v5/README.md`) showed that the download-mode runner can install its own handlers in
the RAM vector table, so `syscall`, `bkpt` and `hbkpt` are now captured there. What download mode still cannot do:

- configure the interrupt controller and a timer without disturbing the ROM's USB handling, so interrupt
  delivery, `cli`/`sti`, `icfg` bit 8, `swi` delivery and events cannot be observed;
- survive a reset or hang: `idle` reset the unit, and four uploads after a debug return hung, each costing a
  power cycle and giving no result;
- start from a known state: the ROM leaves RAM (vector 2's word, for one) different after each recovery, and
  `copex` depends on history that the runs could not control.

The open cases are in `docs/GAPS.md`, "Meaning (behaviour)". This design runs the same cases from a small
application that owns the whole chip, keeps the results in retained RAM, and hands them to the existing
download-mode tools.

Facts below come from the FM-1 firmware trees (fm1-base `bsp/chip/`, MPL-2.0; Felucca `firmware/hal/`,
GPL-3.0) and JieLi's AC79 SDK headers (Apache-2.0), used as facts only, and from m-bootloader's
`docs/SPEC.md` (MIT). Nothing is copied; the application is written for this repo (MIT-0).

## What is known

- **Entry.** m-bootloader validates the app and calls `0x02000120` with interrupts disabled and `r0` = the
  boot object pointer, on its own stacks (SPEC §6.5). The image's first instructions are `goto +4; rts`
  (fm1-base `crt0.S`). The application runs from flash (XIP) and sets up its own stacks.
- **Vectors.** A RAM table at `0x01C7FE00`, 128 words, one handler address per source; installing a handler is
  a store, no base register (fm1-base `bsp/chip/fm1_irq.h`; SDK `include_lib/driver/cpu/wl82/asm/hwi.h`).
  Slot 2 overlaps the boot object at `0x01C7FE08` and slot 126 the second core's entry word. Run 5 confirmed
  on hardware that the ROM follows slots 0, 1 and 2 of this table.
- **Sources.** 0 debug (SDTAP), 1 every CPU exception, 2 system call, 3..127 peripherals, 120..127 soft
  interrupts (raised by setting an `ILAT_SET` bit). The cause of an exception is in `EMU_MSG` (`0x1EEF0D4`:
  misaligned, illegal instruction, divide by zero, stack overflow, watchpoint, FPU) and `DBG_MSG` (`0x1EEE244`,
  unlocked by writing `0xE7` to `0x1EEE240`: watchdog, bus errors, PC/write limits). Per-source enable and
  priority are 4-bit fields in the `ICFG` words at `0x1EEF100`; `icfg` bit 8 is a global enable on top of
  `cli`/`sti`.
- **Handlers.** The existing ones push `{psr, rets, reti}` and the caller-saved registers, run, and return with
  `csync; rti`. The fault handler also saves `sp, ssp, usp, icfg, retx, rete`.
- **Back to download mode.** An application requests it by writing `usb_update_mode` + NUL at `0x01C7FD80` and
  doing a soft reset (power-control bit 4) (SPEC §4.2). That is how the stock firmware's soft key works.
- **Retained RAM.** fm1-base keeps a crash record in a `.noinit` area at `0x01C7C000` that survives a reset, and
  `0x01C7FD80` onward is the boot/update/application communication area (SPEC §6.1). The mask ROM's
  download mode left the sampled retained areas unchanged in step 1; step 3 also preserved the progress
  journal across a watchdog restart. Run 5 saw some RAM words
  differ after each recovery, so "retained" has to be measured, not assumed.
- **Packaging.** M-Flasher installs `.fwsc` packages, M-VAVE's or custom ones in the same format (fm1-base
  `fm1pkg.py` builds them; format in SPEC §5). m-bootloader stays installed, so download mode, and with it
  restoring a backup, keeps working whatever the application does.

## Design

1. **Image.** A small assembly application (no C, no libraries; built with this repo's `as` and `ld`):
   `crt0` (entry contract, stacks), a vector setup, the existing runner core (`hw_run`, the exits), the cases
   and their stubs, all generated by `gen.py` (a new `--app` output beside the RAM images). Stubs are copied to
   RAM and run there, as in the download-mode runs, so the results compare directly.
2. **Handlers.** Every vector slot points at a recording handler: it stores the vector number, `EMU_MSG`,
   `DBG_MSG`, `reti`, `rete`, `retx`, `rets`, `psr`, `icfg`, `sp` and the registers into the current case's
   result, clears the cause bits, sets the return register to the stub's resume label and returns. The case
   then ends normally, so one trap costs one case, not the run. Run 5's `hw_probe_handler` is the starting
   point. The debug route (slot 0) must return through `rete`/`rte`: returning from it with `rti` left the unit
   unable to take the next upload. `hbkpt` leaves `rete` at the instruction itself, so its handler must step
   past it; `syscall` and `bkpt` leave the address after the instruction. Which sources are enabled, and at which
   priority, is part of each case's set-up (for the interrupt-control forms).
3. **Progress and recovery.** Before each case the application writes the case number to retained RAM; after it,
   the result. The watchdog is armed in reset mode with a short timeout, so a hang becomes a reset. On start
   the application finds an unfinished case in retained RAM, records it as "reset or hung", and continues with
   the next. A bounded count of such restarts, also retained, ends the run. No power cycles are needed while it
   runs.
4. **Hand-over.** When all cases are done (or the restart limit is hit) the application writes the download-mode
   marker and resets. The host then reads the result area with the existing runner (`run-ram` + `FD61`),
   and `analyze.py` turns it into `results.jsonl` as for the other runs.
5. **Host side.** `gen.py --app` writes the image and a manifest; a small tool packs it into a `.fwsc`; M-Flasher
   installs it; after the run, a read-back script fetches the results. Afterwards the unit's own firmware is put
   back from its backup with M-Flasher.

## Steps

1. **Retention probe.** An application that only writes a pattern to the planned result area and requests
   download mode. Read the area back with `run-ram`. If the ROM clears it, choose another area (inside
   `0x01C7FD80`.., or one the ROM is shown to leave alone) before going on.
2. **Harness check.** The self-test and a sample of register-only cases from run 1 through the application.
   Results must equal run 1's for the same inputs; this proves the handoff, the stub copy and the read-back.
3. **Handlers.** The trap and event forms still open in `docs/GAPS.md`, one per case, with the recording
   handlers, the soft-interrupt sources enabled, and the watchdog armed.
4. **Interrupt control.** `cli`/`sti` (with and without a register) and `icfg` bit 8 against a timer interrupt
   whose handler counts: does it fire, is it held pending, at which priority.

## Open questions

- ~~Is the result area retained across the ROM's download-mode entry (step 1)?~~ Yes: every sampled
  area in `0x01C0C000..0x01C1FFFF` and `0x01C30000..0x01C7F7FF` kept all its words, and the ROM clears the marker.
- ~~How to arm the watchdog~~: the experiment uses P33 register 0x80, timeout code 0xB (nominal 2 s),
  reset mode, and clears the exception-enable bit in P33 0x17. An intentional stall caused a restart;
  the app marked the unfinished batch and continued without a manual power cycle. Precise timing was
  not calibrated. See app2 for the original register facts and observed journal.
- ~~Can the application install its vector table at entry?~~ The experiment installed all 128 RAM entries
  and received the intended callbacks without a write-guard exception. It did not install fm1-base
  guards or establish the behavior after such guards are enabled.
- ~~The `.fwsc` packer~~: `fm1app.py`, written from SPEC §5; M-Flasher accepts its packages.


## Steps 3–4 experiment profile

Use a distinct `--run-id` for every new attempt. At most nine one-probe batches fit in the retained slots;
each still starts with two calibration nops. After `gen.py --cases ... --batch 1 --app`, run:

```sh
python3 tools/hwtest/appplan.py DIR --run-id 0x2006 --modes 0,2 --priorities 3,7
python3 tools/hwtest/fm1app.py DIR/app.fwsc tools/hwtest/app/experiment.S DIR/app.S DIR/plan.S
```

The example mode list requires exactly two batches. Mode 0 runs without a timer; mode 1 deliberately stalls
after arming the watchdog; mode 2 starts TIMER5 (source 63) before the runner. Priority is 0..7. The handler
acknowledges TIMER5 and software sources, records exception/debug causes before clearing them, and uses
rete/rte for debug entry 0. Other asynchronous handlers preserve their return PC; synchronous syscall and
exception probes explicitly resume at the planned instruction end. The exception can arrive after later
runner instructions: the entry frame is not automatically the state at the tested opcode.

The basic profile sets its own main/supervisor stacks at `0x01C0D000` / `0x01C0F000`. It leaves the bootloader
and all flash beyond the installed application untouched. It does not start the second core or alter voltages;
the optional advanced profile below explicitly adds CPU1 and an independent TIMER4 counter.
Interrupt-controller state is owned by the app, not borrowed from USB.

Retained header at `0x01C7C000`, twelve words: magic `0x32504148`, starts, next batch, active batch+1,
boot argument, main sp after stack setup, psr/icfg after journal setup and before controller setup,
run id, current journal pointer, resume PC,
and P33 timeout flag. On restart, an active batch is marked unfinished and skipped; 16 starts is the cap.
The journal at header+0x100+256*batch has status (0 untouched, 1 active, 2 completed, 3 unfinished at restart),
handler count, last vector, EMU_MSG, DBG_MSG, reti/rete/retx/rets, psr/icfg/entry sp, sixteen GPRs, and reserved
sample words. It is a last-entry snapshot plus a count, not a trace of every interrupt.

`appcollect.py` requires a matching run id and only analyzes status-2 batches. A failed batch's RAM is never
turned into instruction outputs. Keep the binary dump outside the repository. `appverify.py` checks
`expectations.json` over handler tags/causes and relative counter samples; timer counts intentionally have
no exact numerical prediction. `check.py` models GPR/scratch preservation for the recording-handler context.

`runapp.sh` expects app.fwsc, reset.bin and reader.bin in its directory. The latter two use `0x01C28000`;
the unchanged bundled M-Flasher loader uses `0x01C20000`. A normal application reset can disconnect with
ENODEV or time out: the script checks download-mode USB before reading, without repeating the start.
The loader's install/read CRC checks and logs are retained. If the unit fails to return, stop for operator
recovery; do not retry uploads blindly. Before every run, confirm that an existing custom plug-in does not
occupy the loader's target slot.

Restore only the application area after testing. For app2 the specified full backup was repackaged as a
`.fwsc` member ending at `0xA9000` (the original application-file extent, rounded to a sector), then
installed without --with-bootloader or --wipe-settings. A first package incorrectly used the stock
`0x93000` boundary and was refused before writing because this backup has larger application files.
The complete package bounds allowed writes to `[0x4000,0xA9000)`; a generic full-backup restore command has broader permission and is not
used by this workflow. Verify by reading the flash afterwards and comparing it to the requested backup.


## Application run app3: event limits, nesting and CPU1

[Run app3](../../hw/fm1-2026-10-24-app3/README.md) attempted 60 batches in eight applications: 59 completed,
with one masked-IDLE case skipped after a watchdog restart. There were no USB hangs or manual recoveries.
Synchronized independent-counter samples distinguish a nonblocking WFE sequence (128 executions, 3 ticks)
from enabled IDLE (60034 ticks and TIMER5). Neither SEVL/SEVG prefixes nor the tested global masks create
a blocking WFE receiver. The masked-IDLE case provides no instruction output. Event delivery/routing,
consumption and other enabling/power configurations therefore remain open; no intrinsic nop/reset hw
classification follows from these contexts.

Software requests remain pending through either global gate in the tested number-0/number-7 cases.
The advanced handlers preserve reti and entry icfg before opening gates, acknowledge their own source,
record depth and entry/exit order, and restore state before rti. A higher numeric priority preempts only
with both gates enabled: 3/7 and 0/7 nest, while 3/3, 7/3 and 7/0 defer. Opening only bit 8 or using sti
alone defers 3/7. These tests use software sources 120/121; they are not an exhaustive controller model.

Build the optional advanced profile with app/advanced.S instead of app/experiment.S. Modes 0/1/2 retain
their meanings, while mode 3 attempts CPU1 startup with bounded ready polling and a watchdog already armed.
It publishes the entry at 0x01C7FFF8, temporarily sets SYS_DIV bit 3, and controls C1_CON at 0x01EEE004.
CPU1 uses owned stacks 0x01C12000/0x01C14000 with interrupts disabled and reports cnum. The source facts
are fm1-base's MPL-2.0 fm1_cpu1.h/.S and fm1_time.h, and the Apache-2.0 AC79 SDK csfr.h/debug.c, read as
facts only. The independently written assembly is not a copied core-start or interrupt implementation.

**CPU1 restarts are not reliable in this harness.** Of 17 release attempts, four reached ready/cnum=1 and
thirteen timed out; one failed-start batch also saw an untagged vector-1 frame outside the main probe.
Do not interpret a completed main batch as a successful peer test. Use one mode-3 startup per application
and require its ready marker before drawing peer conclusions. In the successful single-start sequence,
CPU1 acknowledges eight commands, including SEVL, SEVG, one WFE and 128 WFE. Main WFE returns while the
delayed peer-SEVG command is still unacknowledged. Since neither core was shown blocking on WFE, this does
not distinguish delivered events from no event.

Advanced nesting journals use +112 gate selection, +116 current depth, +120 maximum depth, +124 trace
length, and +128..188 for up to sixteen entry/exit tokens (vector / vector+256). CPU1 uses a sixteen-word
mailbox at 0x01C7CE00; after the stop controls are written it is copied to journal +112..175. Its fields and
command protocol are in the run README. Failed startups have no peer snapshot; their main r8=0 is a
missing ready marker, not a measured core number. The journal remains a last-entry frame plus these
explicit samples, not a general interrupt trace.

app3cases.py regenerates the committed case programs; attempts.json preserves exact plans, manifests,
own profile revisions, binary hashes and all device logs. appverify.py now additionally checks entry/exit
order, depth, bounded unsigned counter deltas, protocol acknowledgements, unaffected GPRs/flags and
stack/scratch preservation. semantics/app3.py supplies a numerical model for the deterministic nesting
programs. Timing-dependent programs and copex remain separate from ordinary opcode models. Copex repeats
its eight-result sequence across two application launches, but its numerical/history rule remains unknown.
