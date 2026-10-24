	.text
	.type f,@function
f:	nop
	nop
	.size f, .-f
	.type g,@object
	.size g, f_end-f
f_end:	nop
	.long g
