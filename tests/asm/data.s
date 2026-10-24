	.data
	.byte 1, 2, 3, -1, 255
	.short 1, -1, 65535
	.long 1, -1, 0xFFFFFFFF
	.int 7
	.2byte 9
	.4byte 10
	.quad 0x1122334455667788
	.8byte -2
	.ascii "abc"
	.asciz "def"
	.string "ghi"
	.string "esc\n\t\"\\\101"
	.space 3
	.space 2, 0x55
	.skip 2
	.zero 4
	.fill 3, 2, 0x1234
	.fill 2
	.float 1.5
	.double 2.5
	.uleb128 300
	.sleb128 -129
	.align 4
	.byte 5
	.balign 8, 0xAA
	.p2align 4
	.byte 6
	.p2align 3, 0xFF, 4
