int d2(int *p){ return p[0]*3 - p[1]; }
int d2b(int *p){ return p[0] - p[1]*5; }
int d3(int *p){ return p[0]*3 - p[1]*5 + p[2]*7; }
int d4(int *p){ return p[0]*3 - p[1]*5 + p[2]*7 - p[3]*9; }
void s4(int *p,int a,int b,int c,int d){ p[0]=a; p[1]=b; p[2]=c; p[3]=d; }
void s2(int *p,int a,int b){ p[0]=a; p[1]=b; }
void s3(int *p,int a,int b){ p[0]=a; p[1]=b; p[2]=a+b; }
struct T{int a,b,c,d,e,f;}; void cp(struct T*d,struct T*s){*d=*s;}
long long ld64(long long*p){return p[0]+p[1];}
void st64(long long*p,long long v){p[0]=v;p[1]=v+1;}
void step(int *p, int s, int n){ int t=0; for(int i=0;i<n;i++){ t+=*p; p+=s;} *p=t; }
short stepsh(short *p, int s){ short a=*p; p+=s; return a+*p; }
