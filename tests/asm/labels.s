	.text
a:	nop
b:	c:	nop
1:	nop
	goto 1b
	goto 1f
1:	nop
	goto 1b
	call 2f
2:	rts
