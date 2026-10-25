# CPU1 on the FM-1 AC791N

This is the lifecycle exercised by [application run app4](../hw/fm1-2026-10-24-app4/README.md), for the
second core of this FM-1. The repository calls the boot core CPU0 and the worker CPU1; fm1-base's public
API calls the worker `cpu2`. This is a tested setup, not a complete specification of the chip.

The source facts were read from fm1-base origin/main at
[aa2b3bc8](https://github.com/charlesvestal/fm1-base/tree/aa2b3bc8f7900cd1820947cb93ca0e8ecc4189e7)
(include/plat.h, device/cpu2.c, device/main_fm1.c and DESIGN.md), its
[loom-hooks merge](https://github.com/charlesvestal/fm1-base/commit/e35f7e2c6904ff1a3eed10035474c8cf089c0b88),
and its pinned felucca-bsp at
[d6b8f771](https://github.com/hugelton/felucca-bsp/tree/d6b8f771795be04d77e15d72a79f474a723796d7)
(chip/fm1_cpu1.h, fm1_cpu1_stop.h, fm1_cpu1.S, fm1_guard.h and fm1_irq.h). Those files are MPL-2.0.
The AC79 SDK's Apache-2.0 csfr.h supplies register layout facts only. No implementation or wording was
copied; the [dual platform](../tools/hwtest/app/dual-platform.S) and [RAM worker](../tools/hwtest/app/peer.S)
are independently written MIT-0 experiment code. Hardware outcomes and the exact revisions used by each
attempt are in the app4 report and attempts.json.

## Boot once, then send work

The working application starts CPU1 once during each whole-chip boot, with CPU0 interrupts disabled and
before normal peripheral work. It keeps that worker alive between jobs. Nine successive software-reset
boots pass the startup checks, and the persistent-worker calibration completes nine batches in one boot.
These observations are separate from the earlier attempt whose intentional-reset journal was wrong.

Late re-entry after holding CPU1 is not established. In the diagnostic, the first start succeeds; after a
stop, clearing the mailbox and trying the same release sequence gives no ready nonce or heartbeat. CPU1's
sampled PC is in ROM at 0x01E0005A, not in the worker; the wait expires after 480000 TIMER4 ticks. A
watchdog restart recovers that attempt. This is consistent with fm1-base permitting plat_cpu2_set(1)
only during app_init, before audio and timers. It does not identify the missing ROM handshake or prove
that a late restart is impossible in a different setup. Do not use the hold/release bits as a demonstrated
warm-reset API.

## Sequence used by the test application

1. **Hold before shared-memory initialization.** Once CPU0 has selected its private stacks, its first
   helper applies the stop procedure below, preserving the boot argument. It does this before clearing
   journals, mailbox, or copying code. fm1-base similarly holds CPU1 at the start of fm1_cstart, before
   clearing RAM. The loom-hooks merge supplies the equivalent early hook for an application's own core.
2. **Prepare owned memory.** The worker image is assembled/linked for 0x01C10000, copied there, and
   followed by csync. Its user stack ends at 0x01C12000 and supervisor stack at 0x01C14000. Code and stacks
   do not overlap the batch slots or CPU0 stacks. Clear the mailbox while CPU1 is held and give this boot
   a nonzero nonce. CPU0's request fields and CPU1's reply fields use separate 32-byte lines.
3. **Disable CPU1 IRQ sources.** Clear the 32 words at 0x01EEF300..0x01EEF37C and software-pending bits
   through 0x01EEF3A4. This is CPU1's bank; CPU0's source words start at 0x01EEF100. CPU1 remains polled
   in these experiments. The RAM vector table is installed by the app; its word at 0x01C7FFF8 is reserved
   for CPU1 startup and is not simultaneously available as an ordinary vector-126 handler.
4. **Open the startup path.** Read DBG_WR_EN (0x01EEE240) bit 0 before changing its write access:
   writing 0xE7 toggles that access, so an unconditional write is insufficient. Preserve the four PC-limit
   words at 0x01EEE380..0x01EEE38C and temporarily make both intervals cover the address space. CPU1
   traverses ROM on its way to the worker. Preserve C0_WR_LIMIT_EN at 0x01EEE348 and clear bit 2 while
   publishing the entry word in protected top RAM. This is application-owned guard configuration;
   it is not a request to bypass an unknown operating system's protection policy.
5. **Publish and release.** Write 0x01C10000 to 0x01C7FFF8. Save SYS_DIV at 0x00010008 and set bit 3;
   synchronize. In C1_CON at 0x01EEE004, set bit 3 with one read/modify/write, then clear bit 1 with a
   subsequent write. The retained journal records the held and released values.
6. **Establish CPU1's context.** The worker entry disables interrupts and writes its local icfg as zero,
   assigns usp, sp **and ssp**, sets reti to its main loop and uses rti to leave the ROM entry context.
   Its main loop again disables delivery, records cnum and the three stack pointers, then publishes the
   nonce reply with csync. Captures report cnum=1, usp/sp=0x01C12000 and ssp=0x01C14000. App3 omitted
   the explicit ssp initialization.
7. **Check before using it.** CPU0 waits for the exact nonce, bounded by 480000 ticks of the separately
   configured TIMER4. The data also checks core identity and stacks. A stale Boolean ready flag is not
   enough. On timeout the experiment holds CPU1 and takes its bounded watchdog recovery; no peer result
   is fabricated. Restore SYS_DIV, saved PC intervals and top-write protection after successful entry;
   preserve the prior debug write-access state. Clear and record startup debug causes as the source
   sequence requires. The exact assembly and source snapshots make the ordering reviewable.
8. **Dispatch jobs.** CPU0 writes command/arguments, synchronizes, then increments the request sequence.
   CPU1 processes a new sequence, publishes its samples, synchronizes, then acknowledges that sequence.
   CPU0 requires the matching acknowledgement. Subsequent batches check that the existing heartbeat
   advances; they do not stop, clear the mailbox and pretend the worker re-entered. The journal labels
   initial entry and live reuse separately. The worker loop executes from owned RAM, with no libraries.
9. **Stop before handover.** Finish or abandon the outstanding job explicitly, apply the stop procedure,
   then verify that heartbeat samples stay equal over a further bounded window. Only then does the test
   application request download mode and reset. A command that did not acknowledge is not a completed
   result. This protocol does not make arbitrary user code safe to interrupt at an unknown side effect.

TIMER4 here uses the source-described oscillator configuration, but this run reports counter ticks rather
than a newly calibrated instruction or startup latency. Different images/clock setups must establish
their own timeout. The journal contains the actual startup intervals.

## Stop procedure, executed by CPU0

Preserve DBG_WR_EN's access state and DBG_EN at 0x01EEE340. Open writes if necessary. Temporarily clear
DBG_EN bits selected by 0x003F0030, synchronize, set C1_CON bit 1, then clear bit 3. Wait a short bounded
interval (256 loop decrements here), clear the delayed bus-cause bits with 0x003F0030 at DBG_MSG_CLR
(0x01EEE248), synchronize, and restore DBG_EN and the original write-access state. This order and the
delayed-cause handling are source facts from fm1_cpu1_stop.h. Holding a core can interrupt a bus access;
app3 used the opposite bit order without this masking/cleanup.

The sampled heartbeat may advance between the pre-stop read and the hold taking effect; the two samples
after the hold must agree. The test checks this distinction. It does not infer a full reset of CPU1's
registers or ROM state from the fact that the heartbeat stopped.

## Fault ownership and limits

The app records cnum, the selected vector, reti/rete, sp/icfg, the faulting core's EMU_MSG bank and DBG_MSG.
A CPU1 fault parks CPU1; it never returns to a CPU0 case continuation. CPU0 can also receive debug reports
about the other core; a zero CPU0 EMU_MSG alone therefore does not identify an innocent instruction or
exclude a CPU1 problem. fm1-base's fault hook and felucca-bsp's core-specific fault handling supplied these
facts. A failed app handover still requires operator recovery; the app4 report records one such failure
without inventing which planned instruction ran.

The working protocol and finite memory-sharing probes do not specify a complete memory model, all cache
operations, IRQ delivery on CPU1, every icfg mode, or a universal power/event-enable configuration. The
app4 report separates event observations and lock/ordering tests from these lifecycle results. Nothing
here changes an instruction encoding, syntax or confirmation status.
