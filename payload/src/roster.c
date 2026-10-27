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
static const char *menuPostfix[3]; // vanilla "pc_menu", "ds_menu", "rs_menu"
static const char *kartArchivePostfix(s32 id) {
    if (id >= MENU_PEACH && id <= MENU_ROSALINA)
        return menuPostfix[id - MENU_PEACH];
    if (validId(id) && rosterById[id].isCustom)
        return rosterById[id].suffix;
    return origKartArchivePostfix(id);
}

// The race and kart-select archive loaders (ArchiveMgr::LoadKartArchive,
// LoadKartArchiveHolder2, LoadKartArchiveAsync, GetMenuKartBRRES) read the
// postfix table directly instead of calling GetKartArchivePostfix, so a custom
// character loaded the Mii files (ma_kart-ma_mii_m.szs: white kart, Mii body).
// Point the custom IDs' entries at their suffixes.
void roster_patch_tables(void) {
    const char **table = (const char **)ADDR_KartArchivePostfixTable;
    for (u32 i = 0; i < 3; i++)
        menuPostfix[i] = table[0x2D + i];
    for (s32 id = 0; id < ROSTER_MAX; id++)
        if (rosterById[id].isCustom)
            table[id] = rosterById[id].suffix;
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
// The same `cmpwi id, 0x18` choosing a Mii face or name: the race results
// (leaderboard), team results, and the cup ceremony.
PATCH_IMM16(ADDR_RaceResult_Load_MiiCheck, 0x18, 0x30);
PATCH_IMM16(ADDR_RaceResult_FillName_MiiCheck, 0x18, 0x30);
PATCH_IMM16(ADDR_RaceResult_Fill_MiiCheck, 0x18, 0x30);
PATCH_IMM16(ADDR_RaceResultTeam_InitSelf_MiiCheck1, 0x18, 0x30);
PATCH_IMM16(ADDR_RaceResultTeam_InitSelf_MiiCheck2, 0x18, 0x30);
PATCH_IMM16(ADDR_AwardDemoResultItem_MiiCheck1, 0x18, 0x30);
PATCH_IMM16(ADDR_AwardDemoResultItem_MiiCheck2, 0x18, 0x30);
PATCH_IMM16(ADDR_AwardsMgr_LoadPlayers_MiiCheck1, 0x18, 0x30);
PATCH_IMM16(ADDR_AwardsMgr_LoadPlayers_MiiCheck2, 0x18, 0x30);

// RKSYS::LicenseCompletion::IsCompleted(bit): the one getter behind every
// unlock (vehicle classes, cups per engine class and Mirror, characters,
// vehicles). With unlock_all, everything reads as unlocked; the save is not
// written.
typedef bool (*IsCompleted_t)(void *completion, s32 bit);
static bool isCompleted(void *completion, s32 bit);
REPLACE_FUNCTION_ORIG(ADDR_LicenseCompletion_IsCompleted, isCompleted, IsCompleted_t, origIsCompleted);
static bool isCompleted(void *completion, s32 bit) {
    return rosterUnlockAll || origIsCompleted(completion, bit);
}

// Pages::IsCharacterUnlocked(CharacterId): custom characters are always
// available; vanilla ones keep the game's unlock rules unless unlock_all is on.
typedef bool (*IsCharacterUnlocked_t)(s32 id);
static bool isCharacterUnlocked(s32 id);
REPLACE_FUNCTION_ORIG(ADDR_IsCharacterUnlocked, isCharacterUnlocked, IsCharacterUnlocked_t, origIsCharacterUnlocked);
static bool isCharacterUnlocked(s32 id) {
    if (rosterUnlockAll || (validId(id) && rosterById[id].isCustom))
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
