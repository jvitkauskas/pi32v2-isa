	.macro LOOP n, body:vararg
	.rept \n
	\body
	.endr
	.endm
	.macro PUSHALL
	[--sp] = {r3-r0}
	.endm
	.macro CNT
	cnt\@:
	nop
	goto cnt\@
	.endm
	.text
	LOOP 3, nop
	PUSHALL
	CNT
	CNT
	.macro M2 x
	.if \x > 2
	r1 = \x
	.else
	r2 = \x
	.endif
	.endm
	M2 1
	M2 5
