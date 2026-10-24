/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* Retention probe (tools/hwtest/APP.md, step 1): an FM-1 application that records how it was entered, fills
   RAM areas with a known pattern, and asks the mask ROM for USB download mode. The host then reads RAM back with
   the download-mode runner (m-flasher run-ram ... --read) and sees which words survived the reset and the ROM.

   m-bootloader calls the entry (0x02000120) with r0 = the boot object, interrupts disabled, on its own stacks
   (m-bootloader docs/SPEC.md §6.5). Nothing here uses a stack or enables an interrupt.

   The record at PROBE (32 words):
     +0 "HWAP"   +4 the number of starts seen (1 when the record was not there before)
     +8 r0 at entry   +12 sp   +16 ssp   +20 usp   +24 psr   +28 icfg   +32 rets   +36 reti   +40 rete   +44 retx
     +48 the number of areas   +52 the pattern's seed
   Each area (AREAS, start and length in words) gets word i = address XOR SEED. */

#define PROBE	0x01C7C000
#define SEED	0x5AA5F00F
#define MARKER	0x01C7FD80		/* "usb_update_mode" + NUL: download mode at the next reset (SPEC §4.2) */
#define PWR	0x00010000		/* power control: bit 4 requests a software reset (SPEC §2.2) */

	.section .entry,"ax"
	.globl app_entry
app_entry:
	goto 1f				/* as JieLi's images start: an entry, and a return at +2 */
	rts
1:	r4 = PROBE
	r5 = [r4+0]
	r6 = 0x50415748			/* "HWAP" */
	r7 = 1
	if (r5 != r6) goto 2f
	r7 = [r4+4]
	r7 = r7 + 1
2:	[r4+0] = r6
	[r4+4] = r7
	[r4+8] = r0
	r1 = sp
	[r4+12] = r1
	r1 = ssp
	[r4+16] = r1
	r1 = usp
	[r4+20] = r1
	r1 = psr
	[r4+24] = r1
	r1 = icfg
	[r4+28] = r1
	r1 = rets
	[r4+32] = r1
	r1 = reti
	[r4+36] = r1
	r1 = rete
	[r4+40] = r1
	r1 = retx
	[r4+44] = r1
	r1 = SEED
	[r4+52] = r1
	r8 = areas
	r9 = 0
next_area:
	r2 = [r8+0]			/* start */
	r3 = [r8+4]			/* words */
	if (r3 == 0) goto areas_done
	r9 = r9 + 1
fill:
	r1 = SEED
	r1 = r1 ^ r2
	[r2+0] = r1
	r2 = r2 + 4
	r3 = r3 + -1
	if (r3 != 0) goto fill
	r8 = r8 + 8
	goto next_area
areas_done:
	[r4+48] = r9
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

	.p2align 2
/* RAM outside the bootloader's stacks (0x01C02000..0x01C0A800), the probe record and the retained area */
areas:
	.4byte 0x01C0C000, 1024
	.4byte 0x01C10000, 1024
	.4byte 0x01C18000, 1024
	.4byte 0x01C30000, 1024
	.4byte 0x01C38000, 1024
	.4byte 0x01C40000, 1024
	.4byte 0x01C50000, 1024
	.4byte 0x01C60000, 1024
	.4byte 0x01C70000, 1024
	.4byte 0x01C78000, 1024
	.4byte 0x01C7C080, 992
	.4byte 0x01C7F000, 512
	.4byte 0, 0
