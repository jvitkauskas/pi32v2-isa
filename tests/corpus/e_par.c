int f(int a){int x=a&7; return x;}
int g(int a,int b){int x=a^b; int y=x+1; return y;}
int h(int *p,int a){ int x=a&7; *p=x; return x; }
int k(int *p,int a){ int x=*p; int y=a+x; return y; }
