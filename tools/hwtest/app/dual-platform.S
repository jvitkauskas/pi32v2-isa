/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* Own experiment implementation; source facts and layout in APP.md and app4 README.
   Clobbers r0..r7; preserves r8..r15. CPU1 is held before shared RAM is initialized.
   The watchdog bounds failures; faults park for reset, never resume another core's probe. */
#define DMAIL 0x01C7CE00
#define DCFG 0x01C7CC00
#define DWORK 0x01C10000
	.text
app4_early:
	[--sp] = {rets, r0}
	call app4_stop
#ifdef HW_APP_PERSIST
	r1 = DCFG
	r0 = 0
	[r1+32] = r0
#endif
	{rets, r0} = [sp++]
	rts
app4_stop:
	r3 = 0x1EEE240
	r4 = [r3+0]
	r1 = 1
	r4 = r4 & r1
	if (r4 != 0) goto app4_stop_unlocked
	r1 = 0xE7
	[r3+0] = r1
app4_stop_unlocked:
	r5 = [r3+256]
	r6 = 0x003F0030
	r1 = ~0x003F0030
	r7 = r5 & r1
	[r3+256] = r7
	csync
	r2 = 0x1EEE004
	r7 = [r2+0]
	r1 = 2
	r7 = r7 | r1
	[r2+0] = r7
	r1 = 0xFFFFFFF7
	r7 = r7 & r1
	[r2+0] = r7
	csync
	r1 = 256
app4_stop_delay:
	r1 = r1 + -1
	if (r1 != 0) goto app4_stop_delay
	[r3+8] = r6
	csync
	[r3+256] = r5
	if (r4 != 0) goto app4_stop_done
	r1 = [r3+0]
	r2 = 1
	r1 = r1 & r2
	if (r1 == 0) goto app4_stop_done
	r1 = 0xE7
	[r3+0] = r1
app4_stop_done:
	csync
	rts
app4_unlock:
	r3 = 0x1EEE240
	r0 = [r3+0]
	r1 = 1
	r0 = r0 & r1
	if (r0 != 0) goto app4_unlock_done
	r1 = 0xE7
	[r3+0] = r1
app4_unlock_done:
	rts

app4_prepare:
	[--sp] = {rets}
	r1 = DCFG
#ifdef HW_APP_PERSIST
	r0 = [r1+32]
	if (r0 != 0) goto app4_live
#endif
	call app4_stop
	r1 = DCFG
	r0 = 1
	[r1+44] = r0
	/* All mailbox words are cleared while CPU1 is held; each batch gets a new nonce. */
	r1 = DMAIL
	r2 = 128
	r0 = 0
app4_mail_clear:
	[r1+0] = r0
	r1 = r1 + 4
	r2 = r2 + -1
	if (r2 != 0) goto app4_mail_clear
	r1 = RECORD
	r1 = [r1+36]
	r2 = r10 + 1
	r2 = r2 << 16
	r3 = app_plan
	r3 = [r3+0]
	r2 = r2 ^ r3
	[r1+128] = r2
	r3 = DMAIL
	[r3+16] = r2
	/* The worker is linked separately for RAM, not fetched from XIP while idle. */
	r1 = app4_worker_blob
	r2 = [r1+0]
	r1 = r1 + 4
	r3 = DWORK
app4_worker_copy:
	if (r2 == 0) goto app4_worker_copied
	r0 = [r1+0]
	[r3+0] = r0
	r1 = r1 + 4
	r3 = r3 + 4
	r2 = r2 + -4
	goto app4_worker_copy
app4_worker_copied:
	csync
	r1 = 0x10800
	r0 = 0x4000
	[r1+0] = r0
	r0 = 0
	[r1+4] = r0
	r0 = -1
	[r1+8] = r0
	r0 = 0x4009
	[r1+0] = r0
	r1 = 0x1EEF300
	r2 = 32
	r0 = 0
