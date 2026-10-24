# FM-1 hardware run 5, 2026-10-24: return selection, block aliases and RAM handlers

The fifth [hwtest](../../tools/hwtest/README.md) run on the same AC791N FM-1. Images use this
repository's assembler and linker and record format 2. Only M-Flasher `run-ram` and reset recovery
through `download-mode` were requested; no flash or interrupt-controller/debug-register MMIO was
written. M-Flasher `/opt/m-flasher/m-flasher` has SHA-256
`1d8404c84febd3def6d8281aa279e59e20a488a36f16c3f2ac19b920dd67d5b8`.

## Evidence and method

There were **167 attempted test batches: 162 completed, one reset, four hung**. `results.jsonl` has
509 records, including calibration nops; `patterns.json` holds their initial scratch. `outcomes.json` retains every attempted batch's exact manifest, slot, image SHA-256
and available log. Failures have no invented instruction outputs. The self-test passed 26/26.
A separate RAM-table inspection uploaded a runner but did not invoke its test command; it is not
counted as an instruction batch.

Each non-self-test batch contains two calibration nops and one probe. The desktop used
[runstep.sh](../../tools/hwtest/runstep.sh), bounded USB inspection, and alternating RAM slots.
The user confirmed download mode initially and after each hang. Power cycles can leave the desktop's
USB inspection stalled; the user recovered the desktop as needed. No upload followed a hang before
that confirmation. The desktop copy is `~/pi32v2-hw-v5`, which survives a desktop reboot.

The case JSON filenames name waves. For example:

```sh
python3 tools/hwtest/gen.py DIR --cases hw/fm1-2026-10-24-v5/iff-and.json --batch 1 --first-slot 0x01C28000
python3 tools/hwtest/analyze.py DIR --json RESULTS.jsonl
python3 tools/hwtest/check.py RESULTS.jsonl --missing
```

Starting slots: selftest `0x01C20000`; iff-and and copex-history `0x01C28000`;
callns-targets, callns-upper, copex-wait and handler `0x01C20000`; handler-owned `0x01C28000`;
handler-routes `0x01C20000`. A read-only table-inspection upload in `0x01C28000` preceded
callns-targets. `handler` only executed its initial installation proof. `handler-owned` stopped at 003,
resumed at 004
after recovery, and finished at 008. `handler-routes` stopped at 000; `handler-routes-b` completed 000
and stopped at 001; `handler-routes-rest` completed 000..002 and stopped at 003. Both latter waves
started in `0x01C28000`. `handler-rte` (eight batches) and `handler-slot-a` (five) also started there
and completed in full. Prepared cases after a stop are not evidence; outcomes identifies actual attempts.

`before` and `after` are executable setup/readback/restore instructions; their effects belong to the
capture. `entry` identifies setup; `stub` identifies the tested instruction. The controlled callns
manifests were subsequently annotated with `model = "v5.callns-targets"`, which changes no image byte.
The btbclr manifests were also marked unmodeled as the delayed path became clear. These model-name
annotations are analysis metadata; the image, operands and runtime addresses are unchanged. Named
context models prevent trap setup from being checked as a bare nop/barrier or ordinary ROM trap.
`v5.handler-unresolved` intentionally has no model for the delayed btbclr path. Copex remains unmodeled.

Runner code was extended during this run. The exact old layouts and resolved symbol inputs are retained
in outcomes, rather than pretending all waves used the final runner. Handler case files contain numeric
own-RAM pointer constants in the first two readback instructions. When rebuilding after a layout or slot
change, first build without uploading, replace those constants with that manifest's `in_values[7]` and
`in_values[5]`, then rebuild. Their instruction lengths stay fixed. Addresses of the main instruction and
its continuation must also be rechecked. Do not run a stale slot/pointer plan.

## Six floating-name blocks are AND-nonzero on this chip

`iff.ne.rr.1` through `.6` take the then-part exactly when `(R[r] & R[s]) != 0` in all **528 captures**:
72 cases in run 3's results, 24 in iffstate, 384 in iffgrid, and 48 new iff-and cases. The earlier
"equal or unordered" interpretation fit the clean-float subset accidentally.

