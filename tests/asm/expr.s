	.text
a:	nop
b:	nop
	r1 = b-a
	r1 = (b-a)*2
	r1 = c-a
	.set K, b-a
	r1 = K
	.long b-a
	.long c-b
	.short c-a
	.zero 100-(.-a)
c:	nop
	.long .
	.long . + 4
	.long a+4
	.long .-a
