int rsum(int *p,int n){ int s=0; p+=n-1; for(int i=0;i<n;i++) s+=*p--; return s; }
void rfill(short *p,int n){ p+=n-1; for(int i=0;i<n;i++) *p--=i; }
long long rd(long long *p,int n){ long long s=0; p+=n-1; for(int i=0;i<n;i++) s+=*p--; return s; }
int pre(int *p,int n){ int s=0; for(int i=0;i<n;i++) s+=*++p; return s; }
