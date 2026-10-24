/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* Hardware test runner: a RAM plug-in for the AC791N mask ROM's USB download mode (m-bootloader docs/SPEC.md
   §10.1). The ROM calls hw_entry(params) with params = {send, receive, handler slot}; it installs hw_handler
   and returns. The handler answers two private commands (16-byte CDB, opcode big endian at CDB+0, CDB at
   command block +15):
     FC60  run every test case in hw_cases; answer: FC 60, case count (BE u32), "HWT1"
     FD61  +2 address (BE u32), +6 length (BE u16): send that many bytes of RAM (the results)
   Everything else goes back to the ROM (return 0). See tools/hwtest/README.md.

   Record format 2. A case (hw_cases, 20 words): stub address, r0..r15, psr flags, sp, rets. Its result
   (hw_results, 53 words): the 16 registers as pushed, psr, sp afterwards, the exit taken (0: the stub's end,
   1: hw_taken or the stub's own taken label), rets afterwards, the number of scratch words that differ from
   hw_pattern (leaving out the 16 words below the final sp, where the exit pushes the registers), then up to
   16 (word index, value) pairs of them. Before each case the scratch (hw_nwords words)
   is reset from hw_pattern; the case enters its stub by popping the stub address from [sp - 4], so that word
   holds the stub address on entry. */

	.section .entry,"ax"
	.globl hw_entry
hw_entry:
	r1 = [r0+0]
	r2 = hw_send
	[r2+0] = r1
	r3 = [r0+8]
	r1 = hw_handler
	csync
	[r3+0] = r1
	csync
	r0 = 0
	rts

	.text
/* hw_handler(r0 = command block, r1 = 16-byte answer): 1 if handled, 0 to leave it to the ROM */
hw_handler:
	[--sp] = {rets, r15-r4}
	r4 = r0
	r5 = r1
	r6 = b[r4+15] (u)
	r7 = b[r4+16] (u)
	r6 = r6 << 8
	r6 |= r7
	r7 = 0xFC60
	if (r6 == r7) goto do_run
	r7 = 0xFD61
	if (r6 == r7) goto do_read
	r0 = 0
	{pc, r15-r4} = [sp++]

do_run:
	r8 = hw_ncases
	r8 = [r8+0]
	r9 = hw_cases
	r10 = hw_results
	r11 = 0
run_loop:
	if (r11 == r8) goto run_done
	r12 = hw_in
	r14 = r9 + 4
	r13 = 19
copy_in:
	r0 = [r14+0]
	[r12+0] = r0
	r14 = r14 + 4
	r12 = r12 + 4
	r13 = r13 + -1
	if (r13 != 0) goto copy_in
	r0 = [r9+0]
	call hw_run
	r12 = hw_out
	r13 = 53
copy_out:
	r0 = [r12+0]
	[r10+0] = r0
	r12 = r12 + 4
	r10 = r10 + 4
	r13 = r13 + -1
	if (r13 != 0) goto copy_out
	r9 = r9 + 80
	r11 = r11 + 1
	goto run_loop
run_done:
	r0 = 0
	[r5+0] = r0
	[r5+4] = r0
	[r5+8] = r0
	[r5+12] = r0
	r0 = 0xFC
	b[r5+0] = r0
	r0 = 0x60
	b[r5+1] = r0
	r0 = r8 >> 24
	b[r5+2] = r0
	r0 = r8 >> 16
	b[r5+3] = r0
	r0 = r8 >> 8
	b[r5+4] = r0
	b[r5+5] = r8
	r0 = 0x48
	b[r5+6] = r0
	r0 = 0x57
	b[r5+7] = r0
	r0 = 0x54
	b[r5+8] = r0
	r0 = 0x31
	b[r5+9] = r0
	call want16
	r0 = r5
	call send
	r0 = 1
	{pc, r15-r4} = [sp++]

do_read:
	r6 = b[r4+17] (u)          /* CDB+2..5: address, big endian (the CDB starts at command block +15) */
	r6 = r6 << 8
	r7 = b[r4+18] (u)
	r6 |= r7
	r6 = r6 << 8
	r7 = b[r4+19] (u)
	r6 |= r7
	r6 = r6 << 8
	r7 = b[r4+20] (u)
	r6 |= r7
	r8 = b[r4+21] (u)          /* CDB+6..7: length, big endian */
	r8 = r8 << 8
	r7 = b[r4+22] (u)
	r8 |= r7
read_loop:
	if (r8 == 0) goto read_done
	r1 = r8
	r7 = 512
	if (r1 <= r7) goto read_chunk
	r1 = r7
read_chunk:
	r9 = r1
	r0 = r6
	call send
	r6 = r6 + r9
	r8 = r8 - r9
	goto read_loop
read_done:
	r0 = 1
	{pc, r15-r4} = [sp++]

/* want16: r1 = min(transfer length in command block +8..11 (LE), 16); r4 = command block */
want16:
	r1 = b[r4+11] (u)
	r1 = r1 << 8
	r2 = b[r4+10] (u)
	r1 |= r2
	r1 = r1 << 8
	r2 = b[r4+9] (u)
	r1 |= r2
	r1 = r1 << 8
	r2 = b[r4+8] (u)
	r1 |= r2
	r2 = 16
	if (r1 <= r2) goto want_ok
	r1 = r2
want_ok:
	rts

/* send: the ROM's send callback with r0 = data, r1 = length */
send:
	[--sp] = {rets}
	r2 = hw_send
	r2 = [r2+0]
	call r2
	{pc} = [sp++]

/* hw_run(r0 = stub): runs one case. Resets the scratch, sets rets, psr and sp from hw_in, puts the stub address
   at [sp - 4], loads r0..r15 and pops the stub address into pc; the stub ends with `goto hw_exit0`. */
	.globl hw_run
hw_run:
	[--sp] = {rets, r15-r4}
	r1 = sp
	r2 = hw_savedsp
	[r2+0] = r1
	r1 = hw_scratch
	r2 = hw_pattern
	r3 = hw_nwords
	r3 = [r3+0]
reset:
	r4 = [r2+0]
	[r1+0] = r4
	r1 = r1 + 4
	r2 = r2 + 4
	r3 = r3 + -1
	if (r3 != 0) goto reset
	r2 = hw_in
	r3 = [r2+72]
	rets = r3
	r5 = [r2+68]
	r5 = r5 + -4
	[r5+0] = r0
	r1 = psr
	r3 = [r2+64]
	r4 = hw_flagmask           /* which psr bits the case sets: 0xF (the condition flags), or 0 to leave psr */
	r4 = [r4+0]
	r3 = r3 & r4
	r4 = ~r4
	r1 = r1 & r4
	r1 = r1 | r3
	psr = r1
	sp = r5
	r15 = hw_in
	r0 = [r15+0]
	r1 = [r15+4]
	r2 = [r15+8]
	r3 = [r15+12]
	r4 = [r15+16]
	r5 = [r15+20]
	r6 = [r15+24]
	r7 = [r15+28]
	r8 = [r15+32]
	r9 = [r15+36]
	r10 = [r15+40]
	r11 = [r15+44]
	r12 = [r15+48]
	r13 = [r15+52]
	r14 = [r15+56]
	r15 = [r15+60]
	{pc} = [sp++]

/* The exits: push the registers onto the case's stack, then record them, psr, sp, the exit, rets and the
   scratch words that changed into hw_out, and return from hw_run on the runner's own stack. */
	.globl hw_exit0, hw_exit1, hw_taken
hw_exit0:
	[--sp] = {r15-r0}
	r1 = psr
	r0 = 0
	goto exit_common
hw_taken:
hw_exit1:
	[--sp] = {r15-r0}
	r1 = psr
	r0 = 1
exit_common:
	r2 = hw_out
	[r2+64] = r1
	[r2+72] = r0
	r1 = rets
	[r2+76] = r1
	r1 = sp
	r3 = r1 + 64
	[r2+68] = r3
	r4 = 16
save:
	r3 = [r1+0]
	[r2+0] = r3
	r1 = r1 + 4
	r2 = r2 + 4
	r4 = r4 + -1
	if (r4 != 0) goto save
	r1 = hw_savedsp
	r1 = [r1+0]
	sp = r1
	r2 = hw_out
	r3 = hw_scratch
	r4 = hw_pattern
	r5 = 0                     /* word index */
	r6 = 0                     /* words that differ */
	r7 = r2 + 84               /* next (index, value) pair */
	r8 = hw_nwords
	r8 = [r8+0]
	r11 = 16
	r12 = [r2+68]              /* the exit's own push filled the 64 bytes below the case's final sp: skip them */
	r13 = r12 + -64
diff:
	r9 = [r3+0]
	r10 = [r4+0]
	if (r9 == r10) goto same
	if (r3 < r13) goto differs
	if (r3 < r12) goto same
differs:
	if (r6 >= r11) goto counted
	[r7+0] = r5
	[r7+4] = r9
	r7 = r7 + 8
counted:
	r6 = r6 + 1
same:
	r3 = r3 + 4
	r4 = r4 + 4
	r5 = r5 + 1
	r8 = r8 + -1
	if (r8 != 0) goto diff
	[r2+80] = r6
	{pc, r15-r4} = [sp++]

	.data
	.p2align 2
hw_send:	.4byte 0
	.globl hw_in, hw_out
hw_savedsp:	.4byte 0
hw_in:		.space 76
hw_out:		.space 212

/* Optional RAM-only trap probe. Cases install and restore the candidate vector table themselves.
   The tested ROM route and its ability to return via rti are experimental. */
	.text
	.globl hw_probe_handler
/* Tagged entries preserve GPRs and flags before recording which candidate vector was followed. */
	.globl hw_probe_handler_0, hw_probe_handler_1, hw_probe_handler_2, hw_probe_handler_120
	.globl hw_probe_handler_0_rete
hw_probe_handler_0_rete:
	[--sp] = {r1-r0}
	r0 = hw_probe_context
	r1 = 1
	[r0+76] = r1
	r0 = 0
	goto hw_probe_tag
hw_probe_handler_0:
	[--sp] = {r1-r0}
	r0 = 0
	goto hw_probe_tag
hw_probe_handler_1:
	[--sp] = {r1-r0}
	r0 = 1
	goto hw_probe_tag
hw_probe_handler_2:
	[--sp] = {r1-r0}
	r0 = 2
	goto hw_probe_tag
hw_probe_handler_120:
	[--sp] = {r1-r0}
	r0 = 120
hw_probe_tag:
	r1 = hw_probe_context
	[r1+72] = r0
	{r1-r0} = [sp++]
	goto hw_probe_handler
hw_probe_handler:
	[--sp] = {rets, r15-r0}
	r0 = psr
	[--sp] = {r0}
	r0 = hw_probe_seen
	r1 = [r0+0]
	r1 = r1 + 1
	[r0+0] = r1
	r0 = hw_probe_context
	r1 = icfg
	[r0+52] = r1
	r1 = reti
	[r0+56] = r1
	r1 = retx
	[r0+60] = r1
	r1 = rete
	[r0+64] = r1
	r1 = sp
	r1 = r1 + 72
	[r0+68] = r1
	r0 = hw_probe_resume
	r0 = [r0+0]
	r1 = hw_probe_context
	r1 = [r1+76]
	if (r1 != 0) goto hw_probe_return_rete
	reti = r0
	{r0} = [sp++]
	psr = r0
	{rets, r15-r0} = [sp++]
	rti
hw_probe_return_rete:
	rete = r0
	{r0} = [sp++]
	psr = r0
	{rets, r15-r0} = [sp++]
	rte
	.data
	.p2align 2
	.globl hw_probe_seen, hw_probe_resume, hw_probe_context
hw_probe_seen:	.4byte 0
hw_probe_resume:	.4byte 0
hw_probe_context:	.space 80
