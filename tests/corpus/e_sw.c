extern int g1; extern int garr[]; extern const int ctab[]; int gl=5; static const int tab[8]={1,2,3,4,5,6,7,8}; const char msg[]="hello";
int sw8(int x){ switch(x){case 0:return 10;case 1:return 21;case 2:return 3;case 3:return 44;case 4:return 5;case 5:return 66;case 6:return 7;case 7:return 88;default:return 0;} }
int sw8b(int x){ extern void a(void),b(void),c(void),d(void),e(void),f(void); switch(x){case 0:a();break;case 1:b();break;case 2:c();break;case 3:d();break;case 4:e();break;case 5:f();break;} return x; }
int sw200(int x){ extern void a(void),b(void),c(void),d(void),e(void),f(void); switch(x){case 0:a();break;case 1:b();break;case 2:c();break;case 3:d();break;case 4:e();break;case 5:f();break;case 6:a();case 7:b();break;case 8:c();break;case 9:d();break;} return x+1; }
int ldg(void){return g1;}
int ldg2(void){return gl;}
void stg(int v){g1=v;}
int ldarr(int i){return garr[i];}
int ldtab(int i){return tab[i&7];}
char ldmsg(int i){return msg[i];}
int ldc(int i){return ctab[i];}
const char* addr(void){return msg;}
int* addr2(void){return &g1;}
void callp(void(*f)(void)){f();}
int fn(void); int (*fp)(void)=fn;
void call_ext(void){ extern void ext(void); ext(); }
int big(void){return 0x12345678;}
int big2(void){return 0xABCD0000;}
int c3(void){return 1000;}
int c4(void){return -1000;}
int c5(void){return 70000;}
int c6(void){return 0x00ff00ff;}
int c7(void){return 255;}
int c8(void){return 256;}
int c9(void){return -129;}
int c10(void){return 0x7fff;}
int c11(void){return 0x8000;}
int c12(void){return 0xffff;}
int c13(void){return 0x10000;}
int c14(void){return 0x12340000;}
