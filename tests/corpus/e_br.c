void f(void); void g(void);
void slt(int a,int b){if(a<b)f();else g();}
void sle(int a,int b){if(a<=b)f();else g();}
void sgt(int a,int b){if(a>b)f();else g();}
void sge(int a,int b){if(a>=b)f();else g();}
void seq(int a,int b){if(a==b)f();else g();}
void sne(int a,int b){if(a!=b)f();else g();}
void ult(unsigned a,unsigned b){if(a<b)f();else g();}
void ule(unsigned a,unsigned b){if(a<=b)f();else g();}
void ugt(unsigned a,unsigned b){if(a>b)f();else g();}
void uge(unsigned a,unsigned b){if(a>=b)f();else g();}
void slti(int a){if(a<10)f();else g();}
void sgti(int a){if(a>10)f();else g();}
void sgei(int a){if(a>=10)f();else g();}
void slei(int a){if(a<=10)f();else g();}
void seqi(int a){if(a==10)f();else g();}
void snei(int a){if(a!=10)f();else g();}
void ulti(unsigned a){if(a<10)f();else g();}
void ugti(unsigned a){if(a>10)f();else g();}
void ugei(unsigned a){if(a>=10)f();else g();}
void ulei(unsigned a){if(a<=10)f();else g();}
void slt0(int a){if(a<0)f();else g();}
void sge0(int a){if(a>=0)f();else g();}
void sgt0(int a){if(a>0)f();else g();}
void sle0(int a){if(a<=0)f();else g();}
void eq0(int a){if(a==0)f();else g();}
void ne0(int a){if(a!=0)f();else g();}
void big(int a){if(a<100000)f();else g();}
void bigeq(int a){if(a==100000)f();else g();}
void m1(int a){if(a==-1)f();else g();}
void m200(int a){if(a<200)f();else g();}
void m2000(int a){if(a<2000)f();else g();}
void m3000(int a){if(a<3000)f();else g();}
void m5000(int a){if(a==5000)f();else g();}
