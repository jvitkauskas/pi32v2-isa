/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* What Rust cannot say on pi32v2 yet (no asm! for the architecture, no interrupt ABI): the interrupt entry and
   three special instructions. The handler saves what it uses and returns with rti, and calls Rust. */
typedef unsigned u32;

void rust_timer5_tick(void);

__attribute__((interrupt)) void fm1_timer5_isr(void) { rust_timer5_tick(); }

void fm1_cli(void) { __asm__ volatile("cli" ::: "memory"); }
void fm1_csync(void) { __asm__ volatile("csync" ::: "memory"); }
void fm1_set_icfg(u32 v) { __asm__ volatile("csync\n\ticfg = %0\n\tcsync" :: "r"(v) : "memory"); }
