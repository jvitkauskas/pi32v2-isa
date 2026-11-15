/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT */
/* Boot probe entry (../README.md): record every register as the loader hands over, before
   anything else runs, then set up our own stacks and call main. The record is at REC (retained RAM, read back
   from download mode). One word is pushed on the loader's stack to free r1; sp is recorded as it was. */
#define REC 0x01C7C000
	.section .entry,"ax"
	.globl _start
_start:
	goto 1f
	rts
1:	[--sp] = {r1}
	r1 = REC
	[r1+8] = r0
	r0 = [sp+0]
	[r1+12] = r0
	[r1+16] = r2
	[r1+20] = r3
	[r1+24] = r4
	[r1+28] = r5
	[r1+32] = r6
	[r1+36] = r7
	[r1+40] = r8
	[r1+44] = r9
	[r1+48] = r10
	[r1+52] = r11
	[r1+56] = r12
	[r1+60] = r13
	[r1+64] = r14
	[r1+68] = r15
	r0 = sp
	r0 = r0 + 4
	[r1+72] = r0
	r0 = ssp
	[r1+76] = r0
	r0 = usp
	[r1+80] = r0
	r0 = psr
	[r1+84] = r0
	r0 = icfg
	[r1+88] = r0
	r0 = rets
	[r1+92] = r0
	r0 = reti
	[r1+96] = r0
	r0 = rete
	[r1+100] = r0
	r0 = retx
	[r1+104] = r0
	r0 = 0x01EEE218
	r0 = [r0+0]
	[r1+108] = r0
	r0 = 0x42505242			/* "BRPB" */
	[r1+0] = r0
	cli
	ssp = __sstack_top
	sp = __stack_top
	r1 = __data_load
	r2 = __data_start
	r3 = __data_end
2:	if (r2 >= r3) goto 3f
	r0 = [r1+0]
	[r2+0] = r0
	r1 = r1 + 4
	r2 = r2 + 4
	goto 2b
3:	r2 = __bss_start
	r3 = __bss_end
	r0 = 0
4:	if (r2 >= r3) goto 5f
	[r2+0] = r0
	r2 = r2 + 4
	goto 4b
5:	call main
6:	goto 6b
