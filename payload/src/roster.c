// Character ID hooks: make the Mii/biker IDs behave like regular drivers
// (all 24, or the 18 that roster.toml `miis` leaves free).
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
static void patchMiiSites(void);
void roster_patch_tables(void) {
    const char **table = (const char **)ADDR_KartArchivePostfixTable;
    for (u32 i = 0; i < 3; i++)
        menuPostfix[i] = table[0x2D + i];
    for (s32 id = 0; id < ROSTER_MAX; id++)
        if (rosterById[id].isCustom)
            table[id] = rosterById[id].suffix;
    if (rosterMiis)
        patchMiiSites();
}

// Mii::IsMiiId(CharacterId): only the IDs kept for Miis (roster.toml `miis`),
// otherwise none.
static bool isMiiId(s32 id) {
    u32 n = (u32)(id - 0x18);
    return rosterMiis && n <= 0x11 && ((ROSTER_MII_MASK >> n) & 1);
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

// With Miis kept, the checks above must still call the kept IDs Miis. Each
// `li rX, 1` (taken for ids 0x18-0x29/0x2C, with r0 = id - 0x18) branches to a
// stub that sets rX from ROSTER_MII_MASK instead; these sit in leaf and
// tail-calling functions, so the stubs return with `b`. Each `cmpwi rN, 0x18`
// becomes `bl` to a stub that sets cr0 to "greater" for a kept Mii and "less"
// otherwise, saving the two registers it uses.
#define STR_(x) #x
#define STR(x) STR_(x)
// The last instruction of an `li` stub becomes `b site + 4` at boot.
#define MII_LI_STUB(name, reg) \
    #name ":\n\tli " #reg ", " STR(ROSTER_MII_MASK) "\n\tsrw " #reg ", " #reg ", 0\n" \
    "\tclrlwi " #reg ", " #reg ", 31\n\tnop\n"
#define MII_CMP_STUB(name, reg) \
    #name ":\n\tstwu 1, -16(1)\n\tstw 11, 8(1)\n\tmr 11, " #reg "\n\tb mii_cmp\n"
__asm__(".text\n.balign 4\n"
        MII_LI_STUB(mii_li_voice1, 6)
        MII_LI_STUB(mii_li_voice2, 6)
        MII_LI_STUB(mii_li_voice3, 7)
        MII_LI_STUB(mii_li_voice4, 3)
        MII_LI_STUB(mii_li_players, 5)
        MII_CMP_STUB(mii_cmp_r0, 0)
        MII_CMP_STUB(mii_cmp_r3, 3)
        MII_CMP_STUB(mii_cmp_r6, 6)
        MII_CMP_STUB(mii_cmp_r15, 15)
        MII_CMP_STUB(mii_cmp_r25, 25)
        "mii_cmp:\n\tstw 12, 12(1)\n\taddi 11, 11, -0x18\n\tcmplwi 11, 0x11\n\tli 12, -1\n\tbgt 1f\n"
        "\tli 12, " STR(ROSTER_MII_MASK) "\n\tsrw 12, 12, 11\n\trlwinm 12, 12, 1, 30, 30\n\taddi 12, 12, -1\n"
        "1:\tcmpwi 12, 0\n\tlwz 11, 8(1)\n\tlwz 12, 12(1)\n\taddi 1, 1, 16\n\tblr\n");
extern u8 mii_li_voice1[], mii_li_voice2[], mii_li_voice3[], mii_li_voice4[], mii_li_players[];
extern u8 mii_cmp_r0[], mii_cmp_r3[], mii_cmp_r6[], mii_cmp_r15[], mii_cmp_r25[];
// site, stub (+1: bl)
static const u32 miiSites[][2] = {
    {ADDR_MenuVoice_IsMii1, (u32)mii_li_voice1},
    {ADDR_MenuVoice_IsMii2, (u32)mii_li_voice2},
    {ADDR_MenuVoice_IsMii3, (u32)mii_li_voice3},
    {ADDR_MenuVoice_IsMii4, (u32)mii_li_voice4},
    {ADDR_AnyPlayerIsMii, (u32)mii_li_players},
    {ADDR_Race2DMapCharacter_InitSelf_MiiCheck, (u32)mii_cmp_r3 + 1},
    {ADDR_Race2DMapCharacter_CalcPos_MiiCheck, (u32)mii_cmp_r0 + 1},
    {ADDR_RaceResult_Load_MiiCheck, (u32)mii_cmp_r3 + 1},
    {ADDR_RaceResult_FillName_MiiCheck, (u32)mii_cmp_r6 + 1},
    {ADDR_RaceResult_Fill_MiiCheck, (u32)mii_cmp_r3 + 1},
    {ADDR_RaceResultTeam_InitSelf_MiiCheck1, (u32)mii_cmp_r25 + 1},
    {ADDR_RaceResultTeam_InitSelf_MiiCheck2, (u32)mii_cmp_r25 + 1},
    {ADDR_AwardDemoResultItem_MiiCheck1, (u32)mii_cmp_r3 + 1},
    {ADDR_AwardDemoResultItem_MiiCheck2, (u32)mii_cmp_r3 + 1},
    {ADDR_AwardsMgr_LoadPlayers_MiiCheck1, (u32)mii_cmp_r15 + 1},
    {ADDR_AwardsMgr_LoadPlayers_MiiCheck2, (u32)mii_cmp_r15 + 1},
};
static u32 branchTo(u32 from, u32 to) {
    return 0x48000000 | ((to - from) & 0x03FFFFFC);
}
static void patchMiiSites(void) {
    for (u32 i = 0; i < sizeof(miiSites) / sizeof(miiSites[0]); i++) {
        u32 at = miiSites[i][0], to = miiSites[i][1];
        if (!(to & 1))
            hook_write32(to + 12, branchTo(to + 12, at + 4));
        hook_write32(at, branchTo(at, to) | (to & 1));
    }
}

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
    return origDriverParamEntry(validId(id) && rosterById[id].isCustom ? rosterById[id].statsFrom : id);
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
