	.text
	rep 5 {
	nop
	r1 = 0x12345678
	}
	rep r1 {
	nop
	nop
	}
	if (r1 == r2) {
	nop
	}
	if (r1 == r2) {
	r1 = 5
	r2 = 0x12345678
	} else {
	nop
	}
	iff (r1 < r2) {
	nop
	}
	ifs (r1 < 5) {
	r1 = [r1+0]
	r0 += r7 #
	r1 = [r1+0]
	nop
	}
