/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT-0 */
/* An FM-1 application: code in the flash window from 0x02000120 (where m-bootloader calls it), data and stacks
   in RAM from 0x01C40000, clear of the bootloader's (0x01C02000..0x01C0A800), the download-mode plug-in slots
   (0x01C20000..0x01C30000) and the retained area (0x01C7C000..). */
ENTRY(_start)
MEMORY {
  flash (rx) : ORIGIN = 0x02000120, LENGTH = 0x8EEE0
  ram (rwx) : ORIGIN = 0x01C40000, LENGTH = 0x3C000
}
SECTIONS {
  .entry : { KEEP(*(.entry)) } > flash
  .text : { *(.text*) *(.rodata*) . = ALIGN(4); } > flash
  .data : ALIGN(4) { __data_start = .; *(.data*) . = ALIGN(4); __data_end = .; } > ram AT> flash
  __data_load = LOADADDR(.data);
  .bss (NOLOAD) : ALIGN(4) { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(4); __bss_end = .; } > ram
  __sstack_top = ORIGIN(ram) + LENGTH(ram) - 0x2000;
  __stack_top = ORIGIN(ram) + LENGTH(ram);
}
