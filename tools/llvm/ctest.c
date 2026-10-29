/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* C functions for the differential test (tools/llvm/ctest.py): compiled by JieLi's clang and by the LLVM PI32V2
   target, run in the simulator on the same inputs; the results must agree. Each takes up to four int arguments
   and returns an int (f_*) or a long long (l_*). No library calls. */

typedef unsigned u32;
typedef long long i64;
typedef unsigned long long u64;

int f_arith(int a, int b, int c) { return a * 3 + b * c - (a ^ c) + (b >> 2); }
int f_udiv(int a, int b) { return b ? (int)((u32)a / (u32)b + (u32)a % (u32)b) : 7; }
int f_sdiv(int a, int b) { return (b && !(a == (int)0x80000000 && b == -1)) ? a / b * 3 + a % b : 9; }
int f_shifts(int a, int b) { b &= 31; return (a << b) ^ ((u32)a >> b) ^ (a >> (31 - b)); }
int f_cmp(int a, int b) {
  return (a < b) | (a <= b) << 1 | (a > b) << 2 | (a >= b) << 3 | (a == b) << 4 | (a != b) << 5 |
         ((u32)a < (u32)b) << 6 | ((u32)a <= (u32)b) << 7 | ((u32)a > (u32)b) << 8 | ((u32)a >= (u32)b) << 9;
}
int f_minmax(int a, int b, int c) {
  int lo = a < b ? a : b, hi = a < b ? b : a;
  return c < lo ? lo : c > hi ? hi : c;
}
int f_bits(int a) {
  u32 x = a;
  int n = 0;
  while (x) { n += x & 1; x >>= 1; }
  return n;
}
int f_clz(int a) {
  u32 x = a;
  int n = 0;
  if (!x) return 32;
  while (!(x & 0x80000000u)) { x <<= 1; n++; }
  return n;
}
int f_bytes(int a) {
  signed char b = (signed char)a;
  unsigned char u = (unsigned char)a;
  short h = (short)a;
  unsigned short uh = (unsigned short)a;
  return b + u * 3 + h * 5 + uh * 7;
}

static int table[16] = {3, -1, 4, -1, 5, -9, 2, 6, 5, -3, 5, 8, -9, 7, 9, -3};
static unsigned char btab[8] = {200, 1, 255, 0, 17, 128, 64, 99};
int f_table(int i, int j) { return table[i & 15] * btab[j & 7] - table[(i + j) & 15]; }

int counter;
int f_global(int a) { counter += a; return counter * 2; }

int f_loop(int n, int s) {
  int acc = s;
  for (int i = 0; i < (n & 63); i++)
    acc = acc * 31 + (i ^ s);
  return acc;
}

int f_switch(int x) {
  switch (x & 15) {
  case 0: return 11;
  case 1: return -7;
  case 2: return x * 3;
  case 3: return x >> 1;
  case 5: return x ^ 0x5555;
  case 8: return 1000000;
  case 9: return -x;
  case 13: return x + 13;
  default: return 42;
  }
}

static int fib(int n) { return n < 2 ? n : fib(n - 1) + fib(n - 2); }
int f_fib(int n) { return fib(n & 15); }

static int six(int a, int b, int c, int d, int e, int f) { return a - b + c * d - e * f; }
int f_six(int a, int b, int c, int d) { return six(a, b, c, d, a ^ b, c + d); }

struct S { int a, b, c; char d; };
static int take(struct S s, int k) { return s.a * k + s.b - s.c + s.d; }
static struct S make(int a, int b) { struct S s = {a, b, a + b, (char)(a ^ b)}; return s; }
int f_struct(int a, int b, int k) { struct S s = make(a, b); s.c ^= k; return take(s, k) + make(b, a).d; }

/* structs passed by value through real calls (byval in JieLi's bitcode): in r1, after r0-r3 on the stack, a
   small one, and a callee that writes to its copy */
struct T { int a, b, c, d, e; };
struct B3 { char x, y, z; };
__attribute__((noinline)) int byval_mid(int k, struct T t, int m, struct B3 q) {
  t.b += k;
  t.e ^= m;
  return t.a + t.b * 3 - t.c + (t.d ^ t.e) + q.x * 5 + q.z - m;
}
__attribute__((noinline)) int byval_fifth(int a, int b, int c, int d, struct T t) { return t.e - t.a + a * b - c + d; }
int f_byval(int a, int b, int c) {
  struct T t = {a, b, c, a ^ b, b - c};
  struct B3 q = {(char)a, (char)b, (char)c};
  int r = byval_mid(c, t, a, q);
  return r + t.b + byval_fifth(a, b, c, r, t) * 7;
}

