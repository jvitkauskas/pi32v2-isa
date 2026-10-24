extern void a(void),b(void),c(void);
void (*const tbl[3])(void)={a,b,c};
void disp(int i){ tbl[i](); }
int k1(int x){ return x*0x12345 + 0x87654321; }
double dc(double x){ return x*3.14159; }
float fc(float x){ return x*3.14159f + 2.71828f; }
const char *names[]={"aa","bb","cc"};
const char *nm(int i){ return names[i]; }
int lut[256]; int lk(int i){ return lut[i&255]; }
int sw(int x){ switch(x){case 1:return 100;case 2:return 2000;case 3:return 30000;case 4:return 400000;case 5:return 5;case 6:return 77777;} return 0; }
void far_call(void){ a(); b(); }
