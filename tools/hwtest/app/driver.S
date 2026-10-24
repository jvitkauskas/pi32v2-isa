/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* Test application (tools/hwtest/APP.md): runs download-mode runner batches (runner.S, built by gen.py --app)
   as an FM-1 application, then asks the mask ROM for USB download mode, where the host reads the results back.

   gen.py --app writes app.S beside the batches: app_batches = count, then per batch {image in flash, length in
   bytes, RAM base}. Each batch is linked at its own RAM base (0x01C30000 + 0x8000 k), so every batch's results
   stay in RAM. For each batch the application copies the image to its base, calls its entry as the ROM does
   (r0 = {send, receive, the word the handler address goes to}), then calls the handler with an FC60 command
   block: the runner runs its cases exactly as in download mode. Its answer goes to app_send, which drops it.

   It runs on m-bootloader's stacks (in 0x01C02000..0x01C0A800, SPEC §2.1), with interrupts disabled as at entry.
   The record at RECORD (also read back):
     +0 "HWAR"   +4 the number of starts seen   +8 batches finished   +12 the batch being run, +1 (0: none)
     +16 r0 at entry   +20 sp   +24 psr   +28 icfg */

#define RECORD	0x01C7C000
#define MARKER	0x01C7FD80		/* "usb_update_mode" + NUL: download mode at the next reset (SPEC §4.2) */
#define PWR	0x00010000		/* power control: bit 4 requests a software reset (SPEC §2.2) */

	.section .entry,"ax"
	.globl app_entry
app_entry:
	goto 1f				/* as JieLi's images start: an entry, and a return at +2 */
	rts
1:
#ifdef HW_APP_EXPERIMENT
	sp = 0x01C0D000
	ssp = 0x01C0F000
	call app_initialize
#else
	r4 = RECORD
	r5 = [r4+0]
	r6 = 0x52415748			/* "HWAR" */
	r7 = 1
	if (r5 != r6) goto 2f
	r7 = [r4+4]
	r7 = r7 + 1
2:	[r4+0] = r6
	[r4+4] = r7
	r1 = 0
	[r4+8] = r1
	[r4+12] = r1
	[r4+16] = r0
	r1 = sp
	[r4+20] = r1
	r1 = psr
	[r4+24] = r1
	r1 = icfg
	[r4+28] = r1

#endif

	r8 = app_batches
	r9 = [r8+0]			/* batches */
	r8 = r8 + 4
#ifdef HW_APP_EXPERIMENT
	r1 = RECORD
	r10 = [r1+8]
	r2 = r10 << 3
	r3 = r10 << 2
	r8 = r8 + r2
	r8 = r8 + r3
#else
	r10 = 0                        /* this batch */
#endif
next_batch:
	if (r10 == r9) goto done
	r4 = RECORD
	r1 = r10 + 1
	[r4+12] = r1
	r1 = [r8+0]			/* image */
	r2 = [r8+4]			/* bytes, a multiple of 4 */
	r3 = [r8+8]			/* base */
	r11 = r3
copy:
	if (r2 == 0) goto copied
	r0 = [r1+0]
	[r3+0] = r0
	r1 = r1 + 4
	r3 = r3 + 4
	r2 = r2 + -4
	goto copy
copied:
	csync
#ifdef HW_APP_EXPERIMENT
	call app_prepare
#endif
	r0 = app_params			/* the runner's entry: hw_entry(params) puts its handler at [params+8] */
	call r11
	r0 = app_command
	r1 = app_answer
	r2 = app_handler
	r2 = [r2+0]
	call r2
#ifdef HW_APP_EXPERIMENT
	call app_finish
#endif
	r10 = r10 + 1
	r4 = RECORD
	[r4+8] = r10
	r8 = r8 + 12
	goto next_batch

done:
#ifdef HW_APP_EXPERIMENT
	call app_quiesce
#endif
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
3:	goto 3b

/* the ROM's send(data, length): the answer is not needed */
app_send:
	rts

	.p2align 2
app_params:
	.4byte app_send, 0, app_handler
/* a command block as the ROM passes it: the CDB at +15, FC 60 */
app_command:
	.byte 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xFC, 0x60, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF
	.byte 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF

	.bss
	.p2align 2
app_handler:	.space 4
app_answer:	.space 16
