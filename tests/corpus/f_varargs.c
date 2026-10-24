
typedef __builtin_va_list va_list;
extern void v(int,...);
void call_v(void) { v(1,2,3LL,4.0f,5.0,6,7LL); }
int vi(int n,...) { va_list a; __builtin_va_start(a,n); int x=__builtin_va_arg(a,int); int y=__builtin_va_arg(a,int); __builtin_va_end(a); return x+y; }
long long vl(int n,...) { va_list a; __builtin_va_start(a,n); return __builtin_va_arg(a,long long); }
double vd(int n,...) { va_list a; __builtin_va_start(a,n); return __builtin_va_arg(a,double); }
long long vthree(int a,int b,int c,...) { va_list p; __builtin_va_start(p,c); return __builtin_va_arg(p,long long); }
int vfour(int a,int b,int c,int d,...) { va_list p; __builtin_va_start(p,d); return __builtin_va_arg(p,int); }
struct S { int a,b,c; }; struct S vs(int n,...) { va_list p; __builtin_va_start(p,n); return __builtin_va_arg(p,struct S); }
int va_size(void) { return sizeof(va_list); }
