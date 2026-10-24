extern int g(int);
int u1(unsigned a){ if(a>0xfffffff0u) return g(a); return 1; }
int u2(unsigned a){ if(a<0xfffffff0u) return g(a); return 1; }
int u3(unsigned a){ if(a>=0xfffff800u) return g(a); return 1; }
int u4(unsigned a){ if(a<2047u) return g(a); return 1; }
int u5(unsigned a){ if(a<4095u) return g(a); return 1; }
int u6(unsigned a){ if(a<0x4000u) return g(a); return 1; }
int u7(unsigned a){ if(a==0xffffffffu) return g(a); return 1; }
int s1(int a){ if(a<-2000) return g(a); return 1; }
int s2(int a){ if(a<2047) return g(a); return 1; }
int s3(int a){ if(a<2048) return g(a); return 1; }
int s4(int a){ if(a<0x4000) return g(a); return 1; }
int s5(int a){ if(a<0x20000) return g(a); return 1; }
