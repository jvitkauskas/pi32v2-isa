typedef unsigned char u8; typedef unsigned short u16;
int sum(int *p, int n){ int s=0; for(int i=0;i<n;i++) s+=p[i]; return s; }
int sum16(int *p){ int s=0; for(int i=0;i<16;i++) s+=p[i]; return s; }
int sumb(u8 *p, int n){ int s=0; for(int i=0;i<n;i++) s+=p[i]; return s; }
int sumh(short *p, int n){ int s=0; for(int i=0;i<n;i++) s+=p[i]; return s; }
void cpy(int*d,const int*s,int n){ for(int i=0;i<n;i++) d[i]=s[i]; }
void cpyb(u8*d,const u8*s,int n){ for(int i=0;i<n;i++) d[i]=s[i]; }
void fill(int*d,int v,int n){ for(int i=0;i<n;i++) d[i]=v; }
void fill8(int*d,int v){ for(int i=0;i<8;i++) d[i]=v; }
int cnt(int n){ int s=0; while(n--) s+=n; return s; }
int dot(short*a,short*b,int n){ int s=0; for(int i=0;i<n;i++) s+=a[i]*b[i]; return s; }
void dec(int *p, int n){ while(n>0){ *p++ = n; n--; } }
void scale(float*p,float k,int n){ for(int i=0;i<n;i++) p[i]*=k; }
int nested(int n,int m){ int s=0; for(int i=0;i<n;i++) for(int j=0;j<m;j++) s+=i*j; return s; }
int fixed5(void){ int s=0; for(int i=0;i<5;i++) s+=i*i; return s; }
int bodycall(int n){ extern int g(int); int s=0; for(int i=0;i<n;i++) s+=g(i); return s; }
long long sum64(long long*p,int n){ long long s=0; for(int i=0;i<n;i++) s+=p[i]; return s; }
void strided(int*p,int n){ for(int i=0;i<n;i+=2) p[i]=0; }
void down(int*p,int n){ for(int i=n-1;i>=0;i--) p[i]=i; }
int strl(const char*s){ int n=0; while(*s++) n++; return n; }
