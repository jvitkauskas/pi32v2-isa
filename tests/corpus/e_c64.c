typedef long long s64; typedef unsigned long long u64; typedef unsigned u32;
s64 add64(s64 a,s64 b){return a+b;}
s64 sub64(s64 a,s64 b){return a-b;}
s64 neg64(s64 a){return -a;}
s64 addi64(s64 a){return a+5;}
s64 addbig64(s64 a){return a+0x123456789LL;}
s64 sub1(s64 a){return a-1;}
u64 and64(u64 a,u64 b){return a&b;}
u64 or64(u64 a,u64 b){return a|b;}
u64 xor64(u64 a,u64 b){return a^b;}
u64 not64(u64 a){return ~a;}
int lt64(s64 a,s64 b){return a<b;}
int ult64(u64 a,u64 b){return a<b;}
int eq64(u64 a,u64 b){return a==b;}
void br64(s64 a,s64 b){ extern void f(void); if(a<b) f(); }
void ubr64(u64 a,u64 b){ extern void f(void); if(a<b) f(); }
u32 carry(u32 a,u32 b){ u32 c=a+b; return c<a; }
u32 borrow(u32 a,u32 b){ return a<b; }
u32 ovf(int a,int b){ int r; return __builtin_add_overflow(a,b,&r); }
u32 uovf(u32 a,u32 b){ u32 r; return __builtin_add_overflow(a,b,&r); }
u32 sovf(u32 a,u32 b){ u32 r; return __builtin_sub_overflow(a,b,&r); }
u32 movf(int a,int b){ int r; return __builtin_mul_overflow(a,b,&r); }
int clz(unsigned a){return __builtin_clz(a);}
int clzll(u64 a){return __builtin_clzll(a);}
int ctz(unsigned a){return __builtin_ctz(a);}
int ffs(unsigned a){return __builtin_ffs(a);}
int pop(unsigned a){return __builtin_popcount(a);}
int popll(u64 a){return __builtin_popcountll(a);}
unsigned bs32(unsigned a){return __builtin_bswap32(a);}
unsigned short bs16(unsigned short a){return __builtin_bswap16(a);}
u64 bs64(u64 a){return __builtin_bswap64(a);}
int pc(unsigned a){return __builtin_parity(a);}
unsigned hclz(unsigned a){return a? 31-__builtin_clz(a):0;}
int pi_clz(unsigned a){return __builtin_pi32v2_clz(a);}