int f_local_array(int a, int b) {
  int v[10];
  for (int i = 0; i < 10; i++)
    v[i] = a * i + b;
  int s = 0;
  for (int i = 9; i >= 0; i -= 2)
    s += v[i] ^ v[9 - i];
  return s;
}

static int sum(int n, ...) {
  __builtin_va_list ap;
  __builtin_va_start(ap, n);
  int s = 0;
  for (int i = 0; i < n; i++)
    s = s * 7 + __builtin_va_arg(ap, int);
  __builtin_va_end(ap);
  return s;
}
int f_varargs(int a, int b, int c) { return sum(5, a, b, c, a + b, b + c) + sum(1, a); }

i64 l_add(int a, int b, int c, int d) { return ((i64)a << 32 | (u32)b) + ((i64)c << 32 | (u32)d); }
i64 l_sub(int a, int b, int c, int d) { return ((i64)a << 32 | (u32)b) - ((i64)c << 32 | (u32)d); }
i64 l_shift(int a, int b, int c) { i64 x = (i64)a << 32 | (u32)b; c &= 63; return (x << c) ^ (x >> (63 - c)); }
int l_cmp(int a, int b, int c, int d) {
  i64 x = (i64)a << 32 | (u32)b, y = (i64)c << 32 | (u32)d;
  return (x < y) | (x == y) << 1 | ((u64)x < (u64)y) << 2;
}

/* floating point and 64-bit multiply/divide: library helpers (compiler-rt's for the LLVM build) */
static float fx(int a) { return (float)(a >> 6) / 64.0f; }
static int fbits(float f) { union { float f; int i; } u = {f}; return u.i; }
int g_fadd(int a, int b) { return fbits(fx(a) + fx(b)); }
int g_fsub(int a, int b) { return fbits(fx(a) - fx(b)); }
int g_fmul(int a, int b) { return fbits(fx(a) * fx(b)); }
int g_fdiv(int a, int b) { float d = fx(b); return fbits(fx(a) / (d == 0.0f ? 1.0f : d)); }
int g_fcmp(int a, int b) { float x = fx(a), y = fx(b); return (x < y) | (x <= y) << 1 | (x == y) << 2 | (x > y) << 3; }
int g_fconv(int a) { float x = fx(a); return (int)x + (int)(unsigned)(x < 0 ? -x : x) * 3; }
int g_dmix(int a, int b) {
  double x = (double)a / 7.0, y = (double)b * 0.25;
  double z = x * y + x - y;
  return (int)(z / 4294967296.0) ^ (int)(float)x;   /* in range: an int overflow would be undefined */
}
i64 l_mul(int a, int b, int c, int d) { return ((i64)a << 32 | (u32)b) * ((i64)c << 32 | (u32)d); }
i64 l_div(int a, int b, int c, int d) {
  i64 x = (i64)a << 32 | (u32)b, y = (i64)c << 32 | (u32)d;
  return (y == 0 || (y == -1 && x == (i64)0x8000000000000000ull)) ? 5 : x / y + x % y;
}
i64 l_udiv(int a, int b, int c, int d) {
  u64 x = (u64)(u32)a << 32 | (u32)b, y = (u64)(u32)c << 32 | (u32)d;
  return y ? (i64)(x / y ^ x % y) : 3;
}

/* atomics: __sync_* calls (the LLVM build links tools/llvm/runtime/sync.c) */
static int shared;
int g_atomic(int a, int b) {
  shared = a;
  int r = __atomic_fetch_add(&shared, b, __ATOMIC_SEQ_CST);
  r ^= __atomic_exchange_n(&shared, r + 1, __ATOMIC_SEQ_CST);
  int expect = r + 1;
  __atomic_compare_exchange_n(&shared, &expect, b, 0, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST);
  __atomic_fetch_or(&shared, 0x100, __ATOMIC_SEQ_CST);
  return shared ^ r ^ __atomic_load_n(&shared, __ATOMIC_SEQ_CST);
}

/* tail calls: a call whose result is returned becomes a goto (in the LLVM build) */
__attribute__((noinline)) static int tailee(int a, int b) { return a * 3 - b; }
int f_tail(int a, int b) { return b > 0 ? tailee(a, b) : tailee(b ^ a, a); }
__attribute__((noinline)) static i64 tailee64(int a, int b) { return (i64)a * b; }
i64 l_tail(int a, int b) { return tailee64(a + 1, b); }

