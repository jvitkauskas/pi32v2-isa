typedef long long s64; typedef unsigned long long u64; typedef unsigned u32; typedef int s32;
int mul(int a,int b){return a*b;}
int muli(int a){return a*10;}
int muli3(int a){return a*3;}
int muli8(int a){return a*8;}
int muli1000(int a){return a*1000;}
int muli7(int a){return a*7;}
s64 smull(int a,int b){return (s64)a*b;}
u64 umull(u32 a,u32 b){return (u64)a*b;}
s32 smulh(int a,int b){return ((s64)a*b)>>32;}
u32 umulh(u32 a,u32 b){return ((u64)a*b)>>32;}
s64 smlal(s64 acc,int a,int b){return acc+(s64)a*b;}
u64 umlal(u64 acc,u32 a,u32 b){return acc+(u64)a*b;}
s64 smlsl(s64 acc,int a,int b){return acc-(s64)a*b;}
int mla(int acc,int a,int b){return acc+a*b;}
int mls(int acc,int a,int b){return acc-a*b;}
s64 mul64(s64 a,s64 b){return a*b;}
int sdiv(int a,int b){return a/b;}
u32 udiv(u32 a,u32 b){return a/b;}
int smod(int a,int b){return a%b;}
u32 umod(u32 a,u32 b){return a%b;}
int sdivi(int a){return a/10;}
u32 udivi(u32 a){return a/10;}
int sdiv8(int a){return a/8;}
int smod8(int a){return a%8;}
u32 umod8(u32 a){return a%8;}
s64 sdiv64(s64 a,s64 b){return a/b;}
u64 udiv64(u64 a,u64 b){return a/b;}
s64 smod64(s64 a,s64 b){return a%b;}
void dm(int a,int b,int*q,int*r){*q=a/b;*r=a%b;}
void udm(u32 a,u32 b,u32*q,u32*r){*q=a/b;*r=a%b;}
int sm16(short a,short b){return a*b;}
int sm16b(short a,short b,int c){return c+a*b;}
s64 sq(int a){return (s64)a*a;}
int mulhs(int a){return ((s64)a*0x12345678)>>32;}
