typedef long long s64;
extern int g(int,int,int,int,int,int,int);
extern s64 g64(int,s64,int,s64);
extern float gf(float,float);
extern void (*fp)(int);
int a1(int a,int b,int c,int d,int e,int f){ return e+f; }
int a2(int a,s64 b,int c){ return (int)b+c; }
int a3(s64 a,s64 b,s64 c){ return (int)(a+b+c); }
int a4(char a,short b){ return a+b; }
int callp(int x){ fp(x); return x+1; }
int c7(void){ return g(1,2,3,4,5,6,7); }
s64 c64(void){ return g64(1,2,3,4)+1; }
float cf(float a){ return gf(a,a)+1.0f; }
struct S{int a,b,c;}; struct S mk(int x){ struct S s={x,x,x}; return s; }
struct T{int a,b;}; struct T mk2(int x){ struct T s={x,x+1}; return s; }
int usesS(struct S s){ return s.a+s.c; }
int va(int n,...){ __builtin_va_list ap; __builtin_va_start(ap,n); int s=0; for(int i=0;i<n;i++) s+=__builtin_va_arg(ap,int); __builtin_va_end(ap); return s; }
void keep(int);
int save(int a,int b){ keep(a); keep(b); return a+b; }
