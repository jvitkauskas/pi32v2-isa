	.text
	nop
	.section .text.foo,"ax",@progbits
	nop
	.section .rodata.str1.1,"aMS",@progbits,1
	.asciz "x"
	.section .mydata,"aw",@progbits
	.long 1
	.section .mybss,"aw",@nobits
	.space 8
	.section .noflags
	.byte 1
	.data
	.long 2
	.bss
	.space 4
	.comm cc1, 8, 4
	.lcomm lc1, 4
	.pushsection .tmp,"a"
	.byte 1
	.popsection
	.text
	nop
	.previous
	.space 3
