/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* The __sync_* functions the compiler calls for atomic read-modify-write operations (as JieLi's compiler does,
   docs/ABI.md), safe between interrupts and between the two cores: each runs with this core's interrupts masked
   (`cli rN` keeps the previous icfg, `sti rN` puts its mask bit back; isa/pi32v2.toml, cli.r and sti.r) and
   holding the shared core lock (`lockset`/`lockclr`, which excludes the other core: hw/fm1-2026-10-24-app4), with
   csync on both sides of the access, as the AC79 SDK's critical sections take it. The lock is never taken twice:
   its recursion is not known.

   The compiler passes an operand narrower than a word without extending it (LLVM's default for these calls), so
   each function takes its operands as words and uses only their low bytes: with a parameter of the narrow type
   it would compare the whole register, and a compare-and-swap whose expected value has its top bit set (-5 as a
   signed char, 0x100 for 0) would store nothing while the caller, comparing the bytes, saw it succeed. The value
   returned is the old one, zero-extended, as the compiler expects. */

typedef unsigned u32;
typedef unsigned short u16;
typedef unsigned char u8;

static inline u32 irq_save(void) {
  u32 s;
  __asm__ volatile("cli %0\n\tlockset\n\tcsync" : "=r"(s) :: "memory");
  return s;
}

static inline void irq_restore(u32 s) { __asm__ volatile("csync\n\tlockclr\n\tsti %0" :: "r"(s) : "memory"); }

#define RMW(N, T, NAME, EXPR)                                                                          \
  T sync_##NAME##_##N(volatile T *p, u32 operand) __asm__("__sync_" #NAME "_" #N);                      \
  T sync_##NAME##_##N(volatile T *p, u32 operand) {                                                     \
    T v = (T)operand;                                                                                   \
    u32 s = irq_save();                                                                                 \
    T old = *p;                                                                                         \
    *p = (EXPR);                                                                                        \
    irq_restore(s);                                                                                     \
    return old;                                                                                         \
  }

#define ALL(N, T, S)                                                                                   \
  RMW(N, T, fetch_and_add, old + v)                                                                     \
  RMW(N, T, fetch_and_sub, old - v)                                                                     \
  RMW(N, T, fetch_and_and, old & v)                                                                     \
  RMW(N, T, fetch_and_or, old | v)                                                                      \
  RMW(N, T, fetch_and_xor, old ^ v)                                                                     \
  RMW(N, T, fetch_and_nand, ~(old & v))                                                                 \
  RMW(N, T, fetch_and_max, (S)old > (S)v ? old : v)                                                     \
  RMW(N, T, fetch_and_min, (S)old < (S)v ? old : v)                                                     \
  RMW(N, T, fetch_and_umax, old > v ? old : v)                                                          \
  RMW(N, T, fetch_and_umin, old < v ? old : v)                                                          \
  RMW(N, T, lock_test_and_set, v)                                                                       \
  T sync_cas_##N(volatile T *p, u32 expect, u32 operand) __asm__("__sync_val_compare_and_swap_" #N);    \
  T sync_cas_##N(volatile T *p, u32 expect, u32 operand) {                                              \
    T expected = (T)expect, v = (T)operand;                                                             \
    u32 s = irq_save();                                                                                 \
    T old = *p;                                                                                         \
    if (old == expected)                                                                                \
      *p = v;                                                                                           \
    irq_restore(s);                                                                                     \
    return old;                                                                                         \
  }

ALL(1, u8, signed char)
ALL(2, u16, short)
ALL(4, u32, int)
