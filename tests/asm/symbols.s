	.text
	.globl g1
	.global g2
	.weak w1
	.local l1
	.type g1,@function
	.type d1,@object
	.type t1,%function
	.type t2,STT_FUNC
g1:	nop
g2:	nop
l1:	nop
d1:	nop
t1:	nop
t2:	nop
	.size g1, .-g1
	.size d1, 4
	.hidden g2
	.protected g1
	.extern ext1
	.weak w2
w2:	nop
	.set alias1, g1
	.global alias1
