extern int g(int); extern int h(int);
int a(int x,int y){ int r; if(x<y){ r=x*3; r+=y; r^=5; } else { r=y*7; r-=x; } return r; }
int b(int x,int y){ if(x==y){ x=g(x); y=h(y); x+=y; y-=x; x*=y; } return x+y; }
int c(int x,int y,int *p){ if(x>y){ p[0]=x; p[1]=y; p[2]=x+y; p[3]=x-y; p[4]=x^y; } return x; }
int d(int x,int y){ if(x>y){ return x+1; } else if (x<y) return y+1; return 0; }
