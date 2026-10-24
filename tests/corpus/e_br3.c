extern int g(int);
int t1(int a){ if(a&4) return g(a); return 1; }
int t2(int a){ if(!(a&4)) return g(a); return 1; }
int t3(int a){ if(a&0x8000) return g(a); return 1; }
int t4(int a){ if(a&0x80000000) return g(a); return 1; }
int t5(int a,int b){ if(a&b) return g(a); return 1; }
int t6(int a,int b){ if(!(a&b)) return g(a); return 1; }
int t7(int a){ if(a&0xf0) return g(a); return 1; }
int t8(int a){ if((a&0xf0)==0xf0) return g(a); return 1; }
int t9(int a){ if(a<200) return g(a); return 1; }
int t10(int a){ if(a<=200) return g(a); return 1; }
int t11(int a){ if((unsigned)a<500) return g(a); return 1; }
int t12(int a){ if(a<-5) return g(a); return 1; }
int t13(int a){ while(a>5) a=g(a); return a; }
int t14(int a){ do { a=g(a); } while(a!=3); return a; }
int t15(int a){ while(1){ a=g(a); if(a==3) break; } return a; }
int t16(int a,int b){ for(;a<b;a++) g(a); return a; }
int t17(unsigned a,unsigned b){ for(;a<b;a++) g(a); return a; }
int t18(int a){ if(a==1000) return g(a); return 1; }
int t19(int a){ if(a==5) return g(a); return 1; }
int t20(int a){ if(a==-5) return g(a); return 1; }
int t21(int a){ if(a>=0 && a<10) return g(a); return 1; }
int t22(unsigned a){ if(a<10) return g(a); return 1; }
