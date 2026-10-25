/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* Own polled CPU1 worker. Link at 0x01C10000 with fm1app --plugin; copy before release.
   CPU0 owns mailbox +0..31, CPU1 +32..95. These occupy separate 32-byte lines. */
#define PEERMAIL 0x01C7CE00
	.section .entry,"ax"
	.globl app_entry
app_entry:
	cli
	r0 = 0
	icfg = r0
	usp = 0x1C12000
	sp = 0x1C14000
	ssp = 0x1C14000
	reti = peer_main
	rti
	.text
peer_main:
	cli
	r0 = 0
	icfg = r0
	r7 = PEERMAIL
	r0 = cnum
	[r7+40] = r0
	r0 = usp
	[r7+44] = r0
	r0 = ssp
	[r7+48] = r0
	r0 = sp
	[r7+52] = r0
	r6 = 0
	r5 = 0
	csync
	r0 = [r7+16]
	[r7+32] = r0
	csync
peer_loop:
	r6 = r6 + 1
	[r7+56] = r6
	csync
	r0 = [r7+0]
	if (r0 == r5) goto peer_loop
	r1 = [r7+4]
	r2 = 0
	[r7+64] = r2
	[r7+68] = r2
	[r7+72] = r2
	[r7+80] = r2
	[r7+88] = r2
	csync
	[r7+92] = r0
	csync

	r2 = 2
	if (r1 == r2) goto peer_sevl
	r2 = 3
	if (r1 == r2) goto peer_sevg
	r2 = 4
	if (r1 == r2) goto peer_delayed_event
	r2 = 5
	if (r1 == r2) goto peer_waits
	r2 = 6
	if (r1 == r2) goto peer_waits
	r2 = 7
	if (r1 == r2) goto peer_waits
	r2 = 8
	if (r1 == r2) goto peer_waits
	r2 = 10
	if (r1 == r2) goto peer_lock_once
	r2 = 11
	if (r1 == r2) goto peer_increment
	r2 = 12
	if (r1 == r2) goto peer_message
	r2 = 13
	if (r1 == r2) goto peer_store_buffer
	r2 = 14
	if (r1 == r2) goto peer_delayed_choice
	r2 = 15
	if (r1 == r2) goto peer_idle
	goto peer_ack
peer_sevl:
	sevl
	goto peer_ack
peer_sevg:
	sevg
	goto peer_ack
peer_delayed_event:
	r8 = [r7+8]
peer_delay:
	r8 = r8 + -1
	if (r8 != 0) goto peer_delay
	r8 = 0x10804
	r2 = [r8+0]
	[r7+68] = r2
	r2 = 1
	[r7+64] = r2
	csync
	sevg
	csync
	r2 = [r8+0]
	[r7+72] = r2
	goto peer_ack
peer_delayed_choice:
	r8 = [r7+8]
peer_choice_delay:
	r8 = r8 + -1
	if (r8 != 0) goto peer_choice_delay
	r8 = 0x10804
	r2 = [r8+0]
	[r7+68] = r2
	r2 = 1
	[r7+64] = r2
	csync
	r10 = [r7+12]
	if (r10 == 0) goto peer_choice_sent
	r2 = 1
	if (r10 != r2) goto peer_choice_global
	sevl
	goto peer_choice_sent
peer_choice_global:
	sevg
peer_choice_sent:
	csync
	r2 = [r8+0]
	[r7+72] = r2
	goto peer_ack
peer_idle:
	r2 = [r7+12]
	icfg = r2
	r8 = 0x10804
	r2 = 1
	[r7+64] = r2
	r2 = [r8+0]
	[r7+68] = r2
	csync
	idle
	csync
	r2 = [r8+0]
	[r7+72] = r2
	r2 = 3
	[r7+64] = r2
	r2 = 0
	icfg = r2
	goto peer_ack