New distinguishing pairs include zero/zero (false), 1/1 (true), 1/2 (false), 3/1 (true),
1.0/2.0 (false), adjacent unequal floats sharing bits (true), negative-zero/positive-zero (false),
and negative-zero/negative-zero (true). All six selectors agree, with flags 0 or 15 unchanged and
two then markers versus one else marker. The new model also checks every earlier capture, including
other flags and block shapes. The AC791N `hw` value becomes `as:if.ne.and.rr`; encodings, printed
floating syntax, oracle examples and encoding status are unchanged. Other cores remain untested.

## callns selects one of four return registers

Both callns waves completed: **32 probes**, all sixteen encoded x fields at flags 0 and 15.
All four return registers point to distinct RAM markers; the named GPR points elsewhere, and a stack
continuation is different again. The selected bank is:

| x low two bits | Selected bank | Observed relation |
| --- | --- | --- |
| 0 | rets | same bank as rtss |
| 1 | reti | same bank as rtns |
| 2 | retx | same bank as rtx/rthw |
| 3 | rete | same bank as rte |

No instruction-induced sp change is observed. Flags and icfg sampled before restoration stay unchanged.
The upper-field wave explicitly pushes r10..r15 so its operand can overwrite a saved-state GPR;
its sampled sp is 24 bytes below the original for that known push, then is restored. The model includes
both this stack traffic and every marker/readback instruction.

Run 4's r7/r15 cases had not aimed rete at a valid continuation: its baseline was zero. Their ROM
fallback, stack/r0 changes and resets therefore do not establish a flag-dependent callns rule.
The present experiment does not establish mode transitions, a general zero-target rule, or behaviour
outside this ROM context. It does not change the oracle's GPR field kind or syntax.

## copex: old destination alone is insufficient

**56 probes** completed. Each runs a preceding mode-14 or mode-15 copex, restores the exact original
r0/r1 with immediate loads, then executes mode 15 on r4/r5 = `0x10000000/0x08000000`.
All sixteen GPR inputs and flags are known at that target. The first wave varies final old destination,
adds 0/4/16 nops after the target, and repeats prior-mode sequences `(14,15,15,14)`.
The second uses 0/32/128 nops between the preceding operation and restoration/target, and 32 nops after.

Target results include `0x0d402406/0x06a01200`, `0x0d4023fe/0x06a011ec`, and
`0x0d402412/0x06a0121a`. Identical full GPR inputs and flags, the same immediate prefix, slot, stub,
sp and rets can give different outputs (copex-history 000 versus 004). Zero and all-ones old destination
variants and the waits retain the repeated history pattern. Only the destination pair changes and the
low flags remain 15. This strengthens the hidden-state/history evidence beyond the earlier comparison,
which had different old destinations. Unobserved special state and ROM/batch history are not controlled;
there is no justified numerical formula, latency model or state machine yet.

## Installing an own RAM handler

Facts from the local AC79 SDK C headers (source `ac79-sdk`, no source text or library code copied):
`hwi.h` gives a candidate 128-word table at `0x01C7FE00`, with indices 0 debug, 1 exception,
2 syscall and 120..127 software interrupts. The ROM's use of those indices was initially unproved.
A separate FD61 RAM read found index 1 `0x01E0024E`, index 2 `0x01C00DD8` and index 9
`0x01E018A0`. The full RAM snapshot is not committed: only these data facts are relevant.
This RAM is not uniformly initialized in download mode; vector 2 later read `0xF0A7356D` after a
power cycle, `0xF0A73D6D` after later recoveries, and `0x01C00DD8` after the idle reset. A read value is not automatically a valid handler.

The hook saves entries 0/1/2/120, prior reti/rete/retx/rets, psr, icfg, usp, ssp and sp, installs
own RAM code, supplies an owned scratch ssp, and restores the saved state on completion. Two csync
installation proofs completed. The second directly read the installed pointer and the restored original;
the handler count stayed zero. No interrupt-controller configuration or acknowledgement was requested.

`hw_probe_handler` saves GPRs/rets and flags, increments a counter, records icfg/reti/retx/rete and entry sp,
sets reti to an explicit cleanup continuation, restores GPRs/flags and tries rti. Tagged entries additionally
record which table entry was followed. `hw_probe_handler_0_rete` instead selects a rete/rte continuation
for the debug route. Handler stack writes are included in the executable models, including the words left
below the exit's own saved registers. Measured ROM RETI/vector baselines are model context inputs,
not independent validation of those values.

### Debug return and the four USB failures

