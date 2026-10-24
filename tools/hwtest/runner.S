/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* Hardware test runner: a RAM plug-in for the AC791N mask ROM's USB download mode (m-bootloader docs/SPEC.md
   §10.1). The ROM calls hw_entry(params) with params = {send, receive, handler slot}; it installs hw_handler
   and returns. The handler answers two private commands (16-byte CDB, opcode big endian at CDB+0, CDB at
   command block +15):
     FC60  run every test case in hw_cases; answer: FC 60, case count (BE u32), "HWT1"
     FD61  +2 address (BE u32), +6 length (BE u16): send that many bytes of RAM (the results)
   Everything else goes back to the ROM (return 0). See tools/hwtest/README.md. */

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
	r13 = 17
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
	r13 = 17
copy_out:
	r0 = [r12+0]
	[r10+0] = r0
	r12 = r12 + 4
	r10 = r10 + 4
	r13 = r13 + -1
	if (r13 != 0) goto copy_out
	r9 = r9 + 72
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

/* hw_run(r0 = stub): runs one case. Loads r0..r15 from hw_in[0..15] and the low four psr bits from hw_in[16],
   then enters the stub through rets; the stub ends with `goto hw_exit`. */
	.globl hw_run
hw_run:
	[--sp] = {rets, r15-r4}
	rets = r0
	r1 = psr
	r2 = hw_in
	r3 = [r2+64]
	r4 = hw_flagmask           /* which psr bits the case sets: 0xF (the condition flags), or 0 to leave psr */
	r4 = [r4+0]
	r3 = r3 & r4
	r4 = ~r4
	r1 = r1 & r4
	r1 = r1 | r3
	psr = r1
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
	rts

/* hw_exit: stores the registers as pushed (their order on the stack is found by the nop cases) and psr into
   hw_out, then returns from hw_run */
	.globl hw_exit
hw_exit:
	[--sp] = {r15-r0}
	r0 = psr
	r1 = hw_out
	[r1+64] = r0
	r2 = [sp+0]
	[r1+0] = r2
	r2 = [sp+4]
	[r1+4] = r2
	r2 = [sp+8]
	[r1+8] = r2
	r2 = [sp+12]
	[r1+12] = r2
	r2 = [sp+16]
	[r1+16] = r2
	r2 = [sp+20]
	[r1+20] = r2
	r2 = [sp+24]
	[r1+24] = r2
	r2 = [sp+28]
	[r1+28] = r2
	r2 = [sp+32]
	[r1+32] = r2
	r2 = [sp+36]
	[r1+36] = r2
	r2 = [sp+40]
	[r1+40] = r2
	r2 = [sp+44]
	[r1+44] = r2
	r2 = [sp+48]
	[r1+48] = r2
	r2 = [sp+52]
	[r1+52] = r2
	r2 = [sp+56]
	[r1+56] = r2
	r2 = [sp+60]
	[r1+60] = r2
	sp += 64
	{pc, r15-r4} = [sp++]

	.data
	.p2align 2
hw_send:	.4byte 0
	.globl hw_in, hw_out
hw_in:		.space 68
hw_out:		.space 68
