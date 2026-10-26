# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
# Independently probed assembler aliases (JieLi 20260730.1, -mcpu=r3).
.text

[r5++] = r6

[r2--] = r3

h[r0++] = r2

h[r3--] = r5

b[r2++] = r4

r1 = h[r0++] (u)

r3 = h[r0++] (s)

r9 = h[r10--] (s)

r1 = b[r4++] (s)

r12 = b[r15--] (s)

r6 = -r6

r11 = -r12

r1 = fabs(r1)

r12 = fabs(r9)

r5_r4.h = r2

r3_r2.l = r5_r4.h

r15_r14.l = uextra(r0,p:0,l:23)

r0 = r3_r2 >>> 14 (round)

r5_r4.l = r0 >< r1 (sat)

r1_r0 = copex(r3_r2) (23)

r15_r14 = copex(r13_r12) (11)

r7_r6 = cmpu(r7_r6 < r3_r2) (v)

r5_r4 = r12*r0 (s)

r3_r2 += r7*r7 (s)

r5_r4 = h[r1++]*r2 (s)

r9_r8 += h[r15++=2]*r5 (s)

r5_r4 = [r0--]*[r7++] (s)

r3_r2 = h[r8++=2]*[r1++=0] (s)

r3_r2 = [r0++=0]*[r2++] (s)

r5_r4 += [r0++]*[r7--] (s)

r15_r14 = h[r8--]*r9 (u)

r1 = 1.f

r2 = 10.f

r3 = 1.5f

r4 = -1.f

r9 -= 1 # r4 = [r1++=4]

r2 = -r1 #
r1 = [r0]

r12 = fabs(r9) # r0 = [r1++]

r4=-r4(f)

r11=-r12(f)

r1=r7_r6>>>7

r2=r15_r14>>>r8

r4=r4+|+|+|+r6(uavg,rnd)

r7><=r10

r4><=r1(sat)

ifs(r6==32) {
nop
}

ifs(r7!=0) {
nop
}

1:
nop
ifs(--r10!=0)goto 1b
ifs (--r3 != 0) goto 1b
