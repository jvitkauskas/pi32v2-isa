// SPDX-FileCopyrightText: 2026 Julius Vitkauskas
// SPDX-License-Identifier: MIT-0
//! fm1-blink in Rust: Ferris on the screen (lcd.rs, the picture from make_frame.py), and the PLAY LED blinking
//! once a second, timed by a 100 Hz TIMER5 interrupt; holding PLAY for two seconds puts the unit in USB download mode. With the `autotest` feature it counts 300 ticks instead, keeps the
//! tick count and the time TIMER4 measured in the record at 0x01C7C000 and goes to download mode by itself.
//!
//! The same program as `examples/fm1-blink/blink.c` (its comments give the hardware facts and their sources).
//! `shim.c` holds the interrupt entry and the three special instructions Rust cannot emit on pi32v2 yet.

#![no_std]
#![no_main]

use core::panic::PanicInfo;
use core::ptr::{read_volatile, write_volatile};
use core::sync::atomic::{AtomicU32, Ordering::Relaxed};

mod lcd;

/// The picture: lcd::W x lcd::H RGB565 pixels, most significant byte first (build.sh makes it).
static FRAME: &[u8; (lcd::W * lcd::H * 2) as usize] = include_bytes!(env!("FM1_FRAME"));

// GPIO port A: +0 out, +4 in, +8 direction (1 input), +0xC digital input, +0x10 pull-up, +0x14 pull-down,
// +0x18 and +0x1C drive strength
const PA_OUT: u32 = 0x50000;
const PA_IN: u32 = 0x50004;
const PA_DIR: u32 = 0x50008;
const PA_DIE: u32 = 0x5000C;
const PA_PU: u32 = 0x50010;
const PA_PD: u32 = 0x50014;
const PA_HD0: u32 = 0x50018;
const PA_HD: u32 = 0x5001C;

const T4_CON: u32 = 0x10800;
const T4_CNT: u32 = 0x10804;
const T4_PRD: u32 = 0x10808;
const T5_CON: u32 = 0x10900;
const T5_CNT: u32 = 0x10904;
const T5_PRD: u32 = 0x10908;

const VECTORS: u32 = 0x01C7FE00;
const ICFG_WORDS: u32 = 0x01EEF100;
const ILAT_CLR: u32 = 0x01EEF1A4;
const TIMER5_SOURCE: u32 = 63;
const RECORD: u32 = 0x01C7C000;

const LATCH: u32 = 1;
const BACKLIGHT: u32 = 2;
const CLOCK: u32 = 3;
const DATA: u32 = 4;
const KEYROW: u32 = 6;
const LEDLINE: u32 = 10;
const PLAY_COLUMN: u32 = 0xFBFF;

const fn bit(n: u32) -> u32 {
    1 << n
}

fn rd(a: u32) -> u32 {
    unsafe { read_volatile(a as *const u32) }
}

fn wr(a: u32, v: u32) {
    unsafe { write_volatile(a as *mut u32, v) }
}

fn or(a: u32, m: u32) {
    wr(a, rd(a) | m)
}

fn and_not(a: u32, m: u32) {
    wr(a, rd(a) & !m)
}

unsafe extern "C" {
    fn fm1_timer5_isr();
    fn fm1_cli();
    fn fm1_csync();
    fn fm1_set_icfg(v: u32);
}

static TICKS: AtomicU32 = AtomicU32::new(0);

/// Called by the interrupt entry in shim.c.
#[unsafe(no_mangle)]
pub extern "C" fn rust_timer5_tick() {
    or(T5_CON, 0x4000); // acknowledge
    TICKS.store(TICKS.load(Relaxed) + 1, Relaxed); // the only writer
}

fn delay(n: u32) {
    for i in 0..n {
        core::hint::black_box(i);
    }
}

/// One edge at a time, read-modify-write: plain writes were too short for the 595s (fm1-base).
fn set(b: u32, on: bool) {
    if on {
        or(PA_OUT, bit(b))
    } else {
        and_not(PA_OUT, bit(b))
    }
}

