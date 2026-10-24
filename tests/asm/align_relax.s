	.text
	goto L
	.p2align 3
	nop
	.p2align 4
	goto L
	.space 2040
	.p2align 4
L:	nop
	.balign 32
	call L
