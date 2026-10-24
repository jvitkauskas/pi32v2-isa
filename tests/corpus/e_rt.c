typedef long long s64; typedef unsigned long long u64;
double dadd(double a,double b){return a+b;}
double dmul(double a,double b){return a*b;}
double ddiv(double a,double b){return a/b;}
double i2d(int a){return a;}
double u2d(unsigned a){return a;}
int d2i(double a){return (int)a;}
unsigned d2u(double a){return (unsigned)a;}
double f2d(float a){return a;}
float d2f(double a){return (float)a;}
int dlt(double a,double b){return a<b;}
float sq(float a){return __builtin_sqrtf(a);}
double sqd(double a){return __builtin_sqrt(a);}
float fm(float a,float b,float c){return __builtin_fmaf(a,b,c);}
s64 sdiv64(s64 a,s64 b){return a/b;}
u64 udiv64(u64 a,u64 b){return a/b;}
s64 smod64(s64 a,s64 b){return a%b;}
u64 umod64(u64 a,u64 b){return a%b;}
float i64f(s64 a){return (float)a;}
s64 f2i64(float a){return (s64)a;}
float rintf_(float a){return __builtin_rintf(a);}
long lr(float a){return __builtin_lrintf(a);}
int cp(void*d,const void*s,unsigned n){ __builtin_memcpy(d,s,n); return 0;}
