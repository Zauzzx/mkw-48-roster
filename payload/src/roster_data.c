#include "addresses.h"
#include "hooks.h"
#include "roster_table.h"

_Static_assert(sizeof(struct RosterFile) % 32 == 0, "DVD reads need a multiple of 32 bytes");

__attribute__((aligned(32))) struct RosterFile roster;

typedef s32 (*DVDConvertPathToEntrynum_t)(const char *path);
typedef bool (*DVDFastOpen_t)(s32 entrynum, void *fileInfo);
typedef s32 (*DVDReadPrio_t)(void *fileInfo, void *buf, s32 len, s32 offset, s32 prio);
typedef bool (*DVDClose_t)(void *fileInfo);
typedef void (*OSReport_t)(const char *fmt, ...);

// Vanilla select-screen order, read across the 4-column grid.
static const u8 vanillaOrder[24] = {0x00, 0x07, 0x10, 0x0F, 0x0A, 0x11, 0x12, 0x14, 0x08, 0x0D, 0x0E, 0x05,
                                    0x06, 0x0C, 0x01, 0x04, 0x0B, 0x02, 0x09, 0x03, 0x13, 0x17, 0x16, 0x15};

static void useVanilla(void) {
    roster.magic = ROSTER_MAGIC;
    roster.count = 24;
    for (u32 i = 0; i < ROSTER_MAX; i++) {
        roster.order[i] = i < 24 ? vanillaOrder[i] : 0;
        roster.byId[i].statsFrom = i;
        roster.byId[i].isCustom = 0;
    }
}

void roster_load(void) {
    __attribute__((aligned(4))) u8 fileInfo[0x40]; // DVDFileInfo is 0x3C bytes
    s32 entry = ((DVDConvertPathToEntrynum_t)ADDR_DVDConvertPathToEntrynum)(ROSTER_PATH);
    bool ok = false;
    if (entry >= 0 && ((DVDFastOpen_t)ADDR_DVDFastOpen)(entry, fileInfo)) {
        ok = ((DVDReadPrio_t)ADDR_DVDReadPrio)(fileInfo, &roster, sizeof(roster), 0, 2) == sizeof(roster);
        ((DVDClose_t)ADDR_DVDClose)(fileInfo);
    }
    if (ok && roster.magic == ROSTER_MAGIC && roster.count >= 1 && roster.count <= ROSTER_MAX) {
        for (u32 i = 0; i < ROSTER_MAX; i++) { // never trust a string to be terminated
            roster.byId[i].suffix[sizeof(roster.byId[i].suffix) - 1] = 0;
            roster.byId[i].iconPane[sizeof(roster.byId[i].iconPane) - 1] = 0;
            if (roster.byId[i].statsFrom >= 24)
                roster.byId[i].statsFrom = 0;
        }
        for (u32 i = 0; i < roster.count; i++)
            if (roster.order[i] >= ROSTER_MAX)
                roster.order[i] = 0;
    } else {
        ((OSReport_t)ADDR_OSReport)("[mkw-48-roster] " ROSTER_PATH " missing or invalid, using the vanilla roster\n");
        useVanilla();
    }
    ((OSReport_t)ADDR_OSReport)("[mkw-48-roster] roster: %d characters\n", (int)roster.count);
}