The initial reti/rti handler returned captures for bkpt and hbkpt, including the tagged route-0 cases.
However, **every next upload/start after a debug reti/rti capture failed** with USB inspection timing out:

- handler-owned 003 (swi 0), after bkpt in 002;
- handler-routes 000 (hbkpt, slot `0x01C20000`), after hbkpt in handler-owned 008;
- handler-routes-b 001 (plain csync), after hbkpt in 000;
- handler-routes-rest 003 (plain csync), after bkpt in 002.

Logs reached M-Flasher's upload/start message, but no result was returned. Reaching the failed batch's
main instruction is **not established**. In particular these are not evidence that swi 0 or csync
intrinsically hangs, or that hbkpt intrinsically fails in the first slot. The unit was recovered with
user-confirmed power cycles before resumption each time. The four failures and manifests are retained.

The corrected debug handler sets rete to the address after the debug instruction and returns through rte.
Both bkpt and hbkpt then completed in **both RAM slots**, each followed by a successful plain csync
upload and capture. The sampled post-return sp, low flags and icfg match the pre-trap values before
cleanup. These tests establish a usable return path in this context; a successful capture alone had not.
They do not prove the detailed hidden-mode cause of each earlier USB failure or reinterpret run 4's
unhooked ROM failures as one known cause.

### Trap and event observations

| Form | Hooked observation | What remains open |
| --- | --- | --- |
| syscall | Entry 2; reti = instruction end, icfg `0x01090200`; supplied ssp; reti/rti return and later uploads work | Other privilege modes |
| bkpt | Entry 0; rete = instruction end, icfg `0x01090700`; current stack; rete/rte works in both slots | Wider debugger configuration/modes |
| hbkpt | Entry 0; rete = instruction address, same icfg/current stack; explicit skip with rete/rte works in both slots | Wider debug configuration/modes; causes of old ROM failures |
| swi 0 | Fresh hooked case completed, no handler entry; next upload works | Delivery, other numbers, acknowledgement |
| sevg | Completed, no handler entry | Event delivery and other-core effects |
| wfe after sevl | Completed, no handler entry | Unprimed wait, event consumption/routing |
| idle | Reset into app; no result | Wakeup/configuration; no handler entry can be inferred |
| btbclr | Two captures with one delayed entry; tagged route 1, supplied ssp; later upload works | Cause of exception and branch-buffer effect |

For btbclr, the original handler capture's saved GPRs include the first five readback operations:
r0 is the vector-2 address and r9 its installed pointer; reti = stub+24. The tagged follow-up instead
records reti = stub+34, before the r9 move. Its saved r2 already holds the original icfg `0x01090700`.
Handler icfg is `0x07010280`; after its rti, the repeated readback samples `0x07010700` before cleanup
restores the original. The handler explicitly resets reti to stub+2, so earlier readback instructions
execute again. Treating this as an immediate trap at btbclr would contradict the saved registers.
The table tag identifies the SDK-named exception entry, but the origin of the delayed exception and
btbclr's advertised branch-buffer effect remain unestablished. Both cases remain unmodeled.

Fresh swi 0 in handler-rte 002 completed with no hook entry, and its post-return samples match the
original sp/flags/icfg. Its earlier upload failure immediately after debug rti is not an instruction
result. No controller enabling or acknowledgement was attempted. The installed software hook only
covers index 120, and no other swi number was tested.

The successful syscall/hbkpt/btbclr captures bring the total to 773 of 803 non-parallel forms with results;
30 retain only failure observations. No `hw = resets` claim is added to a ROM-context trap or wait.
The unit was left in download mode; the last loaded runner is in `0x01C28000`, tracked by
`/tmp/hw/LASTSLOT` on the desktop. A future upload must use the other slot until reset/power cycle.

## Validation

`python3 -m pi32v2isa check` reported 1,165 entries and zero problems.
`python3 -m unittest discover -s tests` passed all 132 tests (one skipped). `check.py` passed on all
19 `hw/*/*.jsonl` files. Run 5 models match every capture of the 20 modeled forms; copex and the delayed
btbclr path remain explicitly unmodeled. A separate evidence audit matched all completed manifests,
patterns and 509 result records, with no outputs assigned to failed batches. A table diff against main
verified changes only to behavior summaries/notes and the six AND-block hardware aliases: no encoding,
syntax, oracle example or encoding status was changed.
