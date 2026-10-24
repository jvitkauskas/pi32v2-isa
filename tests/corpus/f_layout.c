
#define OFF(T,m) __builtin_offsetof(T,m)
struct S { char a; short b; int c; long long d; char e; };
struct P { char a; int b; long long c; } __attribute__((packed));
union U { char a[9]; long long b; double c; };
#define F(n,e) int n(void) { return (e); }
F(s_size,sizeof(struct S)) F(s_align,__alignof__(struct S))
F(s_b,OFF(struct S,b)) F(s_c,OFF(struct S,c)) F(s_d,OFF(struct S,d)) F(s_e,OFF(struct S,e))
F(p_size,sizeof(struct P)) F(p_align,__alignof__(struct P)) F(p_b,OFF(struct P,b)) F(p_c,OFF(struct P,c))
F(u_size,sizeof(union U)) F(u_align,__alignof__(union U)) F(u_c,OFF(union U,c))
struct B { unsigned a:3; signed b:5; unsigned c:9; unsigned d:15; unsigned e:1; };
F(b_size,sizeof(struct B)) F(b_align,__alignof__(struct B))
#define BITS(n,m,v) unsigned n(void) { union { struct B b; unsigned w[2]; } x={0}; x.b.m=v; return x.w[0]; }
BITS(bit_a,a,7) BITS(bit_b,b,-1) BITS(bit_c,c,511) BITS(bit_d,d,32767)
unsigned bit_e(void) { union {struct B b; unsigned w[2];} x={0}; x.b.e=1; return x.w[1]; }
int signed_field(struct B *p) { return p->b; }
struct Cross { unsigned a:28; unsigned b:8; char c; };
struct Zero { unsigned char a:3; unsigned :0; unsigned char b:2; char c; };
struct PackedBits { unsigned a:28; unsigned b:8; char c; } __attribute__((packed));
F(cross_size,sizeof(struct Cross)) F(cross_c,OFF(struct Cross,c))
F(zero_size,sizeof(struct Zero)) F(zero_align,__alignof__(struct Zero)) F(zero_c,OFF(struct Zero,c))
F(pb_size,sizeof(struct PackedBits)) F(pb_align,__alignof__(struct PackedBits)) F(pb_c,OFF(struct PackedBits,c))
unsigned cross_b(void) { union {struct Cross b; unsigned w[2];} x={0}; x.b.b=255; return x.w[1]; }
long long packed_bits(void) { union {struct PackedBits b; long long w;} x={0}; x.b.b=255; return x.w; }
