	.text
	r1 = ext
	r1 = ext+4
	r1 = ext-4
	r1 = 4+ext
	r1 = (ext+4)
	r1 = ext + 8
	call ext
	call (ext+4)
	goto ext
	goto (ext-4)
	call 4+ext
	if (r1 == 0) goto ext
	if (r9 == r2) goto ext
	ifeq goto ext
	ifne goto (ext+2)
	if (--r3 != 0) goto ext
	if ((r1 & r2) == 0) goto ext
	if (r1 == 5) goto ext
	if (r1 >= 3000) goto ext
	gotoss ext
	reti = ext
	psr = ext+1
	.data
	.long ext
	.long ext+4
	.long ext-4
	.short ext
	.byte ext
	.long loc
	.long loc+8
	.text
loc:	nop
