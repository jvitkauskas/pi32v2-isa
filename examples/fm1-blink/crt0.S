/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* Start-up of an FM-1 application built with the open toolchain. m-bootloader calls the entry (0x02000120) with
   interrupts disabled, on its own stacks (m-bootloader docs/SPEC.md section 6.5); this sets up the application's
   stacks, copies .data, clears .bss and calls main. */

	.section .entry,"ax"
	.globl _start
_start:
	goto 1f				/* as JieLi's images start: an entry, and a return at +2 */
	rts
1:	cli
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
