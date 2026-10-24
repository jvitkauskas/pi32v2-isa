typedef long long s64; typedef unsigned long long u64; typedef unsigned u32;
int pop(unsigned a){return __builtin_popcount(a);}
int popll(u64 a){return __builtin_popcountll(a);}
int pc(unsigned a){return __builtin_parity(a);}
int ctz(unsigned a){return __builtin_ctz(a);}
int clz(unsigned a){return __builtin_clz(a);}
unsigned bs32(unsigned a){return __builtin_bswap32(a);}
unsigned rot16(unsigned a){return (a>>16)|(a<<16);}
unsigned swap16(unsigned a){return ((a&0xff00ff00)>>8)|((a&0x00ff00ff)<<8);}
int cls(int a){ int x=a^(a>>31); return x? __builtin_clz(x)-1 : 31; }
int sat8(int a){ return a>127?127:a<-128?-128:a; }
int sat16(int a){ return a>32767?32767:a<-32768?-32768:a; }
unsigned usat8(int a){ return a>255?255:a<0?0:a; }
unsigned usat16(int a){ return a>65535?65535:a<0?0:a; }
int sadd(int a,int b){ long long r=(long long)a+b; return r>2147483647?2147483647:r<-2147483648LL?-2147483648LL:r; }
int ssub(int a,int b){ long long r=(long long)a-b; return r>2147483647?2147483647:r<-2147483648LL?-2147483648LL:r; }
unsigned uadd(unsigned a,unsigned b){ unsigned r=a+b; return r<a?0xffffffffu:r; }
unsigned usub(unsigned a,unsigned b){ return a>b?a-b:0; }
int avg(int a,int b){ return (a+b)>>1; }
int clamp(int a,int lo,int hi){ return a<lo?lo:a>hi?hi:a; }
int sminc(int a){ return a<100?a:100; }
int smaxc(int a){ return a>100?a:100; }
unsigned umaxc(unsigned a){ return a>100u?a:100u; }
int absd(int a,int b){ return a>b?a-b:b-a; }
int neg(int a){ return -a; }
int notx(int a){ return ~a; }
int bic(int a,int b){ return a&~b; }
int orn(int a,int b){ return a|~b; }
int tstbit(int a){ return (a>>5)&1; }
int setbit(int a){ return a|(1<<5); }
int clrbit(int a){ return a&~(1<<5); }
int xorbit(int a){ return a^(1<<5); }
int bitv(int a,int n){ return a&(1<<n); }
int setbitv(int a,int n){ return a|(1<<n); }
int clrbitv(int a,int n){ return a&~(1<<n); }
int xorbitv(int a,int n){ return a^(1<<n); }
int ext6(int a){ return (a<<26)>>26; }
int ex8_4(unsigned a){ return (a>>8)&0xf; }
int sex8_4(int a){ return (a<<20)>>28; }
unsigned ins(unsigned a,unsigned b){ return (a&~0xff00u)|((b&0xff)<<8); }
unsigned mask(unsigned a){ return a&0xfff0; }
unsigned mask2(unsigned a){ return a&0xffff0000u; }
unsigned mask3(unsigned a){ return a&0x7fffffffu; }
