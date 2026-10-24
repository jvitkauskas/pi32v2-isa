/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* Independently written platform experiments, not an operating-system interrupt layer.
   Plan: run identity, then {resume address, mode, priority} per batch. Modes:
   0 no timer, 1 intentional watchdog stall, 2 timer armed before the runner.
   Journal: status,count,vector,emu,dbg,reti,rete,retx,rets,psr,icfg,entry_sp,r0..r15.
   +112 onward is reserved for case-owned samples. Header +36 holds the current journal pointer. */
	.text
	.globl app_trap
app_initialize:
	r7 = RECORD
	r1 = [r7+0]
	r2 = 0x32504148
	r3 = app_plan
	r3 = [r3+0]
	r4 = [r7+32]
	if (r1 != r2) goto fresh_experiment
	if (r3 != r4) goto fresh_experiment
	goto retained_experiment
fresh_experiment:
	r4 = r7
	r5 = 1024
	r6 = 0
zero_journals:
	[r4+0] = r6
	r4 = r4 + 4
	r5 = r5 + -1
	if (r5 != 0) goto zero_journals
	[r7+0] = r2
	[r7+32] = r3
retained_experiment:
	[r7+16] = r0
	r1 = sp
	[r7+20] = r1
	r1 = psr
	[r7+24] = r1
	r1 = icfg
	[r7+28] = r1
	r1 = [r7+4]
	r1 = r1 + 1
	[r7+4] = r1
	r2 = [r7+12]
	if (r2 == 0) goto no_interrupted_batch
	r3 = r2 + -1
	r3 = r3 << 8
	r3 = r3 + 0x100
	r3 = r3 + r7
	r4 = 3
	[r3+0] = r4
	[r7+8] = r2
	r4 = 0
	[r7+12] = r4
no_interrupted_batch:
	r2 = 16
	if (r1 < r2) goto init_platform
	r2 = app_batches
	r2 = [r2+0]
	[r7+8] = r2
init_platform:
	[--sp] = {rets}
	cli
	r0 = 0
	icfg = r0
	r1 = 0x01EEF100
	r2 = 32
clear_sources:
	[r1+0] = r0
	r1 = r1 + 4
	r2 = r2 + -1
	if (r2 != 0) goto clear_sources
	r1 = 0x01EEF1A4
	r0 = 255
	[r1+0] = r0
	r1 = 0x01EEE240
	r0 = 0xE7
	[r1+0] = r0
	r1 = 0x01EEE248
	r0 = -1
	[r1+0] = r0
	r1 = 0x01EEF0D4
	[r1+0] = r0
	r1 = app_vectors
	r2 = 0x01C7FE00
	r3 = 128
install_vectors:
	r0 = [r1+0]
	[r2+0] = r0
	r1 = r1 + 4
	r2 = r2 + 4
	r3 = r3 + -1
	if (r3 != 0) goto install_vectors
	csync
	{pc} = [sp++]

/* P33 three-byte operation (r0 op, r1 address, r2 data). Bounded polling; r0..r7 clobbered. */
app_p33:
	[--sp] = {rets}
	r5 = r0
	r6 = r1
	r7 = r2
	r3 = 0x13E08
	r4 = [r3+0]
	r0 = 0xFFFFFEFE
	r4 = r4 & r0
	r0 = 13
	r4 = r4 | r0
	[r3+0] = r4
	r0 = r5
	call p33_byte
	r0 = r6
	call p33_byte
	r0 = r7
	call p33_byte
	r4 = [r3+0]
	r1 = 0xFFFFFEFE
	r4 = r4 & r1
	[r3+0] = r4
	{pc} = [sp++]
p33_byte:
	[r3+4] = r0
	r4 = [r3+0]
	r1 = 16
	r4 = r4 | r1
	[r3+0] = r4
	csync
	r2 = 100000
p33_busy:
	r4 = [r3+0]
	r1 = 2
	r4 = r4 & r1
	if (r4 == 0) goto p33_ready
	r2 = r2 + -1
	if (r2 != 0) goto p33_busy
	r4 = RECORD
	r1 = 1
	[r4+44] = r1
p33_ready:
	r0 = [r3+4]
	rts

