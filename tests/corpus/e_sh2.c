unsigned m1(unsigned a,unsigned b){return a<<(b&31);}
unsigned m2(unsigned a,unsigned b){return b>=32?0:a<<b;}
unsigned m3(unsigned a,unsigned b){return b>=32?0:a>>b;}
int m4(int a,int b){return b>=32?(a>>31):a>>b;}
int m5(int a,int b){return b>=0? a<<b : a>>(-b);}
int m6(int a,int b){return b>=0? a>>b : a<<(-b);}
int hi(int a,int b,int c){return a+(b<<c);}
int lo(int a,int c){return a<<c<<c;}
int hr(int a,int b,int c,int d,int e,int f,int g,int h,int i,int j){return (i>>3)+(j<<5)+(h>>9);}
int s31(int a){return a<<31;}
int s32l(unsigned a){return a>>31;}
int s1(int a){return a>>1;}
int hr2(int a,int b,int c,int d,int e,int f,int g,int h,int i,int j){return (i>>3);}
long long sh32(long long a){return a<<32;}
long long sh33(long long a){return a<<33;}
long long sh63(long long a){return a>>63;}
unsigned lo32(long long a){return (unsigned)(a>>5);}
unsigned lo32b(long long a){return (unsigned)(a>>37);}
int lo32c(long long a,int n){return (int)(a>>n);}
unsigned short us(unsigned short a){return a>>3;}
short ss(short a){return a>>3;}
short ssl(short a){return a<<3;}
