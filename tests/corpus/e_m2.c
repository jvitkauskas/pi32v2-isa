typedef long long s64; typedef unsigned long long u64; typedef unsigned u32;
u32 umin(u32 a,u32 b){return a<b?a:b;}
u64 umsub(u64 acc,u32 a,u32 b){return acc-(u64)a*b;}
s64 sma(s64 acc,int a,int b){return acc+(s64)a*b;}
s64 smul_s_u(int a,u32 b){return (s64)a*b;}
u64 umul64lo(u64 a,u64 b){return a*b;}
int neg1(int a){return a*-1;}
int mm(int a){return a*-7;}
int mm2(int a){return a*100000;}
int mm3(int a){return a*0x00ff0000;}
int mm4(int a){return a*65;}
int sdivp2(int a){return a/2;}
int sdivp(int a,int b){return b? a/b : 0;}
int smods(int a,int b){return b? a%b : 0;}
long long mulacc(int *a,int *b,int n){ long long s=0; for(int i=0;i<n;i++) s+=(long long)a[i]*b[i]; return s; }
