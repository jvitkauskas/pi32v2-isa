	.text
	call later
	call wk
	.globl later
later:	nop
	.weak wk
wk:	nop
	.hidden und1
	r1 = und1
	.type tf, %function
tf:	rts
	.set a1, tf
	.set a2, a1+2
	call a2
	r1 = a2
	.size a2, 8
	.global a2
