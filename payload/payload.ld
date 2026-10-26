/* PAYLOAD_ADDR is passed by tools/build.py (--defsym) per region. */
ENTRY(roster_entry)
SECTIONS {
    . = PAYLOAD_ADDR;
    .text : { *(.text.entry) *(.text .text.*) }
    .rodata : { *(.rodata .rodata.*) }
    .data : { *(.data .data.*) *(.sdata .sdata.*) }
    .hooks : { __hooks_start = .; KEEP(*(.hooks)) __hooks_end = .; }
    .bss : { __bss_start = .; *(.bss .bss.*) *(.sbss .sbss.*) *(COMMON) __bss_end = .; }
    /DISCARD/ : { *(.comment) *(.eh_frame) }
}