app4_clear_peer_irqs:
	[r1+0] = r0
	r1 = r1 + 4
	r2 = r2 + -1
	if (r2 != 0) goto app4_clear_peer_irqs
	r1 = 0x1EEF3A4
	r0 = 255
	[r1+0] = r0
	call app4_unlock
	r7 = DCFG
	[r7+0] = r0
	r1 = 0x1EEE380
	r0 = [r1+0]
	[r7+4] = r0
	r0 = [r1+4]
	[r7+8] = r0
	r0 = [r1+8]
	[r7+12] = r0
	r0 = [r1+12]
	[r7+16] = r0
	r0 = -1
	[r1+0] = r0
	[r1+8] = r0
	r0 = 0
	[r1+4] = r0
	[r1+12] = r0
	r1 = 0x1EEE348
	r0 = [r1+0]
	[r7+20] = r0
	r2 = 0xFFFFFFFB
	r0 = r0 & r2
	[r1+0] = r0
	r1 = 0x1C7FFF8
	r0 = DWORK
	[r1+0] = r0
	r1 = 0x10008
	r0 = [r1+0]
	[r7+24] = r0
	r2 = 8
	r0 = r0 | r2
	[r1+0] = r0
	csync
	r1 = 0x1EEE004
	r0 = [r1+0]
	r2 = RECORD
	r2 = [r2+36]
	[r2+120] = r0
	r3 = 8
	r0 = r0 | r3
	[r1+0] = r0
	r3 = 0xFFFFFFFD
	r0 = r0 & r3
	[r1+0] = r0
	[r2+124] = r0
	csync
	r3 = 0x10804
	r4 = [r3+0]
	r5 = 480000
	r6 = DMAIL
app4_wait_ready:
	csync
	r0 = [r6+32]
	r1 = [r6+16]
	if (r0 == r1) goto app4_ready
	r0 = [r3+0]
	r0 = r0 - r4
	if (r0 < r5) goto app4_wait_ready
	r0 = 0
	[r2+112] = r0
	r0 = [r3+0]
	r0 = r0 - r4
	[r2+116] = r0
	r1 = 0x1EEF27C
	r0 = [r1+0]
	[r2+148] = r0
	r1 = 0x1EEF258
	r0 = [r1+0]
	[r2+132] = r0
	r0 = [r6+56]
	[r2+156] = r0
	r1 = r2 + 192
	r3 = r6 + 32
	r4 = 16
app4_failed_snapshot:
	r0 = [r3+0]
	[r1+0] = r0
	r1 = r1 + 4
	r3 = r3 + 4
	r4 = r4 + -1
	if (r4 != 0) goto app4_failed_snapshot
	call app4_stop
	goto intentional_stall
app4_ready:
	r1 = DCFG
	r0 = [r1+44]
	[r2+112] = r0
	r0 = 1
	[r1+32] = r0
	r0 = [r3+0]
	r0 = r0 - r4
	[r2+116] = r0
	r0 = [r6+40]
	[r2+132] = r0
	r0 = [r6+44]
	[r2+136] = r0
	r0 = [r6+48]
	[r2+140] = r0
	r0 = [r6+52]
	[r2+144] = r0
	r1 = 0x1EEF27C
	r0 = [r1+0]
	[r2+148] = r0
	r7 = DCFG
	r0 = [r7+24]
	r1 = 0x10008
	[r1+0] = r0
	r1 = 0x1EEE244
	r0 = [r1+0]
	[r2+176] = r0
	call app4_unlock
	r7 = DCFG
	r1 = 0x1EEE248
	r0 = -1
	[r1+0] = r0
	r1 = 0x1EEE380
	r0 = [r7+4]
	[r1+0] = r0
	r0 = [r7+8]
	[r1+4] = r0
	r0 = [r7+12]
	[r1+8] = r0
	r0 = [r7+16]
	[r1+12] = r0
	r1 = 0x1EEE348
	r0 = [r7+20]
	[r1+0] = r0
	r0 = [r7+0]
	if (r0 != 0) goto app4_start_unlocked
	r1 = 0x1EEE240
	r0 = 0xE7
	[r1+0] = r0
app4_start_unlocked:
	csync
	{pc} = [sp++]

app4_quiesce:
	[--sp] = {rets}
	cli
	r0 = 0
	icfg = r0
	r1 = RECORD
	r1 = [r1+36]
	r0 = [r1+0]
	r2 = 2
	if (r0 == r2) goto app4_quiesce_only
	r2 = DMAIL
	r0 = [r2+56]
	[r1+156] = r0
	r3 = 0x1EEF27C
	r3 = [r3+0]
	[r1+188] = r3