app_prepare:
	[--sp] = {rets}
	cli
	r0 = 0
	icfg = r0
	r1 = r10 << 8
	r1 = r1 + 0x100
	r2 = RECORD
	r1 = r1 + r2
	[r2+36] = r1
	r0 = 1
	[r1+0] = r0
	r0 = r10 << 3
	r3 = r10 << 2
	r0 = r0 + r3
	r3 = app_plan
	r3 = r3 + r0
	r0 = [r3+4]
	[r2+40] = r0
	/* The app's watchdog is reset mode, timeout code 0xB (nominal 2 s). */
	r0 = 0
	r1 = 0x80
	r2 = 0
	call app_p33
	r0 = 0x40
	r1 = 0x17
	r2 = 0xBF
	call app_p33
	r0 = 0
	r1 = 0x80
	r2 = 0x4B
	call app_p33
	r0 = 0x20
	r1 = 0x80
	r2 = 0x10
	call app_p33
	r1 = 0x01EEF100
	r0 = 0xFFF
	[r1+0] = r0
	r1 = 0x01EEF13C
	r0 = 0x77777777
	[r1+0] = r0
	r0 = r10 << 3
	r1 = r10 << 2
	r0 = r0 + r1
	r1 = app_plan
	r1 = r1 + r0
	r0 = [r1+8]
	r2 = 1
	if (r0 == r2) goto intentional_stall
	r2 = 2
	if (r0 != r2) goto sources_ready
	r0 = [r1+12]
	r0 = r0 << 1
	r2 = 1
	r0 = r0 | r2
	r0 = r0 << 28
	r1 = 0x01EEF11C
	[r1+0] = r0
	r1 = 0x10900
	r0 = 0x4000
	[r1+0] = r0
	r0 = 0
	[r1+4] = r0
	r0 = 60000
	[r1+8] = r0
	r0 = 0x4019
	[r1+0] = r0
sources_ready:
#ifdef HW_APP_ADVANCED
	call app3_prepare
#endif
	r0 = 0x300
	icfg = r0
	csync
	{pc} = [sp++]
intentional_stall:
	goto intentional_stall

app_finish:
	[--sp] = {rets}
	call app_quiesce
	r1 = RECORD
	r1 = [r1+36]
	r0 = 2
	[r1+0] = r0
	{pc} = [sp++]
app_quiesce:
	[--sp] = {rets}
#ifdef HW_APP_ADVANCED
	call app3_quiesce
#endif
	cli
	r0 = 0
	icfg = r0
	r1 = 0x10900
	r0 = 0x4000
	[r1+0] = r0
	r0 = 0
	r1 = 0x80
	r2 = 0
	call app_p33
	{pc} = [sp++]

app_trap:
	/* All GPRs/rets and flags have already been saved by the vector stub. */
	r1 = RECORD
	r1 = [r1+36]
	r2 = [r1+4]
	r2 = r2 + 1
	[r1+4] = r2
	[r1+8] = r0
	r2 = 0x01EEF0D4
	r2 = [r2+0]
	[r1+12] = r2
	r2 = 0x01EEE244
	r2 = [r2+0]
	[r1+16] = r2
	r2 = reti
	[r1+20] = r2
	r2 = rete
	[r1+24] = r2
	r2 = retx
	[r1+28] = r2
	r2 = rets
	[r1+32] = r2
	r2 = [sp+0]
	[r1+36] = r2
	r2 = icfg
	[r1+40] = r2
	r2 = sp
	r2 = r2 + 72
	[r1+44] = r2
	r2 = sp
	r2 = r2 + 4
	r3 = r1 + 48
	r4 = 16
save_trap_gprs:
	r5 = [r2+0]
	[r3+0] = r5
	r2 = r2 + 4
	r3 = r3 + 4
	r4 = r4 + -1
	if (r4 != 0) goto save_trap_gprs
	r2 = 63
	if (r0 == r2) goto timer_return
	r2 = 120
#ifdef HW_APP_ADVANCED
	if (r0 >= r2) goto app3_soft
#else
	if (r0 >= r2) goto soft_return
#endif
	r2 = 0x01EEF0D4
	r3 = -1
	[r2+0] = r3
	r2 = 0x01EEE248
	[r2+0] = r3
	r2 = RECORD
	r2 = [r2+40]
	if (r0 == 0) goto debug_return
	reti = r2
	goto normal_return
debug_return:
	rete = r2
	{r0} = [sp++]
	psr = r0
	{rets, r15-r0} = [sp++]
	csync
	rte
timer_return:
	r2 = 0x10900
	r3 = [r2+0]
	r4 = 0x4000
	r3 = r3 | r4
	[r2+0] = r3
	goto normal_return
soft_return:
	r0 = r0 + -120
	r2 = 1
	r2 = r2 << r0
	r3 = 0x01EEF1A4
	[r3+0] = r2
normal_return:
	{r0} = [sp++]
	psr = r0
	{rets, r15-r0} = [sp++]
	csync
	rti
