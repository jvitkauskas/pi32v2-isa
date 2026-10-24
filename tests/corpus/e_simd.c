typedef short v2h __attribute__((vector_size(4)));
typedef signed char v4b __attribute__((vector_size(4)));
typedef short v4h __attribute__((vector_size(8)));
typedef int v2w __attribute__((vector_size(8)));
v2h vadd(v2h a,v2h b){return a+b;}
v2h vsub(v2h a,v2h b){return a-b;}
v2h vmul(v2h a,v2h b){return a*b;}
v4b vaddb(v4b a,v4b b){return a+b;}
v4h vadd4(v4h a,v4h b){return a+b;}
v2w vaddw(v2w a,v2w b){return a+b;}
v2h vshl(v2h a){return a<<3;}
v2h vsra(v2h a){return a>>3;}
v2h vand(v2h a,v2h b){return a&b;}
int hsum(short*a,short*b,int n){int s=0;for(int i=0;i<n;i++)s+=a[i]*b[i];return s;}
void vaddloop(short*a,short*b,short*c,int n){for(int i=0;i<n;i++)c[i]=a[i]+b[i];}
void vaddloopb(unsigned char*a,unsigned char*b,unsigned char*c,int n){for(int i=0;i<n;i++)c[i]=a[i]+b[i];}
void ssat(short*a,int*b,int n){for(int i=0;i<n;i++){int x=b[i]; a[i]= x>32767?32767:x<-32768?-32768:x;}}
