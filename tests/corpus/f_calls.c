
extern void ints(int,int,int,int,int,int,int,int);
void call_ints(void) { ints(1,2,3,4,5,6,7,8); }
int take_ints(int a,int b,int c,int d,int e,int f,int g,int h) { return a+2*b+3*c+4*d+5*e+6*f+7*g+8*h; }
extern void mix(int,long long,int,long long,int);
void call_mix(void) { mix(11,0x2222222233333333LL,44,0x5555555566666666LL,77); }
long long take_mix(int a,long long b,int c,long long d,int e) { return a+b+c+d+e; }
extern void pair3(long long,long long,long long);
void call_pairs(void) { pair3(0x1111111122222222LL,0x3333333344444444LL,0x5555555566666666LL); }
extern void split(int,int,int,long long,int);
void call_split(void) { split(1,2,3,0x4444444455555555LL,6); }
long long take_split(int a,int b,int c,long long d,int e) { return d+e; }
extern void floats(float,float,float,float,float,float);
void call_floats(void) { floats(1,2,3,4,5,6); }
extern void doubles(double,double,double);
void call_doubles(void) { doubles(1,2,3); }
extern void fmix(int,float,double,int,float);
void call_fmix(void) { fmix(1,2,3,4,5); }
int ret_int(int x) { return x; }
long long ret_ll(long long x) { return x; }
float ret_float(float x) { return x; }
double ret_double(double x) { return x; }
long double ret_ld(long double x) { return x; }
int ret_small(char a,short b,_Bool c) { return a+b+c; }
extern void oddfp(int,double,int,long double,int);
void call_oddfp(void) { oddfp(11,1.25,22,2.5L,33); }
extern void splitfp(int,int,int,double,int);
void call_splitfp(void) { splitfp(1,2,3,1.25,6); }