peer_waits:
	/* arg1 contains the tested global gates, with the peer source bank disabled. */
	r2 = [r7+12]
	icfg = r2
	r8 = 0x10804
	r2 = 1
	[r7+64] = r2
	csync
	r2 = 6
	if (r1 != r2) goto peer_no_local_prime
	sevl
peer_no_local_prime:
	r2 = 7
	if (r1 != r2) goto peer_no_global_prime
	sevg
peer_no_global_prime:
	r2 = [r8+0]
	[r7+68] = r2
	csync
	wfe
	csync
	r2 = [r8+0]
	[r7+72] = r2
	r2 = 2
	[r7+64] = r2
	r9 = [r7+8]
peer_more_wfe:
	if (r9 == 0) goto peer_wait_done
	wfe
	csync
	r9 = r9 + -1
	goto peer_more_wfe
peer_wait_done:
	r2 = [r8+0]
	[r7+88] = r2
	r2 = 3
	[r7+64] = r2
	r2 = 0
	icfg = r2
	goto peer_ack
peer_lock_once:
	r2 = 1
	[r7+64] = r2
	csync
peer_lock_go:
	r2 = [r7+20]
	if (r2 != r0) goto peer_lock_go
	lockset
	csync
	r2 = [r7+128]
	[r7+80] = r2
	r2 = 2
	[r7+64] = r2
	r2 = 1000
peer_locked_delay:
	r2 = r2 + -1
	if (r2 != 0) goto peer_locked_delay
	csync
	lockclr
	goto peer_ack
peer_increment:
	r2 = 1
	[r7+64] = r2
	csync
peer_inc_go:
	r2 = [r7+20]
	if (r2 != r0) goto peer_inc_go
	r9 = [r7+8]
	r10 = [r7+12]
peer_inc_loop:
	if (r10 == 0) goto peer_inc_unlocked
	lockset
	csync
peer_inc_unlocked:
	r2 = [r7+128]
	/* Widen the read/write overlap in the unlocked control. */
	nop
	nop
	nop
	nop
	r2 = r2 + 1
	[r7+128] = r2
	if (r10 == 0) goto peer_inc_next
	csync
	lockclr
peer_inc_next:
	r9 = r9 + -1
	if (r9 != 0) goto peer_inc_loop
	r2 = 2
	[r7+64] = r2
	goto peer_ack
peer_message:
	r9 = [r7+8]
	r10 = [r7+12]
	r11 = 1
	r12 = 0
	[r7+64] = r11
	csync
peer_message_go:
	r2 = [r7+20]
	if (r2 != r0) goto peer_message_go
peer_message_flag:
	csync
	r2 = [r7+160]
	if (r2 != r11) goto peer_message_flag
	if (r10 == 0) goto peer_message_read
	csync
peer_message_read:
	r3 = [r7+128]
	if (r3 == r11) goto peer_message_ok
	r12 = r12 + 1
peer_message_ok:
	[r7+84] = r11
	csync
	r11 = r11 + 1
	if (r11 <= r9) goto peer_message_flag
	[r7+80] = r12
	r2 = 2
	[r7+64] = r2
	goto peer_ack
peer_store_buffer:
	r9 = [r7+8]
	r10 = [r7+12]
	r11 = 1
peer_sb_ready:
	[r7+64] = r11
	csync
peer_sb_go:
	r2 = [r7+20]
	if (r2 != r11) goto peer_sb_go
	r2 = 1
	[r7+160] = r2
	if (r10 == 0) goto peer_sb_read
	csync
peer_sb_read:
	r3 = [r7+128]
	[r7+80] = r3
	csync
	[r7+84] = r11
	csync
	r11 = r11 + 1
	if (r11 <= r9) goto peer_sb_ready
	goto peer_ack
peer_ack:
	r2 = 2
	if (r1 >= r2) goto peer_ack_publish
	r2 = [r7+24]
	[r7+80] = r2
peer_ack_publish:
	csync
	r5 = r0
	[r7+36] = r5
	csync
	goto peer_loop
