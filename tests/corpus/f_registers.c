extern int ext(int);
int pressure(int *p) {
 int a=p[0],b=p[1],c=p[2],d=p[3],e=p[4],f=p[5],g=p[6],h=p[7],i=p[8],j=p[9],k=p[10],l=p[11];
 __asm__ volatile("" : "+r"(a),"+r"(b),"+r"(c),"+r"(d),"+r"(e),"+r"(f),"+r"(g),"+r"(h),"+r"(i),"+r"(j),"+r"(k),"+r"(l));
 int x=ext(0);
 __asm__ volatile("" : "+r"(a),"+r"(b),"+r"(c),"+r"(d),"+r"(e),"+r"(f),"+r"(g),"+r"(h),"+r"(i),"+r"(j),"+r"(k),"+r"(l));
 return x+a+b+c+d+e+f+g+h+i+j+k+l;
}
void clobber_low(void) { __asm__ volatile("" ::: "r0","r1","r2","r3"); }
void clobber_high(void) { __asm__ volatile("" ::: "r4","r5","r6","r7","r8","r9","r10","r11","r12","r13","r14","r15"); }
