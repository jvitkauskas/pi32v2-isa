/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* A download-mode RAM plug-in that starts the installed application: when the mask ROM calls it, it clears the
   download-mode marker at 0x01C7FD80 (m-bootloader docs/SPEC.md §4.2) and requests a software reset (power
   control bit 4, §2.2). The ROM then boots normally. It never returns, so M-Flasher's run-ram times out. */

	.section .entry,"ax"
	.globl app_entry
app_entry:
	r4 = 0x01C7FD80
	r1 = 0
	[r4+0] = r1
	[r4+4] = r1
	[r4+8] = r1
	[r4+12] = r1
	csync
	r4 = 0x00010000
	r1 = [r4+0]
	r2 = 0x10
	r1 = r1 | r2
	[r4+0] = r1
	csync
1:	goto 1b
