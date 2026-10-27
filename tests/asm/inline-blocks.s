# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
# Block forms as the SDK's inline assembly writes them: the condition without spaces, rep and iff nested
# in one another, a compare branch after the block. (The compiler passes { and } through unchanged.)
	.text
	r0 = 0
	r1 = 127
	r1 += r4
	if(r1<0){
	r1 = 0
	}
	if(r1>254){
	r1 = 254
	}
	ifs(r1<0){
	r1 = 0
	}
	ifs(r1>254){
	r1 = 254
	}
	r0 <= insert(r1,p:23,l:8)
1:
	rep r1 {
	r0 = [r2++=4]
	r0 = fabs(r0)
	iff(r0 > r3) {
	r3 = r0
	}
	}
	if(r1>0) goto 1b
	if(r3!=r0) {
	r3 = uextra(r3,p:23,l:8)
	r3 += -127
	}
