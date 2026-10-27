// Character ID hooks: make the 24 Mii/biker IDs behave like regular drivers.
// Function signatures follow Pulsar's GameSource headers; addresses are
// filled in per region by addresses/<game id>.toml.

#include "addresses.h"
#include "hooks.h"
#include "roster_table.h"

static bool validId(s32 id) {
    return id >= 0 && id < ROSTER_MAX;
}

// Menu-preview models. The menu swaps Peach, Daisy and Rosalina to dedicated
// models before looking up the file name; vanilla uses IDs 0x2D-0x2F for
// those, which are now roster slots, so the swap is moved to IDs past the end.
#define MENU_PEACH 0x30
#define MENU_DAISY 0x31
#define MENU_ROSALINA 0x32
PATCH_IMM16(ADDR_BindDriverBRRES_PeachSwap, 0x2D, MENU_PEACH);
PATCH_IMM16(ADDR_BindDriverBRRES_DaisySwap, 0x2E, MENU_DAISY);
PATCH_IMM16(ADDR_BindDriverBRRES_RosalinaSwap, 0x2F, MENU_ROSALINA);

// ArchiveMgr::GetKartArchivePostfix(CharacterId): the "mr" in st_kart-mr.szs,
// also used for menu models (<postfix>.brres in Driver.szs).
typedef const char *(*GetKartArchivePostfix_t)(s32 id);
static const char *kartArchivePostfix(s32 id);
REPLACE_FUNCTION_ORIG(ADDR_GetKartArchivePostfix, kartArchivePostfix, GetKartArchivePostfix_t, origKartArchivePostfix);
static const char *kartArchivePostfix(s32 id) {
    switch (id) {
    case MENU_PEACH: return origKartArchivePostfix(0x2D);
    case MENU_DAISY: return origKartArchivePostfix(0x2E);
    case MENU_ROSALINA: return origKartArchivePostfix(0x2F);
    }
    if (validId(id) && rosterById[id].isCustom)
        return rosterById[id].suffix;
    return origKartArchivePostfix(id);
}

// Mii::IsMiiId(CharacterId): no ID is a Mii any more.
static bool isMiiId(s32 id) {
    (void)id;
    return false;
}
REPLACE_FUNCTION(ADDR_IsMiiId, isMiiId);
// Code that checks the Mii range (id - 0x18 <= 0x11 or 0x14) inline: make it
// answer "not a Mii" too. The menu voice code otherwise plays a Mii voice for
// a custom character on an object only set up when a Mii is chosen, and jumps
// to address 0 (seen in Dolphin: A on Test Mario, id 0x1E).
PATCH_IMM16(ADDR_MenuVoice_IsMii1, 1, 0);
PATCH_IMM16(ADDR_MenuVoice_IsMii2, 1, 0);
PATCH_IMM16(ADDR_MenuVoice_IsMii3, 1, 0);
PATCH_IMM16(ADDR_MenuVoice_IsMii4, 1, 0);
PATCH_IMM16(ADDR_AnyPlayerIsMii, 1, 0);
// The race minimap picks a Mii face for ids >= 0x18 (InitSelf) and places it
// as one (CalculatePosition); compare against 0x30 so every id uses its icon.
PATCH_IMM16(ADDR_Race2DMapCharacter_InitSelf_MiiCheck, 0x18, 0x30);
PATCH_IMM16(ADDR_Race2DMapCharacter_CalcPos_MiiCheck, 0x18, 0x30);

// Pages::IsCharacterUnlocked(CharacterId): custom characters are always
// available; vanilla ones keep the game's unlock rules.
typedef bool (*IsCharacterUnlocked_t)(s32 id);
static bool isCharacterUnlocked(s32 id);
REPLACE_FUNCTION_ORIG(ADDR_IsCharacterUnlocked, isCharacterUnlocked, IsCharacterUnlocked_t, origIsCharacterUnlocked);
static bool isCharacterUnlocked(s32 id) {
    if (validId(id) && rosterById[id].isCustom)
        return true;
    return origIsCharacterUnlocked(id);
}

// GetDriverParamEntry(CharacterId): a custom character uses the stats of the
// vanilla character named in its stats_like.
typedef void *(*GetDriverParamEntry_t)(s32 id);
static void *driverParamEntry(s32 id);
REPLACE_FUNCTION_ORIG(ADDR_GetDriverParamEntry, driverParamEntry, GetDriverParamEntry_t, origDriverParamEntry);
static void *driverParamEntry(s32 id) {
    return origDriverParamEntry(validId(id) ? rosterById[id].statsFrom : id);
}

// GetDriverDispEntry(CharacterId): the display table (model setup used by the
// kart and driver in a race) still holds Mii entries for the repurposed ids,
// so a custom character borrows the entry of its stats_like character.
typedef void *(*GetDriverDispEntry_t)(s32 id);
static void *driverDispEntry(s32 id);
REPLACE_FUNCTION_ORIG(ADDR_GetDriverDispEntry, driverDispEntry, GetDriverDispEntry_t, origDriverDispEntry);
static void *driverDispEntry(s32 id) {
    return origDriverDispEntry(validId(id) && rosterById[id].isCustom ? rosterById[id].statsFrom : id);
}
