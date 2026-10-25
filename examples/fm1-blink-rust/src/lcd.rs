// SPDX-FileCopyrightText: 2026 Julius Vitkauskas
// SPDX-License-Identifier: MIT-0
//! The FM-1's 240x240 ST7789 panel on SPI1: PC9 clock, PC10 data out, PC7 chip select, PC8 data/command, the
//! backlight PA2 (low on). Commands go out a byte at a time, pixels by the SPI's DMA, which reads RAM only, so the
//! picture (in flash) goes through a RAM buffer. Hardware facts: Felucca's `hal/fm1_lcd_hw.h` and `src/lcd.c`
//! (pins, registers, the set-up sequence), used as facts; the command set is the ST7789's.

use crate::{and_not, or, rd, wr};

const PA_OUT: u32 = 0x50000;
const PA_DIR: u32 = 0x50008;
const PC_OUT: u32 = 0x50080;
const PC_DIR: u32 = 0x50088;
const IOMAP_CON1: u32 = 0x51020;
const SPI_CON: u32 = 0x11D00;
const SPI_BAUD: u32 = 0x11D04;
const SPI_BUF: u32 = 0x11D08;
const SPI_ADR: u32 = 0x11D0C;
const SPI_CNT: u32 = 0x11D10;
const T4_CNT: u32 = 0x10804;

const BACKLIGHT: u32 = 1 << 2;
const CS: u32 = 1 << 7;
const DC: u32 = 1 << 8;
const CLK: u32 = 1 << 9;
const DO: u32 = 1 << 10;

pub const W: u32 = 240;
pub const H: u32 = 240;

/// Rows per DMA transfer.
const ROWS: usize = 8;
static mut BUF: [u8; ROWS * W as usize * 2] = [0; ROWS * W as usize * 2];

/// TIMER4 counts the 24 MHz crystal (set up by main before this runs).
fn delay_ms(ms: u32) {
    let start = rd(T4_CNT);
    while rd(T4_CNT).wrapping_sub(start) < ms * 24_000 {}
}

fn wait() {
    let start = rd(T4_CNT);
    while rd(SPI_CON) & 0x8000 == 0 && rd(T4_CNT).wrapping_sub(start) < 24_000 * 50 {}
    or(SPI_CON, 0x4000); // the done flag cleared
}

fn cmd(c: u8) {
    and_not(PC_OUT, DC);
    and_not(PC_OUT, CS);
    or(SPI_CON, 0x4000);
    wr(SPI_BUF, c as u32);
    wait();
    or(PC_OUT, CS);
}

/// `bytes` must be in RAM.
fn data(bytes: &[u8]) {
    or(PC_OUT, DC);
    and_not(PC_OUT, CS);
    or(SPI_CON, 0x4000);
    wr(SPI_ADR, bytes.as_ptr() as u32);
    wr(SPI_CNT, bytes.len() as u32);
    wait();
    or(PC_OUT, CS);
}

fn cmd_data(c: u8, d: &[u8]) {
    let buf = unsafe { &mut *core::ptr::addr_of_mut!(BUF) };
    buf[..d.len()].copy_from_slice(d);
    cmd(c);
    data(&buf[..d.len()]);
}

pub fn init() {
    and_not(PA_OUT, BACKLIGHT);
    and_not(PA_DIR, BACKLIGHT);
    or(IOMAP_CON1, 0x10); // SPI1 to its pins
    or(PC_OUT, CS);
    and_not(PC_OUT, DC | CLK | DO);
    and_not(PC_DIR, CS | DC | CLK | DO);
    wr(SPI_CON, 0x4021);
    wr(SPI_BAUD, 4); // 12 MHz
    delay_ms(100);
    cmd(0x01); // SWRESET
    delay_ms(150);
    cmd(0x11); // SLPOUT
    delay_ms(120);
    cmd_data(0x3A, &[0x55]); // COLMOD: 16 bits a pixel
    cmd_data(0x36, &[0x00]); // MADCTL: top left first, RGB
    cmd(0x21); // INVON: the panel is IPS
    cmd(0x13); // NORON
}

/// The whole screen from `pixels`: W x H RGB565 values, most significant byte first.
pub fn show(pixels: &[u8]) {
    cmd_data(0x2A, &[0, 0, 0, (W - 1) as u8]); // CASET
    cmd_data(0x2B, &[0, 0, 0, (H - 1) as u8]); // RASET
    cmd(0x2C); // RAMWR: the pixels follow
    let buf = unsafe { &mut *core::ptr::addr_of_mut!(BUF) };
    for chunk in pixels.chunks(buf.len()) {
        buf[..chunk.len()].copy_from_slice(chunk);
        data(&buf[..chunk.len()]);
    }
    cmd(0x29); // DISPON
}
