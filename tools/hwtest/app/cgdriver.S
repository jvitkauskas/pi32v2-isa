/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* Code generator test application (tools/llvm/cgtest.py): calls compiled functions on the FM-1 and keeps what
   they return, then asks the mask ROM for USB download mode, where the host reads the results back.

   cg_tests (from cgtest.py) = count, then per test {function, r0, r1, r2, r3}; cg_results gets r0 and r1 of
   each call. The functions follow JieLi's C convention (docs/ABI.md): r4..r15 are preserved, so this loop keeps
   its state in r8..r12. It first copies .data to RAM and clears .bss (fm1app.py's app_data_* and app_bss_*).
   It runs on m-bootloader's stacks, with interrupts disabled as at entry.

   The record at RECORD: +0 "HWCG"   +4 starts seen   +8 calls finished   +12 the test being run, +1 */

#define RECORD	0x01C7C000
#define MARKER	0x01C7FD80		/* "usb_update_mode" + NUL: download mode at the next reset (SPEC §4.2) */
#define PWR	0x00010000		/* power control: bit 4 requests a software reset (SPEC §2.2) */

	.section .entry,"ax"
	.globl app_entry
app_entry:
	goto 1f
	rts
1:	r4 = RECORD
	r5 = [r4+0]
	r6 = 0x47435748			/* "HWCG" */
	r7 = 1
	if (r5 != r6) goto 2f
	r7 = [r4+4]
	r7 = r7 + 1
2:	[r4+0] = r6
	[r4+4] = r7
	r1 = 0
	[r4+8] = r1
	[r4+12] = r1

	r1 = app_data_load		/* .data from flash to RAM */
	r2 = app_data_start
	r3 = app_data_end
3:	if (r2 >= r3) goto 4f
	r0 = b[r1+0] (u)
	b[r2+0] = r0
	r1 = r1 + 1
	r2 = r2 + 1
	goto 3b
4:	r2 = app_bss_start		/* .bss cleared */
	r3 = app_bss_end
	r0 = 0
5:	if (r2 >= r3) goto 6f
	b[r2+0] = r0
	r2 = r2 + 1
	goto 5b

6:	r8 = cg_tests
	r9 = [r8+0]			/* tests */
	r8 = r8 + 4
	r10 = cg_results
	r12 = 0				/* this test */
next:
	if (r12 == r9) goto done
	r4 = RECORD
	r1 = r12 + 1
	[r4+12] = r1
	r11 = [r8+0]
	r0 = [r8+4]
	r1 = [r8+8]
	r2 = [r8+12]
	r3 = [r8+16]
	call r11
	[r10+0] = r0
	[r10+4] = r1
	r10 = r10 + 8
	r8 = r8 + 20
	r12 = r12 + 1
	r4 = RECORD
	[r4+8] = r12
	goto next

done:
	r4 = RECORD
	r1 = 0
	[r4+12] = r1
	r4 = MARKER
	r1 = 0x5f627375			/* "usb_" */
	[r4+0] = r1
	r1 = 0x61647075			/* "upda" */
	[r4+4] = r1
	r1 = 0x6d5f6574			/* "te_m" */
	[r4+8] = r1
	r1 = 0x0065646f			/* "ode" NUL */
	[r4+12] = r1
	csync
	r4 = PWR
	r1 = [r4+0]
	r2 = 0x10
	r1 = r1 | r2
	[r4+0] = r1
	csync
7:	goto 7b
