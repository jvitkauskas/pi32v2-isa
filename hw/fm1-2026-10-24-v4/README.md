# FM-1 hardware run 4, 2026-10-24: control, returns and special-register writes

The fourth run of [tools/hwtest](../../tools/hwtest/README.md) on the same AC791N FM-1, in record format 2.
All images were built with this repository's assembler and linker. Only M-Flasher `run-ram` and, after
resets, `download-mode` were used; no flash write was requested. The flasher was
`/opt/m-flasher/m-flasher`, SHA-256
`1d8404c84febd3def6d8281aa279e59e20a488a36f16c3f2ac19b920dd67d5b8`.

Every previously untested non-parallel form was attempted. Forty additional forms returned results:
770 of the 803 non-parallel forms now have captures across the four runs; the other 33 only have failure
observations. The 282 previously tested parallel twins are unchanged by this run.

## Evidence and execution

There were **213 attempted batches: 181 completed, 27 reset, five hung**. `results.jsonl` contains 566
records, including calibration nops, covering 46 forms. The self-test passed 26/26. `patterns.json` holds
the initial scratch for each completed batch. `outcomes.json` records each attempted batch, its slot,
exact case manifest and failure log when preserved. A failure has no invented instruction output.
One initial `writes-rest-006` log was lost when a desktop reboot cleared `/tmp`; its observed runner
status is recorded separately. Batches were subsequently kept in `~/pi32v2-hw-v4` on the desktop.

The JSON input files correspond to generator wave names. For example:

```sh
python3 tools/hwtest/gen.py DIR --wave selftest --per-entry 4 --first-slot 0x01C20000
python3 tools/hwtest/gen.py DIR --cases hw/fm1-2026-10-24-v4/control.json --batch 1 --first-slot 0x01C28000
python3 tools/hwtest/gen.py DIR --cases hw/fm1-2026-10-24-v4/writes.json --batch 1 --first-slot 0x01C28000
```

Every non-self-test batch contains two calibration nops and exactly one probe. Consecutive uploads
alternate slots. `writes` stopped at 053; `writes-rest` resumed at original case 054 and stopped at its
006; `writes-tail` resumed after that. `traps` stopped at 003; `traps-tail` tested trigger, a primed wfe,
and idle. `more` stopped at 001; `more-tail` omitted that failed case and the separately tested primed
wfe. `retry-hangs` retried all four original hangs in order, stopping at hbkpt. `hbkpt-final` was its last,
isolated retry in the other slot. Other completed waves are `followup`, `followup-sti`, `returns`,
`conditions`, `block-grid` and `callns-grid`. Inputs prepared after a stop are not evidence of execution;
use `outcomes.json` to identify actual attempts and starting slots.

The special-register probes save prior state, read back the result, then restore it. `before` and
`after` list the surrounding table forms, whose effects are included in each result. `entry` is the
setup address popped by the runner; `stub` is the tested instruction's address. Pops preload known
words at sp, then restore sp and the affected visible registers. Return probes use distinct RAM
marker positions to identify which return register they follow. The immediate pc-write input names
the batch's own `hw_taken` address; that numeric constant must be resolved again if rebuilding with a
changed layout or starting slot.

Models in `tools/hwtest/semantics/v4.py` evaluate the surrounding instructions too. ROM entry values
of reti/usp are measured context, as in run 2; matching those entry values is not independent validation.
Every captured case of the 45 modeled forms matches; `callns.r` has no general model. No encoding,
syntax, oracle example or encoding status was changed from hardware evidence.

## USB failures and retries

The first three pop failures and first hbkpt hang used the original USB path. Power cycles sometimes
left the desktop's USB inspection stalled; the user rebooted the desktop to recover. A recovery attempt
also blocked in M-Flasher's connection stage before upload and is not counted as an instruction attempt.
The supplied step script's unbounded `lsusb` calls could block after a hang, so execution switched to a
bounded version, now kept as `tools/hwtest/runstep.sh`. It stops on a hang, checks USB before uploading,
checks `/tmp/hw/LASTSLOT`, and only re-enters download mode after observing the app identity.

The user moved the FM-1 from the front-panel path to a motherboard USB port before `traps-tail`.
All three previously hung pop sequences then completed in `retry-hangs`:

- rete-only `pop.srl`: supplied `0x12345679` read back as `0x02345678`.
- rete-only `pop.srmask`: the same readback.
- multi-register `pop.srmask` selecting reti, retx, rets, sr4 and psr: consecutive words loaded in ascending
  register-number order, matching the already completed `pop.srl` case. sr4 still read zero.

Those earlier pop failures are **not established as instruction traps**. USB path, ROM state and history
changed between attempts. Both the failures and successful retries remain in the evidence.

