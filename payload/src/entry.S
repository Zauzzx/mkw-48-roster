# Loader trampoline. A Riivolution memory patch replaces one instruction in
# the game (LOADER_HOOK, chosen so it runs once after StaticR.rel is linked)
# with "b roster_entry". We save the volatile registers, apply our hooks, run
# the instruction we overwrote, and jump back.

    .section .text.entry, "ax"
    .globl roster_entry
roster_entry:
    stwu    1, -0x90(1)
    stw     0, 0x08(1)
    mflr    0
    stw     0, 0x94(1)
    stmw    3, 0x0C(1)          # r3-r31: 29 words, ends at 0x80
    mfcr    0
    stw     0, 0x80(1)
    mfctr   0
    stw     0, 0x84(1)
    bl      roster_apply_hooks
    lwz     0, 0x84(1)
    mtctr   0
    lwz     0, 0x80(1)
    mtcr    0
    lmw     3, 0x0C(1)
    lwz     0, 0x94(1)
    mtlr    0
    lwz     0, 0x08(1)
    addi    1, 1, 0x90
    .globl roster_replaced_insn
roster_replaced_insn:
    nop                         # build.py patches in the overwritten instruction
    .globl roster_return
roster_return:
    nop                         # build.py patches in "b LOADER_HOOK+4"
