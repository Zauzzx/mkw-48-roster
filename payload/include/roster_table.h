#pragma once
// The roster, read at boot from /roster48.bin (written by tools/build.py from
// characters/ and roster.toml). Adding a character only changes that file,
// so the compiled payload never has to be rebuilt.

#include "types.h"

#define ROSTER_MAX 48
#define ROSTER_MAGIC 0x52343801 // "R48", format version 1
#define ROSTER_PATH "/roster48.bin"

struct RosterCharacter {
    char suffix[8];    // file suffix: st_kart-<suffix>.szs, <suffix>.brres
    char iconPane[20]; // picture pane in character_64x64_common.brlyt
    u8 statsFrom;      // character ID whose stats are copied
    u8 isCustom;
    u8 pad[2];
};

struct RosterFile {
    u32 magic;
    u32 count;                  // buttons on the select screen
    u8 order[ROSTER_MAX];       // button index -> character ID
    struct RosterCharacter byId[ROSTER_MAX];
    u8 flags;                   // ROSTER_FLAG_*
    u8 pad[7];                  // to a multiple of 32 bytes, for DVD reads
};

// roster.toml `unlock_all`: play as if the save were 100% complete.
#define ROSTER_FLAG_UNLOCK_ALL 0x01
// roster.toml `speedometer`: show it, on the right in 1-player races, and the
// number of decimals (0-3) in bits 2-3.
#define ROSTER_FLAG_SPEEDO 0x02
#define ROSTER_FLAG_SPEEDO_RIGHT 0x10
#define ROSTER_SPEEDO_DECIMALS_SHIFT 2

// Allocated from the system heap at boot: the boot code area the payload
// lives in is too small to hold it as well.
extern struct RosterFile *rosterFile;
#define roster (*rosterFile)
#define rosterCount (roster.count)
#define rosterButtonToId (roster.order)
#define rosterById (roster.byId)
#define rosterUnlockAll (roster.flags & ROSTER_FLAG_UNLOCK_ALL)
#define rosterSpeedo (roster.flags & ROSTER_FLAG_SPEEDO)
#define rosterSpeedoRight (roster.flags & ROSTER_FLAG_SPEEDO_RIGHT)
#define rosterSpeedoDecimals (roster.flags >> ROSTER_SPEEDO_DECIMALS_SHIFT & 3)

// Load /roster48.bin; falls back to the vanilla 24 if it's missing or invalid.
void roster_load(void);
