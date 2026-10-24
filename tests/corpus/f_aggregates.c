
#define DECL(N) struct S##N { char a[N]; }; 
DECL(1) DECL(2) DECL(3) DECL(4) DECL(5) DECL(8) DECL(9) DECL(12) DECL(16) DECL(20) DECL(32)
#define TEST(N) extern void use##N(struct S##N,int); void pass##N(void) { struct S##N x; for(int i=0;i<N;i++) x.a[i]=i+1; use##N(x,99); } struct S##N ret##N(void) { struct S##N x; for(int i=0;i<N;i++) x.a[i]=i+1; return x; } int take##N(struct S##N x,int y) { return x.a[0]+x.a[N-1]+y; }
TEST(1) TEST(2) TEST(3) TEST(4) TEST(5) TEST(8) TEST(9) TEST(12) TEST(16) TEST(20) TEST(32)
struct W { int a,b; }; struct D { double a; }; struct FF { float a,b; };
extern void ws(int,struct W,int,struct W,int);
void passw(void) { struct W w={22,33}; ws(11,w,44,w,55); }
struct W retw(void) { struct W w={22,33}; return w; }
struct D retd(void) { struct D d={1.0}; return d; }
struct FF retff(void) { struct FF f={1.0f,2.0f}; return f; }
