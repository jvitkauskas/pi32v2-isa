
long long sdiv(long long a,long long b) { return a/b; }
unsigned long long udiv(unsigned long long a,unsigned long long b) { return a/b; }
long long smod(long long a,long long b) { return a%b; }
unsigned long long umod(unsigned long long a,unsigned long long b) { return a%b; }
long long mul64(long long a,long long b) { return a*b; }
float fadd(float a,float b) { return a+b; } float fdiv(float a,float b) { return a/b; }
double dadd(double a,double b) { return a+b; } double dsub(double a,double b) { return a-b; }
double dmul(double a,double b) { return a*b; } double ddiv(double a,double b) { return a/b; }
int dcmp(double a,double b) { return a<b; }
int dtoi(double a) { return a; } double itod(int a) { return a; }
float dtof(double a) { return a; } double ftod(float a) { return a; }
long double ldadd(long double a,long double b) { return a+b; }
struct Big { char a[1000]; }; void copy(struct Big *p,struct Big *q) { *p=*q; }
void zero(struct Big *p) { __builtin_memset(p,0,sizeof(*p)); }
void move(void *p,void *q,unsigned n) { __builtin_memmove(p,q,n); }
