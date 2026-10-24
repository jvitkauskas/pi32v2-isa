float fadd(float a,float b){return a+b;}
float fsub(float a,float b){return a-b;}
float fmul(float a,float b){return a*b;}
float fdiv(float a,float b){return a/b;}
float fneg(float a){return -a;}
float fabsx(float a){return __builtin_fabsf(a);}
float fsqrt(float a){return __builtin_sqrtf(a);}
float fma_(float a,float b,float c){return a*b+c;}
float fmaf_(float a,float b,float c){return __builtin_fmaf(a,b,c);}
float fmin_(float a,float b){return a<b?a:b;}
float fmax_(float a,float b){return a>b?a:b;}
float fminb(float a,float b){return __builtin_fminf(a,b);}
float fmaxb(float a,float b){return __builtin_fmaxf(a,b);}
int f2i(float a){return (int)a;}
unsigned f2u(float a){return (unsigned)a;}
float i2f(int a){return (float)a;}
float u2f(unsigned a){return (float)a;}
float fl(float a){return __builtin_floorf(a);}
float ce(float a){return __builtin_ceilf(a);}
float tr(float a){return __builtin_truncf(a);}
float rn(float a){return __builtin_roundf(a);}
float rne(float a){return __builtin_rintf(a);}
float nbi(float a){return __builtin_nearbyintf(a);}
long lr(float a){return __builtin_lrintf(a);}
long llr(float a){return __builtin_lroundf(a);}
int flt(float a,float b){return a<b;}
int fle(float a,float b){return a<=b;}
int fgt(float a,float b){return a>b;}
int fge(float a,float b){return a>=b;}
int feq(float a,float b){return a==b;}
int fne(float a,float b){return a!=b;}
int funo(float a,float b){return a!=a || b!=b;}
int ford(float a,float b){return __builtin_isunordered(a,b);}
void fbr(float a,float b){ extern void f(void); if(a<b) f(); }
void fbr2(float a,float b){ extern void f(void); if(a==b) f(); }
void fbr3(float a,float b){ extern void f(void); if(a>=b) f(); }
void fbr4(float a,float b){ extern void f(void); if(!(a<b)) f(); }
void fbr5(float a,float b){ extern void f(void); if(a!=b) f(); }
void fbr6(float a,float b){ extern void f(void); if(a>b) f(); }
void fbr7(float a,float b){ extern void f(void); if(a<=b) f(); }
double dadd(double a,double b){return a+b;}
double dmul(double a,double b){return a*b;}
double i2d(int a){return a;}
int d2i(double a){return (int)a;}
double f2d(float a){return a;}
float d2f(double a){return (float)a;}
float cps(float a,float b){return __builtin_copysignf(a,b);}
float cmpsel(float a,float b,float c,float d){return a<b?c:d;}
float c0(float a){return a*2.0f;}
float c1(float a){return a+1.0f;}
float c2(void){return 3.5f;}
float c3(float a){return a/2.0f;}
float c4(float a){return a>0.0f?a:0.0f;}
int isn(float a){return __builtin_isnan(a);}
int isi(float a){return __builtin_isinf(a);}
