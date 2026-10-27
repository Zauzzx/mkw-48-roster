#include "addresses.h"
#include "hooks.h"
#include "roster_table.h"

extern const struct Hook __hooks_start[];
extern const struct Hook __hooks_end[];
extern u8 __bss_start[];
extern u8 __bss_end[];

typedef void (*OSReport_t)(const char *fmt, ...);
#define OSReport ((OSReport_t)ADDR_OSReport)

static void flush(u32 addr) {
    __asm__ volatile("dcbst 0, %0\n\tsync\n\ticbi 0, %0\n\tisync" ::"r"(addr) : "memory");
}

static u32 branch(u32 from, u32 to, bool link) {
    return 0x48000000 | ((to - from) & 0x03FFFFFC) | (link ? 1 : 0);
}

// Move an instruction from `from` to `to`, re-aiming it if it is a relative branch.
static u32 relocate(u32 insn, u32 from, u32 to) {
    if ((insn >> 26) == 18 && !(insn & 2)) { // b/bl
        s32 off = (s32)(insn << 6) >> 6 & ~3;
        return branch(to, from + off, insn & 1);
    }
    return insn;
}

void hook_write32(u32 addr, u32 value) {
    *(u32 *)addr = value;
    flush(addr);
}

// Called once from the loader trampoline, after StaticR.rel has been linked.
void roster_apply_hooks(void) {
    // Riivolution only loads the file image, so clear .bss ourselves.
    for (u8 *p = __bss_start; p < __bss_end; p++)
        *p = 0;
    roster_load();
    for (const struct Hook *h = __hooks_start; h < __hooks_end; h++) {
        switch (h->kind) {
        case HOOK_WRITE32: hook_write32(h->addr, h->value); break;
        case HOOK_BRANCH: hook_write32(h->addr, branch(h->addr, h->value, false)); break;
        case HOOK_CALL: hook_write32(h->addr, branch(h->addr, h->value, true)); break;
        case HOOK_REPLACE: {
            u32 t = (u32)h->trampoline;
            hook_write32(t, relocate(*(u32 *)h->addr, h->addr, t));
            hook_write32(t + 4, branch(t + 4, h->addr + 4, false));
            hook_write32(h->addr, branch(h->addr, h->value, false));
            break;
        }
        case HOOK_IMM16: {
            u32 insn = *(u32 *)h->addr;
            if ((insn & 0xFFFF) == h->value >> 16)
                hook_write32(h->addr, (insn & 0xFFFF0000) | (h->value & 0xFFFF));
            else
                OSReport("[mkw-48-roster] skipped patch at %08x: found %08x\n", h->addr, insn);
            break;
        }
        }
    }
    OSReport("[mkw-48-roster] applied %d hooks\n", (int)(__hooks_end - __hooks_start));
    roster_after_hooks();
    roster_patch_tables();
}
