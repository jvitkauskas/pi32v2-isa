/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* The __sync_* functions the compiler calls for atomic read-modify-write operations (as JieLi's compiler does,
   docs/ABI.md), for one core: each runs with interrupts masked (`cli rN` keeps the previous icfg, `sti rN` puts
   its mask bit back; isa/pi32v2.toml, cli.r and sti.r). Not safe between the two cores: that needs the testset
   lock (docs/CPU1.md). */

typedef unsigned u32;
typedef unsigned short u16;
typedef unsigned char u8;

static inline u32 irq_save(void) {
  u32 s;
  __asm__ volatile("cli %0" : "=r"(s) :: "memory");
  return s;
}

static inline void irq_restore(u32 s) { __asm__ volatile("sti %0" :: "r"(s) : "memory"); }

#define RMW(N, T, NAME, EXPR)                                                                          \
  T sync_##NAME##_##N(volatile T *p, T v) __asm__("__sync_" #NAME "_" #N);                              \
  T sync_##NAME##_##N(volatile T *p, T v) {                                                             \
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
  T sync_cas_##N(volatile T *p, T expected, T v) __asm__("__sync_val_compare_and_swap_" #N);            \
  T sync_cas_##N(volatile T *p, T expected, T v) {                                                      \
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
