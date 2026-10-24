
extern int ext(int); extern void escape(void *);
int nonleaf(int x) { return ext(x)+1; }
int live(int a,int b,int c,int d) { int x=ext(a); return x+a+b+c+d; }
int manylive(int *p) { int a=p[0],b=p[1],c=p[2],d=p[3],e=p[4],f=p[5],g=p[6],h=p[7],i=p[8],j=p[9],k=p[10],l=p[11]; int x=ext(p[12]); return x+a+2*b+3*c+4*d+5*e+6*f+7*g+8*h+9*i+10*j+11*k+12*l; }
void frame(void) { char a[5]; escape(a); }
void alloca_probe(unsigned n) { char *p=__builtin_alloca(n); p[0]=1; escape(p); }
void vla(unsigned n) { volatile int a[n]; a[n-1]=3; escape((void*)a); }
