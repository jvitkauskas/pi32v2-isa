	.macro M a, b=3
	r1 = \a
	r2 = \b
	.endm
	.text
	M 1
	M 4, 5
	M a=7
	.rept 3
	nop
	.endr
	.irp x, r1, r2
	\x = 5
	.endr
	.irpc c, 12
	r\c = \c
	.endr
	.if 1
	nop
	.else
	rts
	.endif
	.ifdef M
	.endif
	.set Q, 3
	.if Q == 3
	r5 = 3
	.elseif Q == 4
	r5 = 4
	.else
	r5 = 5
	.endif
	.ifc a,a
	r6 = 1
	.endif
	.ifnc a,b
	r6 = 2
	.endif
	.ifb
	r6 = 3
	.endif
	.ifnb x
	r6 = 4
	.endif
