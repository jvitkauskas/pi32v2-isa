	.bss
	.global g1
g1:	.space 4
	.align 8
g2:	.space 8
	.lcomm g3, 16
	.comm g4, 4, 4
	.comm g5, 12
	.text
	r1 = g1
	r1 = g2
	r1 = g3
	r1 = g4
	.data
	.long g1, g3
