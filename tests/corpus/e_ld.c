typedef unsigned char u8; typedef signed char s8; typedef unsigned short u16; typedef short s16;
int ldsb(s8*p){return *p;}
int ldub(u8*p){return *p;}
int ldsh(s16*p){return *p;}
int lduh(u16*p){return *p;}
int ldw(int*p){return *p;}
int ldsb5(s8*p){return p[5];}
int ldub5(u8*p){return p[5];}
int ldsh5(s16*p){return p[5];}
int lduh5(u16*p){return p[5];}
int ldw5(int*p){return p[5];}
int ldsbN(s8*p){return p[-5];}
int ldwN(int*p){return p[-5];}
int ldw500(int*p){return p[500];}
int ldw5000(int*p){return p[5000];}
int ldw40000(int*p){return p[40000];}
int ldwi(int*p,int i){return p[i];}
int ldubi(u8*p,int i){return p[i];}
int ldsbi(s8*p,int i){return p[i];}
int lduhi(u16*p,int i){return p[i];}
int ldshi(s16*p,int i){return p[i];}
long long ldd(long long*p){return *p;}
long long ldd3(long long*p){return p[3];}
long long lddi(long long*p,int i){return p[i];}
void stb(u8*p,int v){*p=v;}
void sth(u16*p,int v){*p=v;}
void stw(int*p,int v){*p=v;}
void std(long long*p,long long v){*p=v;}
void stb5(u8*p,int v){p[5]=v;}
void sth5(u16*p,int v){p[5]=v;}
void stw5(int*p,int v){p[5]=v;}
void stwi(int*p,int i,int v){p[i]=v;}
void stbi(u8*p,int i,int v){p[i]=v;}
void sthi(u16*p,int i,int v){p[i]=v;}
void sthh(u16*p,int v){*p=v>>16;}
int exts(int a){return (signed char)a;}
int extu(int a){return (unsigned char)a;}
int exths(int a){return (short)a;}
int exthu(int a){return (unsigned short)a;}
long long sx(int a){return a;}
long long zx(unsigned a){return a;}
int b1(int a){return (a>>8)&0xff;}
int b2(int a){return (a>>16)&0xff;}
int b3(unsigned a){return a>>24;}
int h1(unsigned a){return a>>16;}
int h1s(int a){return a>>16;}
unsigned pk(unsigned a,unsigned b){return (a&0xffff)|(b<<16);}
unsigned pk2(unsigned a,unsigned b){return (a<<16)|(b&0xffff);}
