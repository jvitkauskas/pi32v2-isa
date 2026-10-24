	.text
	goto far
	call far
	if (r1 == 0) goto far
	if (r1 == r2) goto far
	ifeq goto far
	if (r9 != 7) goto far
	.space 3000
far:	nop
	goto far
	.space 70000
	if (r1 == 0) goto near
near:	nop
