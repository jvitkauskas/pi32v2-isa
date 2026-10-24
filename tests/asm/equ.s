	.equ K, 5
	.set L, K+3
	.text
	r1 = K
	r2 = L
	r3 = K+L
	[sp+K+3] = r1
	.set K, 9
	r1 = K
