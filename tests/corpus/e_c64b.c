typedef long long s64; typedef unsigned long long u64; typedef unsigned u32;
extern void f(void);
int le64(s64 a,s64 b){return a<=b;}
int gt64(s64 a,s64 b){return a>b;}
int ge64(s64 a,s64 b){return a>=b;}
int ule64(u64 a,u64 b){return a<=b;}
int ugt64(u64 a,u64 b){return a>b;}
int uge64(u64 a,u64 b){return a>=b;}
int ne64(u64 a,u64 b){return a!=b;}
int lt64z(s64 a){return a<0;}
void brle(s64 a,s64 b){ if(a<=b) f(); }
void brule(u64 a,u64 b){ if(a<=b) f(); }
u32 addc(u32 a,u32 b,u32 c,u32*co){ u32 carry; u32 r=__builtin_addc(a,b,c,&carry); *co=carry; return r; }
u32 subc(u32 a,u32 b,u32 c,u32*co){ u32 carry; u32 r=__builtin_subc(a,b,c,&carry); *co=carry; return r; }
u64 mulq(u64 a,u32 b){return a*b;}
s64 shl_add(s64 a){return a*3;}
u64 u64_add32(u64 a,u32 b){return a+b;}
s64 s64_add32(s64 a,int b){return a+b;}
