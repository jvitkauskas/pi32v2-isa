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
