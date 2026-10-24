	.text
	cc = 1
	cc = 0
	r1 = r2.l (u)
	r1 = r2.l (s)
	r1 = r2.b0 (u)
	r1.l = r2.h
	r1.h = 0x1234
	r1.b2 = 255
	r1_r0 = r3_r2
	r1_r0 = 0
	{r15-r0} = [sp++]
	[--sp] = {r15-r0}
	[--sp] = {rets}
	[--sp] = {rets, r3-r0}
	{pc, r8-r4} = [sp++]
	{psr, rets, reti} = [sp++]
	[--sp] = {psr, rets, reti}
	[--sp] = {sp, ssp, usp, icfg, psr, rets, retx, rete, reti}
	r1 = [r2++=r3]
	[r2++=r3] = r1
	r1 = h[r2++=2] (u)
	r1 = [r2++=-4]
	r1 = [r2+r3<<2]
	r1_r0 = d[r2+8]
	d[r2++=8] = r1_r0
	r1_r0 = d[sp+16]
	csync
	ssync
	cli
	sti
	idle
	swi 3
	syscall
	bkpt
	trigger
	r1 = icfg
	icfg = 0
	usp = r1
	sp = r2
