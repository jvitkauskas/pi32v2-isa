#define F(n,e) int n(void) { return (e); }
F(charbits,__CHAR_BIT__) F(wchar_is_int,__builtin_types_compatible_p(__WCHAR_TYPE__,int))
enum Neg { N=-1,P=1 }; enum Wide { W=0xffffffffU }; enum Huge { H=0x100000000ULL };
F(eneg_size,sizeof(enum Neg)) F(ewide_size,sizeof(enum Wide)) F(ehuge_size,sizeof(enum Huge))
F(eneg_signed,(enum Neg)-1<0) F(ewide_signed,(enum Wide)-1<0) F(ehuge_align,__alignof__(enum Huge))
struct LL { char a; long long b; char c; }; F(lloff,__builtin_offsetof(struct LL,b)) F(llsize,sizeof(struct LL))
extern void small(char,short,_Bool); void smallcall(int a,int b,int c) { small(a,b,c); }
char rc(int x) { return x; } short rs(int x) { return x; } _Bool rb(int x) { return x; }
struct S { int a,b; }; extern void sx(struct S); void mutate(struct S x) { x.a=7; sx(x); }
union U { int i; float f; }; extern void ux(union U); void unionpass(void) { union U u={7}; ux(u); } union U unionret(void) { union U u={7}; return u; }
extern struct S sr(int); int structcaller(void) { struct S s=sr(7); return s.a+s.b; }
extern void three(int,int,int,struct S,int); void structsplit(void) { struct S s={4,5}; three(1,2,3,s,6); }
extern void variadic(int,...); void vstruct(void) { struct S s={4,5}; variadic(1,s,6); }
void aligned_frame(void) { char x[8] __attribute__((aligned(32))); extern void escape(void *); escape(x); }
extern void fifth(int,int,int,int,struct S,int);
void structstack(void) { struct S s={4,5}; fifth(1,2,3,4,s,6); }
unsigned char ruc(int x) { return x; } unsigned short rus(int x) { return x; }
extern void usmall(unsigned char,unsigned short); void ucall(int a,int b) { usmall(a,b); }
