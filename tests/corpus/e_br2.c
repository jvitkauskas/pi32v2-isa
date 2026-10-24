int f(int); 
int a1(int a,int b){ if(a<b){ a=f(a); b=f(b);} return a+b; }
int a2(int a,int b){ if(a==b){ a=f(a); b=f(b);} return a+b; }
int a3(unsigned a,unsigned b){ if(a<b){ a=f(a);} return a; }
int a4(int a){ if(a==0) return 5; return f(a); }
int a5(int a){ if(a!=0) return f(a); return 7; }
int a6(int a){ if(a<0) return f(a); return 7; }
int a7(int a){ if(a>=0) return f(a); return 7; }
int a8(int a){ if(a>0) return f(a); return 7; }
int a9(int a){ if(a<=0) return f(a); return 7; }
int b1(int a,int b){ if(a==b) return f(a); return 7; }
int b2(int a,int b){ if(a<b) return f(a); return 7; }
int b3(unsigned a,unsigned b){ if(a<b) return f(a); return 7; }
int b4(int a){ if(a==9) return f(a); return 7; }
int b5(int a){ if(a<9) return f(a); return 7; }
int b6(unsigned a){ if(a<9) return f(a); return 7; }
int b7(int a,int b){ return a<b; }
int b8(unsigned a,unsigned b){ return a<b; }
int b9(int a,int b){ return a==b; }
int c1(int a,int b){ return a!=b; }
int c2(int a,int b){ return a<=b; }
int c3(int a){ return a<0; }
int c4(int a){ return a==0; }
int c5(int a){ return a!=0; }
int c6(int a,int b){ return a>b?a:b; }
int c7(unsigned a,unsigned b){ return a>b?a:b; }
int c8(int a){ return a<0?-a:a; }
int c9(int a,int b){ return a<b?a:b; }
int d1(int a,int b,int c,int d){ return a<b?c:d; }
int d2(int a,int b,int c,int d){ return a==b?c:d; }
int d3(int a){ return a?3:4;}
