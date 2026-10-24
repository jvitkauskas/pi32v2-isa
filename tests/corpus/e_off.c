int w16(int*p){return p[16];}
int w100(int*p){return p[100];}
int w300(int*p){return p[300];}
int w1000(int*p){return p[1000];}
int w2000(int*p){return p[2000];}
int w8000(int*p){return p[8000];}
int wneg(int*p){return p[-200];}
int b20(unsigned char*p){return p[20];}
int b1000(unsigned char*p){return p[1000];}
int b4000(unsigned char*p){return p[4000];}
int bn(unsigned char*p){return p[-20];}
int h20(unsigned short*p){return p[20];}
int h1000(unsigned short*p){return p[1000];}
void sw16(int*p,int v){p[16]=v;}
void sw300(int*p,int v){p[300]=v;}
void sb20(unsigned char*p,int v){p[20]=v;}
void sb200(unsigned char*p,int v){p[200]=v;}
void sh200(unsigned short*p,int v){p[200]=v;}
long long d100(long long*p){return p[100];}
long long d1000(long long*p){return p[1000];}
int stk(int i){ int a[200]; extern void use(int*); use(a); return a[150]; }
int stk2(int i){ int a[2000]; extern void use(int*); use(a); return a[1500]; }