/* single-instruction idioms: clz, byte swap, rotates, bit fields, multiply by a constant */
int f_idioms(int a, int b) {
  u32 x = a, n = b & 31;
  u32 r = (u32)__builtin_clz(x | 1) + __builtin_bswap32(x) * 3;
  r ^= (x >> n) | (x << ((32 - n) & 31));
  r += (x >> 5) | (x << 27);
  r ^= (x >> 8) & 0xf;
  r += (u32)((a << 20) >> 28) + (u32)((a << 3) >> 3);
  r ^= (u32)(signed char)b + (u32)(short)a * 7 + (unsigned char)(a >> 3) + (unsigned short)b;
  return (int)(r * 1000 + (x & 0x3ff));
}

/* JieLi's builtins (not popcount: the AC791N runs popcnt as a nop, so JieLi's build differs on purpose) */
int f_builtins(int a, int b) {
  int r = __builtin_pi32v2_clz(a) + __builtin_pi32v2_cls(b) * 3 + __builtin_pi32v2_zcmp(a - b) * 7;
  r ^= __builtin_pi32v2_rev8(a ^ b) + __builtin_pi32v2_uextra(a, 4, 8) + __builtin_pi32v2_sextra(b, 3, 9);
  r += __builtin_pi32v2_uextra(b, 28, 8) + __builtin_pi32v2_sextra(a, 16, 16);
  int lo = a < b ? a : b, hi = (unsigned)a > (unsigned)b ? a : b;
  return r + lo * 5 + hi;
}

/* pointer walks: post-increment loads and stores of words, halves and signed bytes */
static int wbuf[24];
static short hbuf[24];
static signed char cbuf[24];
int f_walk(int a, int b) {
  int n = (a & 15) + 8;
  int *w = wbuf;
  short *h = hbuf;
  signed char *c = cbuf;
  for (int i = 0; i < n; i++) {
    *w++ = a + i * b;
    *h++ = (short)(a ^ (i << 9));
    *c++ = (signed char)(b + i * 37);
  }
  int s = 0;
  const int *pw = wbuf;
  const short *ph = hbuf;
  const signed char *pc = cbuf;
  for (int i = 0; i < n; i++)
    s = s * 3 + *pw++ + *ph++ - *pc++;
  return s;
}

/* negative float constants, and the return address read in a branch (both were compiler errors once) */
static unsigned retaddr_seen;
__attribute__((noinline)) static int note_ra(int a) {
  if (a & 1)
    retaddr_seen = (unsigned)__builtin_return_address(0) != 0;
  return a;
}
int g_negconst(int a, int b) {
  float x = fx(a) * -0.5f - 3.25f;
  float y = fx(b) / -2.0f;
  return fbits(x + y) ^ note_ra(a) ^ (int)retaddr_seen;
}

/* a call in a conditional block (Felucca's panel set-up on the FM-1): a table of commands, each with its count of
   data bytes, the data sent only when there is some. The call must end the block: it returns to the instruction
   after it, which then runs whatever the condition was */
unsigned char cmdtab[] = {0x01, 0, 0x11, 0, 0x3A, 1, 0x55, 0x36, 1, 0x00, 0x21, 0, 0x2A, 4, 0, 0, 0, 239};
static unsigned sent;
__attribute__((noinline)) static void send(const unsigned char *p, unsigned n) {
  while (n--)
    sent = sent * 31u + *p++;
}
__attribute__((noinline)) static void cmd(unsigned c) { sent = sent * 7u + c; }
int f_tablecall(int a, int b) {
  unsigned r, n;
  sent = (unsigned)a;
  for (r = 0; r < sizeof cmdtab; r += 2u + (n & 255u)) {
    n = cmdtab[r + 1u];
    if ((unsigned)b >> (r & 31) & 1)
      continue;
    cmd(cmdtab[r]);
    if (n)
      send(cmdtab + r + 2u, n);
  }
  return (int)sent;
}

