	.data
a:	.long 0
b:	.long b-a, a-b, (b-a)*2
	.short b-a
	.byte c-a
c:	.long c
	.long a+4
	.long c-.
	.text
	.long a
	r1 = a
	r2 = b+4
