unsigned dtou(double a) { return a; } double utod(unsigned a) { return a; }
long long dtoll(double a) { return a; } unsigned long long dtoull(double a) { return a; }
double lltod(long long a) { return a; } double ulltod(unsigned long long a) { return a; }
long long ftoll(float a) { return a; } float lltof(long long a) { return a; }
int deq(double a,double b) { return a==b; } int dne(double a,double b) { return a!=b; }
int dle(double a,double b) { return a<=b; } int dgt(double a,double b) { return a>b; } int dge(double a,double b) { return a>=b; }
int ftoi(float a) { return a; } float itof(int a) { return a; }
long long shl(long long a,int n) { return a<<n; } long long shr(long long a,int n) { return a>>n; }
enum E { A,B }; int enum_signed(void) { return (enum E)-1<0; } int enum_uint(void) { return __builtin_types_compatible_p(enum E,unsigned int); }
