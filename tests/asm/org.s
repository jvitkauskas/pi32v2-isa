	.text
	nop
	.org 0x10
	nop
	.org 0x20, 0xAA
	.ascii "x"
	.org .+8
	nop
