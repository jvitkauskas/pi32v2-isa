typedef unsigned char u8;
extern void *memcpy(void*,const void*,unsigned long); extern void *memset(void*,int,unsigned long);
void mc(void*d,const void*s,unsigned n){ memcpy(d,s,n); }
void mc64(void*d,const void*s){ memcpy(d,s,64); }
void mc256(void*d,const void*s){ memcpy(d,s,256); }
void mc7(void*d,const void*s){ memcpy(d,s,7); }
void ms(void*d,int v,unsigned n){ memset(d,v,n); }
void ms64(void*d){ memset(d,0,64); }
void ms256(void*d){ memset(d,0,256); }
struct S{int a[40];}; void cs(struct S*d,struct S*s){*d=*s;}
void bm(int *p, int n){ for(int i=0;i<n;i++) p[i]=0; }
