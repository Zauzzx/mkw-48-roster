#pragma once
// Patches applied to the game once StaticR.rel is loaded. Each macro adds one
// record to the .hooks section; runtime.c walks that section at startup.
// Addresses come from the generated addresses.h (one per game region).

#include "types.h"

enum HookKind {
    HOOK_WRITE32 = 1, // *addr = value
    HOOK_BRANCH = 2,  // addr: b value
    HOOK_CALL = 3,    // addr: bl value
    HOOK_REPLACE = 4, // like HOOK_BRANCH, and fill a trampoline that calls the original
    HOOK_IMM16 = 5,   // change an instruction's 16-bit immediate: value = expected << 16 | new
};

struct Hook {
    u32 kind;
    u32 addr;
    u32 value;
    u32 *trampoline; // HOOK_REPLACE only: 2 words, [first instruction, b addr+4]
};

#define HOOK_CAT_(a, b) a##b
#define HOOK_CAT(a, b) HOOK_CAT_(a, b)
#define HOOK_RECORD(kind, addr, value, tramp) \
    __attribute__((section(".hooks"), used)) static const struct Hook HOOK_CAT(hook_, __COUNTER__) = { \
        (kind), (u32)(addr), (u32)(value), (tramp)}

// Replace the function at `addr` with `fn` (same signature).
#define REPLACE_FUNCTION(addr, fn) HOOK_RECORD(HOOK_BRANCH, addr, fn, NULL)

// Replace the function at `addr` with `fn`, and define `orig` (with type
// `type`, a function pointer type) that still runs the game's version.
#define REPLACE_FUNCTION_ORIG(addr, fn, type, orig) \
    __attribute__((aligned(4))) static u32 HOOK_CAT(orig, _tramp)[2]; \
    static const type orig = (type)HOOK_CAT(orig, _tramp); \
    HOOK_RECORD(HOOK_REPLACE, addr, fn, HOOK_CAT(orig, _tramp))

#define PATCH_BRANCH(addr, fn) HOOK_RECORD(HOOK_BRANCH, addr, fn, NULL)
#define PATCH_CALL(addr, fn) HOOK_RECORD(HOOK_CALL, addr, fn, NULL)
#define PATCH_WRITE32(addr, value) HOOK_RECORD(HOOK_WRITE32, addr, value, NULL)
// Change the immediate of e.g. `li rX, expected` to `new`, keeping the register.
// Skipped (and logged) if the instruction doesn't hold `expected`.
#define PATCH_IMM16(addr, expected, new) \
    HOOK_RECORD(HOOK_IMM16, addr, ((u32)(expected) << 16) | ((u32)(new) & 0xFFFF), NULL)

// Write one instruction now (flushing caches), for patches that depend on data
// only known at boot.
void hook_write32(u32 addr, u32 value);

// Runs once all hooks are in place; for patches computed from the roster.
void roster_after_hooks(void);

// Point game tables at the custom characters' data (runs after the hooks).
void roster_patch_tables(void);