#ifdef HW_APP_PERSIST
	r3 = r9 + -1
	if (r10 != r3) goto app4_live_snapshot
#endif
	call app4_stop
	r1 = RECORD
	r1 = [r1+36]
	r2 = DMAIL
	r0 = [r2+56]
	[r1+160] = r0
	r3 = 10000
app4_stopped_window:
	r3 = r3 + -1
	if (r3 != 0) goto app4_stopped_window
	csync
	r3 = [r2+56]
	[r1+164] = r3
	if (r0 != r3) goto intentional_stall
	r0 = 1
	[r1+184] = r0
app4_peer_snapshot:
	r2 = r2 + 32
	r1 = r1 + 192
	r3 = 16
app4_capture_peer:
	r0 = [r2+0]
	[r1+0] = r0
	r1 = r1 + 4
	r2 = r2 + 4
	r3 = r3 + -1
	if (r3 != 0) goto app4_capture_peer
	goto app4_quiesce_done
app4_quiesce_only:
	call app4_stop
app4_quiesce_done:
	{pc} = [sp++]

app4_trap:
	/* Core-specific fault records; no resumption into a different core's case. */
	r2 = cnum
	if (r2 != 0) goto app4_fault
	r2 = 63
	if (r0 == r2) goto app4_regular_trap
	r2 = 120
	if (r0 >= r2) goto app4_regular_trap
app4_fault:
	cli
	r2 = cnum
	r1 = 0x1C7CD00
	r3 = r2 << 7
	r1 = r1 + r3
	[r1+4] = r2
	[r1+8] = r0
	r3 = reti
	[r1+12] = r3
	r3 = rete
	[r1+16] = r3
	r3 = sp
	[r1+20] = r3
	r3 = icfg
	[r1+24] = r3
	r3 = r2 << 9
	r4 = 0x1EEF0D4
	r3 = r3 + r4
	r3 = [r3+0]
	[r1+28] = r3
	r3 = 0x1EEE244
	r3 = [r3+0]
	[r1+32] = r3
	r3 = 1
	[r1+0] = r3
	csync
app4_fault_park:
	goto app4_fault_park

#ifdef HW_APP_PERSIST
app4_live:
	r0 = 3
	[r1+44] = r0
	r2 = RECORD
	r2 = [r2+36]
	r6 = DMAIL
	r0 = [r6+16]
	[r2+128] = r0
	r7 = [r6+56]
	[r2+168] = r7
	r1 = 0x10800
	r0 = 0x4000
	[r1+0] = r0
	r0 = 0
	[r1+4] = r0
	r0 = -1
	[r1+8] = r0
	r0 = 0x4009
	[r1+0] = r0
	r1 = 0x1EEE004
	r0 = [r1+0]
	[r2+120] = r0
	[r2+124] = r0
	r3 = 0x10804
	r4 = [r3+0]
	r5 = 480000
app4_wait_live:
	csync
	r0 = [r6+56]
	if (r0 != r7) goto app4_is_live
	r0 = [r3+0]
	r0 = r0 - r4
	if (r0 < r5) goto app4_wait_live
	call app4_stop
	goto intentional_stall
app4_is_live:
	[r2+172] = r0
	goto app4_ready
app4_live_snapshot:
	[r1+160] = r0
	r3 = 10000
app4_live_window:
	r3 = r3 + -1
	if (r3 != 0) goto app4_live_window
	csync
	r3 = [r2+56]
	[r1+164] = r3
	if (r0 == r3) goto intentional_stall
	r0 = 0
	[r1+184] = r0
	goto app4_peer_snapshot
#endif

#ifdef HW_APP_BATCH_RESET
app4_boot_again:
	r1 = RECORD
	r0 = 0
	[r1+12] = r0
	csync
	r1 = MARKER
	r0 = 0
	[r1+0] = r0
	[r1+4] = r0
	[r1+8] = r0
	[r1+12] = r0
	csync
	r1 = PWR
	r0 = [r1+0]
	r2 = 16
	r0 = r0 | r2
	[r1+0] = r0
	csync
app4_reset_wait:
	goto app4_reset_wait
#endif