`hbkpt` behaved differently: the original attempt and the motherboard-port retry, both in slot
`0x01C20000`, hung without results and USB inspection timed out. Its final isolated retry in
`0x01C28000` reset into the app, and the script recovered download mode. Placement and ROM context were
not varied independently; there is no basis to assign an intrinsic halt or a slot-dependent rule.
No more tests were run after that final reset. The unit was last observed in download mode, with the
reset clearing the slot marker.

Validation before committing: `python3 -m pi32v2isa check` reported 1,165 entries and zero problems;
`python3 -m unittest discover -s tests` ran 126 tests successfully (one skipped); and `check.py` passed on
all 18 `hw/*/*.jsonl` files. A table comparison against the parent also verified that only summaries,
notes and source lists changed.

## Control forms

- `cli` clears icfg bit 9; `sti` sets it. `cli.r` also returns the previous icfg in its operand register.
  `sti.r` takes bit 9 from the operand, preserving the other observed icfg bits. Tests start with bit 9
  clear or set, use operands 0, `0x01090700` and `0x200`, and flags 0/15 or 5. Flags stay unchanged.
  Interrupt delivery and other configuration bits were not measured; the probes restore icfg.
- `ssync`, `lockclr`, `sevl`, and `lockset` followed by `lockclr`: no visible register, flag, sp, rets or
  scratch change with flags 0 and 15. This does not establish ordering, exclusion or event delivery.
- `sevg`: one case with flags 0 completed without visible changes; the next with flags 15 reset. These
  batches also differ in slot and history, so the flag value is not established as the cause.
- `trigger` and `wfe` immediately preceded by `sevl`: completed with flags 5 and no visible changes.
  Other-core activity, event consumption, and an unprimed wait were not tested.
- `swi 0`: completed with flags 5 and no visible changes; delivery and other numbers remain open.
- `bkpt`: with `[sp]` holding `hw_taken`, continued there and advanced sp by four. Registers, flags and
  rets stayed unchanged. This describes the ROM context, not debugger semantics.
- `btbclr` (both flag values), `syscall` and `idle` reset into the app without results. `hbkpt` failures
  and retries are described above.

## Returns and jumps

- `rti`, `rtx`, `rte` selected reti, retx and rete respectively, skipping a fall-through marker.
- `rtns`, `rtss`, `rthw`, with all four return registers aimed at distinct marker positions, selected
  reti, rets and retx respectively. Flags, current sp and icfg were unchanged in these cases. Other
  modes and entry/exit transitions remain open.
- `callns.r` remains unresolved. With operand r0 and flags 0, 5 or 15 it followed rets rather than the
  operand and left rets unchanged. With r7 or r15 and flags 0 it also followed rets, but r0 became zero
  and a readback before restoration showed sp had advanced by four. The r7/r15 cases with flags 15 reset.
  These observations do not establish a rule for the other operand values or mode effects.
- `gotoss.xl` with offset 4 branched relative to the end of its six-byte instruction and saved that next
  instruction address in rets. Registers, flags, sp and scratch stayed unchanged. Mode effects are open.

## Special-register writes and pops

- Both `mov.sr_r` and `li.sr_u32`: reti/rete/retx/rets retain bits 26..1. Inputs `0xFFFFFFFF` and
  `0x12345679` read back as `0x07FFFFFE` and `0x02345678`. psr writes 0 and 15 read back those flags.
  The saved value is restored before the exit, so final flags/return registers include that restoration.
- usp, ssp and sp retain the aligned RAM pointers written. sr4/cnum and generic uspn/sspn reads remain
  zero after the tested nonzero writes. icfgn/icfgs were only rewritten as zero; icfg only with its prior
  value. This does not establish their writable masks or hidden state.
- General-register pc writes aimed at stub+8 and at `hw_taken` both fell through. The immediate pc write
  aimed at its own `hw_taken` also fell through, without visible changes. By contrast, a pc-only
  `pop.srmask` transferred to the word at sp and advanced sp by four.
- Dedicated `sp = usp` / `sp = ssp` copy the preloaded normal bank pointer; the reverse moves read back
  the saved sp from that bank. The dedicated `uspn`/`sspn` moves also access normal usp/ssp in this ROM
  context, even though the generic interfaces for the n registers read zero. Follow-ups explicitly save
  and restore the normal banks. The original n-move probes did not know about that aliasing; this is an
  additional reason not to attribute their later pop failures solely to the pop instruction.
- Empty pop masks changed nothing. Single-register masks read back the supplied value with the same
  cuts/zero reads above. A loaded sp wins over the old-sp increment. Multi-register pops selecting
  reti/retx/rets/sr4/psr loaded in ascending register-number order; pc and other mixed masks were not
  combined. Preserve the failure/retry qualifications above.
