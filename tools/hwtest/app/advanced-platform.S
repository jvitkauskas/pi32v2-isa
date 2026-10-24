/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* Own experimental code. Source facts and memory layout: APP.md, app3 README.
   Journal +112: nested gate; +116: depth; +120: maximum depth; +124: trace length;
   +128..188: entry/exit tokens (vector and vector+256). Mailbox: 0x01C7CE00.
   The watchdog is already armed when CPU1 is released. */
#define MAIL 0x01C7CE00
	.text
app3_prepare:
	[--sp] = {rets}
	r1 = 0x1EEE004
	r0 = [r1+0]
	r2 = 0xFFFFFFF7
	r0 = r0 & r2
	[r1+0] = r0
	r2 = 2
	r0 = r0 | r2
	[r1+0] = r0
	csync
	/* Read this batch mode after the common platform setup. */
	r0 = r10 << 3
	r1 = r10 << 2
	r0 = r0 + r1
	r1 = app_plan
	r1 = r1 + r0
	r0 = [r1+8]
	r1 = 3
	if (r0 != r1) goto app3_prepare_done
	r7 = MAIL
	r1 = 0
	r2 = 16
	r3 = r7
app3_clear_mail:
	[r3+0] = r1
	r3 = r3 + 4
	r2 = r2 + -1
	if (r2 != 0) goto app3_clear_mail
	r1 = 0x1C7FFF8
	r0 = app3_cpu1_entry
	[r1+0] = r0
	r1 = 0x10008
	r0 = [r1+0]
	[r7+20] = r0
	r2 = 8
	r0 = r0 | r2
	[r1+0] = r0
	r1 = 0x1EEE004
	r0 = [r1+0]
	[r7+24] = r0
	r2 = 8
	r0 = r0 | r2
	[r1+0] = r0
	r2 = 0xFFFFFFFD
	r0 = r0 & r2
	csync
	[r1+0] = r0
	r0 = 1000000
app3_wait_core:
	csync
	r1 = [r7+0]
	if (r1 != 0) goto app3_core_ready
	r0 = r0 + -1
	if (r0 != 0) goto app3_wait_core
app3_core_ready:
	r1 = 0x10008
	r0 = [r7+20]
	[r1+0] = r0
app3_prepare_done:
	{pc} = [sp++]

app3_quiesce:
	/* Apply the source-described CPU1 stop controls; retain the header/mailbox. */
	cli
	r0 = 0
	icfg = r0
	r1 = 0x1EEE004
	r0 = [r1+0]
	r2 = 0xFFFFFFF7
	r0 = r0 & r2
	[r1+0] = r0
	r2 = 2
	r0 = r0 | r2
	[r1+0] = r0
	csync
	r7 = MAIL
	r0 = [r7+0]
	if (r0 == 0) goto app3_quiesced
	r1 = RECORD
	r1 = [r1+36]
	r1 = r1 + 112
	r2 = 16
app3_copy_mail:
	r0 = [r7+0]
	[r1+0] = r0
	r7 = r7 + 4
	r1 = r1 + 4
	r2 = r2 + -1
	if (r2 != 0) goto app3_copy_mail
app3_quiesced:
	rts

app3_cpu1_entry:
	cli
	r0 = 0
	icfg = r0
	usp = 0x1C12000
	sp = 0x1C14000
	reti = app3_cpu1_main
	rti
app3_cpu1_main:
	cli
	r0 = 0
	icfg = r0
	r7 = MAIL
	r0 = cnum
	[r7+28] = r0
	r0 = 1
	[r7+0] = r0
	csync
app3_cpu1_poll:
	csync
	r0 = [r7+4]
	r1 = [r7+8]
	if (r0 == r1) goto app3_cpu1_poll
	r2 = 2
	if (r0 == r2) goto app3_cpu1_local
	r2 = 3
	if (r0 == r2) goto app3_cpu1_global
	r2 = 4
	if (r0 == r2) goto app3_cpu1_delayed
	r2 = 8
	if (r0 == r2) goto app3_cpu1_wait
	r2 = 5
	if (r0 == r2) goto app3_cpu1_wait
	r2 = 9
	if (r0 == r2) goto app3_cpu1_many
	r2 = 6
	if (r0 == r2) goto app3_cpu1_many
	goto app3_cpu1_ack
app3_cpu1_local:
	sevl
	goto app3_cpu1_ack
app3_cpu1_global:
	sevg
	goto app3_cpu1_ack
app3_cpu1_delayed:
	r2 = 1000000
app3_cpu1_delay:
	r2 = r2 + -1
	if (r2 != 0) goto app3_cpu1_delay
	sevg
	goto app3_cpu1_ack
app3_cpu1_wait:
	r2 = 1
	[r7+32] = r2
	csync
	wfe
	csync
	[r7+36] = r2
	goto app3_cpu1_ack
app3_cpu1_many:
	r2 = 1
	[r7+32] = r2
	csync
	r2 = 128
app3_cpu1_wfes:
	wfe
	r2 = r2 + -1
	if (r2 != 0) goto app3_cpu1_wfes
app3_cpu1_ack:
	r2 = 1
	[r7+36] = r2
	r2 = [r7+12]
	r2 = r2 + 1
	[r7+12] = r2
	[r7+8] = r0
	csync
	goto app3_cpu1_poll

app3_soft:
	/* Save the outer return PC and controller state BEFORE opening the nesting gates. */
	r2 = reti
	[--sp] = {r2}
	r2 = icfg
	[--sp] = {r2}
	[--sp] = {r0}
	/* Acknowledge first: the outer source must not recursively retrigger. */
	r2 = r0 + -120
	r3 = 1
	r2 = r3 << r2
	r3 = 0x1EEF1A4
	[r3+0] = r2
	r2 = [r1+116]
	r2 = r2 + 1
	[r1+116] = r2
	r3 = [r1+120]
	if (r2 <= r3) goto app3_depth_recorded
	[r1+120] = r2
app3_depth_recorded:
	call app3_trace
	r2 = 120
	if (r0 != r2) goto app3_soft_done
	swi 1
	r2 = [r1+112]
	if (r2 == 0) goto app3_nested_disabled
	r3 = 2
	if (r2 == r3) goto app3_sti_only
	r3 = 3
	if (r2 == r3) goto app3_gate8_only
	r2 = 0x300
	icfg = r2
	goto app3_nested_disabled
app3_sti_only:
	sti
	goto app3_nested_disabled
app3_gate8_only:
	r2 = 0x100
	icfg = r2
app3_nested_disabled:
	r2 = 10000
app3_nested_window:
	r2 = r2 + -1
	if (r2 != 0) goto app3_nested_window
	cli
app3_soft_done:
	r2 = 0
	icfg = r2
	r0 = [sp+0]
	r0 = r0 + 256
	call app3_trace
	r2 = [r1+116]
	r2 = r2 + -1
	[r1+116] = r2
	{r0} = [sp++]
	{r2} = [sp++]
	icfg = r2
	{r2} = [sp++]
	reti = r2
	goto normal_return
app3_trace:
	r2 = [r1+124]
	r3 = 16
	if (r2 >= r3) goto app3_trace_full
	r3 = r2 << 2
	r3 = r3 + r1
	[r3+128] = r0
	r2 = r2 + 1
	[r1+124] = r2
app3_trace_full:
	rts