/* ---- selection checks (size work) ---- */
int f_rsub(int a, int b) { return 100 - a + (0x12000 - b) + (-a) + (7 - b); }
int f_bitops(int a, int b) {
  b &= 31;
  return (a | (1u << b)) ^ (a & ~(1u << b)) ^ (a ^ (1u << b)) ^ (a & (1u << b)) ^ (a & ~b);
}
int f_insert(int a, int b, int c) {
  int r = (a & ~0xff00) | ((b & 0xff) << 8);
  r ^= (c & ~0x7f80) | (b << 7 & 0x7f80);
  int d = (a & 0xffffff00) | (c & 0xff);
  int e = (a & 0x7f) | ((b & 0x7f) << 7) | ((c & 0x7f) << 14);
  return r ^ d ^ (e * 3);
}
long long l_sh1(long long a, int b) { return (a << 1) ^ (a >> 1) ^ (long long)((unsigned long long)a >> 1) ^ b; }
long long l_sh31(long long a, int b) { return (a << 31) ^ (a >> 31) ^ (long long)((unsigned long long)a >> 31) ^ b; }
long long l_sh32(long long a, int b) { return (a << 32) ^ (a >> 32) ^ (long long)((unsigned long long)a >> 32) ^ b; }
long long l_sh33(long long a, int b) { return (a << 33) ^ (a >> 33) ^ (long long)((unsigned long long)a >> 33) ^ b; }
long long l_sh63(long long a, int b) { return (a << 63) ^ (a >> 63) ^ (long long)((unsigned long long)a >> 63) ^ b; }
long long l_sh45(long long a, int b) { return (a << 45) + (a >> 45) + (long long)((unsigned long long)a >> 45) + b; }
struct big { int w[80]; short h[80]; unsigned char b[200]; };
static struct big gbig;
int f_anchor(int a, int b) {
  struct big *s = &gbig;
  s->w[30] = a; s->w[31] = b; s->w[33] = a ^ b; s->h[40] = a; s->h[41] = b; s->b[100] = a; s->b[101] = b; s->b[103] = a + b;
  return s->w[30] + s->w[31] * 3 + s->w[33] * 5 + s->h[40] * 7 + s->h[41] * 9 + s->b[100] + s->b[101] * 2 + s->b[103] * 3 + s->w[a & 15];
}
int f_dbnz(int a, int b) {
  int s = 0;
  a = (a & 15) + 1;
  do { s += a * b; } while (--a);
  int n = (b & 7) + 1;
  for (int i = n; i; i--) s ^= i;
  return s;
}
int f_selz(int a, int b) { return (a ? b : 7) + (a == 0 ? 3 : b) + (b ? a : 11); }
int f_post(int a, int b) {
  static int buf[24];
  int *p = buf; int s = 0;
  for (int i = 0; i < 24; i++) *p++ = a + i * b;
  p = buf;
  for (int i = 0; i < 24; i++) s += *p++ * (i + 1);
  return s;
}

/* ---- round 2 selection checks (size work): far struct fields, constant stores, pair shifts, 64/32 divides ---- */
struct farst { int w[700]; unsigned char b[64]; short h[16]; };
static struct farst gfar;
int f_far(int a, int b) {
  struct farst *s = &gfar;
  int r = s->w[400];
  if (a & 1) r += s->w[401] * 3;
  else r ^= s->w[402];
  if (b & 2) { s->w[403] = a; r += s->w[404]; }
  s->w[400] += b;
  s->w[650]++; s->w[650] += a;
  if (a & 4) s->b[7] = b;
  return r + s->w[400] + s->w[650] + s->w[a & 7] + s->b[7];
}
int f_farloop(int a, int b) {
  struct farst *s = &gfar;
  int r = 0;
  for (int i = 0; i < (a & 7) + 1; i++) { s->w[600 + (i & 3)] += b + i; r += s->w[500] ^ s->w[610]; s->w[610] = r; }
  return r + s->w[600] + s->w[603];
}
void f_stc_helper(float *p) { p[1] = 1.0f; p[2] = 1.0f; p[3] = 1.0f; p[4] = 1.0f; p[5] = 2.0f; p[6] = 2.0f; }
int f_stc(int a, int b) {
  static float buf[8];
  f_stc_helper(buf);
  buf[0] = (float)a;
  return (int)(buf[0] + buf[1] + buf[2] * 4 + buf[3] * 8 + buf[4] * 16 + buf[5] * 32 + buf[6] * b);
}
#define PSH(n) long long l_psh##n(long long a, int b) { return (a << n) ^ (a >> n) ^ (long long)((unsigned long long)a >> n) ^ b; }
PSH(2) PSH(3) PSH(5) PSH(7) PSH(8) PSH(12) PSH(15) PSH(16) PSH(17) PSH(20) PSH(24) PSH(29) PSH(30)
long long l_pshlo(long long a, int b) { return (long long)((int)(a >> 16) + (int)((a * b) >> 7) + (int)((a << 5) >> 31)) ^ (a >> 3); }
long long l_dnn(long long a, int b) { return a / (long long)(unsigned)(b & 0x7fffffff | 1); }
long long l_dabs(long long a, int b) { int d = (b < 0 ? -b : b) / 4 + 3; return a / d + a % d; }
long long l_dzx(long long a, unsigned b) { return a / (long long)b + (a % (long long)b); }
int f_clr31(int a, int b) { return (a & 0x7fffffff) + (b & 0x7fffffff); }
