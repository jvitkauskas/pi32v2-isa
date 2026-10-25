/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* The first FM-1 application built with the open toolchain alone (clang, ld.lld): the PLAY LED blinks once a
   second, timed by a 100 Hz TIMER5 interrupt; holding PLAY for two seconds puts the unit in USB download mode.
   With -DAUTOTEST it counts 300 ticks instead, keeps the tick count and the time TIMER4 measured in the record
   at 0x01C7C000, and goes to download mode by itself, so a host can check it.

   Hardware facts (fm1-base bsp/ and m-bootloader docs/SPEC.md section 8, used as facts only): the LED columns are
   two 74HC595s (data PA4, clock PA3, latch PA1, a column selected by its bit low; PLAY is column 10); the PLAY LED
   line is PA10, active high, and the PLAY key reads on PA6, low when pressed; PA2 low (the backlight) lets the
   keys read. TIMER5 (0x10900) from the 24 MHz crystal /4 raises source 63; TIMER4 (0x10800) counts the crystal. */

typedef unsigned u32;
#define REG(a) (*(volatile u32 *)(a))

/* GPIO port A (0x50000): +0 out, +4 in, +8 direction (1 input), +0xC digital input, +0x10 pull-up,
   +0x14 pull-down, +0x18 and +0x1C drive strength */
#define PA_OUT REG(0x50000)
#define PA_IN REG(0x50004)
#define PA_DIR REG(0x50008)
#define PA_DIE REG(0x5000C)
#define PA_PU REG(0x50010)
#define PA_PD REG(0x50014)
#define PA_HD0 REG(0x50018)
#define PA_HD REG(0x5001C)

#define T4_CON REG(0x10800)
#define T4_CNT REG(0x10804)
#define T4_PRD REG(0x10808)
#define T5_CON REG(0x10900)
#define T5_CNT REG(0x10904)
#define T5_PRD REG(0x10908)

#define VECTORS ((volatile u32 *)0x01C7FE00)
#define ICFG_WORDS ((volatile u32 *)0x01EEF100)
#define ILAT_CLR REG(0x01EEF1A4)
#define TIMER5_SOURCE 63
#define RECORD ((volatile u32 *)0x01C7C000)

enum { LATCH = 1, BACKLIGHT = 2, CLOCK = 3, DATA = 4, KEYROW = 6, LEDLINE = 10 };
#define BIT(n) (1u << (n))
#define PLAY_COLUMN 0xFBFFu

static volatile u32 ticks;

__attribute__((interrupt)) static void timer5_isr(void) {
  T5_CON |= 0x4000;            /* acknowledge */
  ticks++;
}

static void delay(u32 n) {
  for (volatile u32 i = 0; i < n; i++)
    ;
}

/* one edge at a time, read-modify-write: plain writes were too short for the 595s (fm1-base) */
static void set(u32 bit, int on) {
  if (on)
    PA_OUT |= BIT(bit);
  else
    PA_OUT &= ~BIT(bit);
}

static void shift_out(u32 word) {
  for (int b = 15; b >= 0; b--) {
    set(DATA, word >> b & 1);
    set(CLOCK, 1);
    set(CLOCK, 0);
  }
  set(LATCH, 1);
  set(LATCH, 0);
}

static int play_pressed(void) {
  u32 led = PA_OUT & BIT(LEDLINE);
  set(LEDLINE, 0);
  delay(600);                  /* about 10 us at 360 MHz, generously */
  int down = !(PA_IN & BIT(KEYROW));
  PA_OUT |= led;
  return down;
}

static void download_mode(void) {
  __asm__ volatile("cli");
  T5_CON = 0x4000;             /* timer stopped, its request cleared */
  volatile u32 *m = (volatile u32 *)0x01C7FD80;   /* "usb_update_mode" + NUL (SPEC section 4.2) */
  m[0] = 0x5f627375;
  m[1] = 0x61647075;
  m[2] = 0x6d5f6574;
  m[3] = 0x0065646f;
  __asm__ volatile("csync");
  REG(0x10000) |= 0x10;        /* software reset */
  for (;;)
    ;
}

static void timer5_start(void) {
  __asm__ volatile("cli");
  for (int k = 0; k < 32; k++)
    ICFG_WORDS[k] = 0;         /* every source off */
  ILAT_CLR = 0xFF;             /* no pending soft interrupts */
  VECTORS[TIMER5_SOURCE] = (u32)timer5_isr;
  ICFG_WORDS[TIMER5_SOURCE / 8] = (u32)((1 << 1) | 1) << (4 * (TIMER5_SOURCE % 8));   /* enabled, priority 1 */
  T5_CON = 0x4000;
  T5_CNT = 0;
  T5_PRD = 59999;              /* a period is PRD + 1 counts of 6 MHz: 100 Hz (hw/fm1-2026-10-25-blink) */
  T5_CON = 0x4019;             /* run, crystal, /4 */
  u32 on = 0x300;              /* icfg bits 8 and 9: both gates open (hw/fm1-2026-10-24-app2) */
  __asm__ volatile("csync\n\ticfg = %0\n\tcsync" :: "r"(on) : "memory");
}

int main(void) {
  /* LED column and line outputs; the key row an input with pull-up; the backlight on */
  PA_DIE |= BIT(LATCH) | BIT(CLOCK) | BIT(DATA) | BIT(LEDLINE) | BIT(BACKLIGHT) | BIT(KEYROW);
  PA_OUT &= ~(BIT(LATCH) | BIT(CLOCK) | BIT(DATA) | BIT(LEDLINE) | BIT(BACKLIGHT));
  PA_DIR &= ~(BIT(LATCH) | BIT(CLOCK) | BIT(DATA) | BIT(LEDLINE) | BIT(BACKLIGHT));
  PA_HD0 |= BIT(LEDLINE);
  PA_HD |= BIT(LEDLINE);
  PA_DIR |= BIT(KEYROW);
  PA_PD &= ~BIT(KEYROW);
  PA_PU |= BIT(KEYROW);
  shift_out(PLAY_COLUMN);

  T4_CON = 0;                  /* TIMER4: a free-running crystal counter, to check the tick rate */
  T4_PRD = 0xFFFFFFFF;
  T4_CNT = 0;
  T4_CON = 0x4009;

  timer5_start();
  u32 start = T4_CNT, held = 0, last = 0;
  for (;;) {
    u32 t = ticks;
    if (t == last)
      continue;
    last = t;
    set(LEDLINE, (t / 50) & 1);              /* half a second on, half off */
#ifdef AUTOTEST
    if (t >= 300) {
      u32 elapsed = T4_CNT - start;
      RECORD[0] = 0x4b4e4c42;                /* "BLNK" */
      RECORD[1] = t;
      RECORD[2] = elapsed;                   /* crystal ticks: 24 MHz x 3 s = 72000000 */
      RECORD[3] = PA_OUT;
      download_mode();
    }
#else
    (void)start;
    held = play_pressed() ? held + 1 : 0;
    if (held >= 200)                         /* two seconds */
      download_mode();
#endif
  }
}