fn shift_out(word: u32) {
    for b in (0..16).rev() {
        set(DATA, word >> b & 1 != 0);
        set(CLOCK, true);
        set(CLOCK, false);
    }
    set(LATCH, true);
    set(LATCH, false);
}

#[cfg_attr(feature = "autotest", allow(dead_code))]
fn play_pressed() -> bool {
    let led = rd(PA_OUT) & bit(LEDLINE);
    set(LEDLINE, false);
    delay(600);
    let down = rd(PA_IN) & bit(KEYROW) == 0;
    or(PA_OUT, led);
    down
}

fn download_mode() -> ! {
    unsafe { fm1_cli() };
    wr(T5_CON, 0x4000); // timer stopped, its request cleared
    let m = 0x01C7FD80; // "usb_update_mode" + NUL (m-bootloader SPEC section 4.2)
    for (k, w) in [0x5f627375u32, 0x61647075, 0x6d5f6574, 0x0065646f].iter().enumerate() {
        wr(m + 4 * k as u32, *w);
    }
    unsafe { fm1_csync() };
    or(0x10000, 0x10); // software reset
    loop {}
}

fn timer5_start() {
    unsafe { fm1_cli() };
    for k in 0..32 {
        wr(ICFG_WORDS + 4 * k, 0); // every source off
    }
    wr(ILAT_CLR, 0xFF); // no pending soft interrupts
    wr(VECTORS + 4 * TIMER5_SOURCE, fm1_timer5_isr as *const () as usize as u32);
    wr(ICFG_WORDS + 4 * (TIMER5_SOURCE / 8), ((1 << 1) | 1) << (4 * (TIMER5_SOURCE % 8))); // on, priority 1
    wr(T5_CON, 0x4000);
    wr(T5_CNT, 0);
    wr(T5_PRD, 59999); // a period is PRD + 1 counts of 6 MHz: 100 Hz
    wr(T5_CON, 0x4019); // run, crystal, /4
    unsafe { fm1_set_icfg(0x300) }; // icfg bits 8 and 9: both gates open
}

#[unsafe(no_mangle)]
pub extern "C" fn main() -> ! {
    // LED column and line outputs; the key row an input with pull-up; the backlight on
    let outs = bit(LATCH) | bit(CLOCK) | bit(DATA) | bit(LEDLINE) | bit(BACKLIGHT);
    or(PA_DIE, outs | bit(KEYROW));
    and_not(PA_OUT, outs);
    and_not(PA_DIR, outs);
    or(PA_HD0, bit(LEDLINE));
    or(PA_HD, bit(LEDLINE));
    or(PA_DIR, bit(KEYROW));
    and_not(PA_PD, bit(KEYROW));
    or(PA_PU, bit(KEYROW));
    shift_out(PLAY_COLUMN);

    wr(T4_CON, 0); // TIMER4: a free-running crystal counter, for the panel's delays and to check the tick rate
    wr(T4_PRD, 0xFFFF_FFFF);
    wr(T4_CNT, 0);
    wr(T4_CON, 0x4009);

    lcd::init();
    lcd::show(FRAME);

    timer5_start();
    let start = rd(T4_CNT);
    let (mut held, mut last) = (0u32, 0u32);
    loop {
        let t = TICKS.load(Relaxed);
        if t == last {
            continue;
        }
        last = t;
        set(LEDLINE, (t / 50) & 1 != 0); // half a second on, half off
        if cfg!(feature = "autotest") {
            if t >= 300 {
                let elapsed = rd(T4_CNT).wrapping_sub(start);
                wr(RECORD, 0x4b4e4c42); // "BLNK"
                wr(RECORD + 4, t);
                wr(RECORD + 8, elapsed); // crystal ticks: 24 MHz x 3 s = 72000000
                wr(RECORD + 12, rd(PA_OUT));
                wr(RECORD + 16, 0x54535552); // "RUST": this build
                download_mode();
            }
        } else {
            held = if play_pressed() { held + 1 } else { 0 };
            if held >= 200 {
                download_mode(); // two seconds
            }
        }
        let _ = start;
    }
}

#[panic_handler]
fn panic(_: &PanicInfo) -> ! {
    download_mode()
}
