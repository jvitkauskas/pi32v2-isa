#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""The picture the Rust example shows: Ferris (rustacean.net, CC0) on white, a line of text under it, as the
240x240 panel's RGB565 pixels, most significant byte first (the order the ST7789 takes them).

    make_frame.py FERRIS.png OUT.bin [PREVIEW.png]

Needs Pillow; the text is Pillow's built-in font (Aileron, CC0).
"""
import sys

from PIL import Image, ImageDraw, ImageFont

W = H = 240


def frame(src):
    img = Image.new("RGB", (W, H), (255, 255, 255))
    ferris = Image.open(src).convert("RGBA")
    w = 216
    h = round(ferris.height * w / ferris.width)
    ferris = ferris.resize((w, h), Image.LANCZOS)
    img.paste(ferris, ((W - w) // 2, 34), ferris)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=22)
    text = "Hello from Rust"
    x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=font)
    draw.text(((W - (x1 - x0)) // 2 - x0, 188), text, font=font, fill=(0x2b, 0x2b, 0x2b))
    return img


def rgb565_be(img):
    out = bytearray()
    for r, g, b in img.getdata():
        v = (r >> 3) << 11 | (g >> 2) << 5 | b >> 3
        out += bytes((v >> 8, v & 0xFF))
    return bytes(out)


def main():
    img = frame(sys.argv[1])
    open(sys.argv[2], "wb").write(rgb565_be(img))
    if len(sys.argv) > 3:
        img.save(sys.argv[3])


if __name__ == "__main__":
    main()
