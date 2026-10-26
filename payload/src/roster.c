// Character ID hooks: make the 24 Mii/biker IDs behave like regular drivers.
// Function signatures follow Pulsar's GameSource headers; addresses are
// filled in per region by addresses/<game id>.toml.

#include "addresses.h"
#include "hooks.h"
#include "roster_table.h"

static bool validId(s32 id) {
    return id >= 0 && id < ROSTER_MAX;
}

// ArchiveMgr::GetKartArchivePostfix(CharacterId): the "mr" in st_kart-mr.szs.
static const char *kartArchivePostfix(s32 id) {
    return validId(id) ? rosterById[id].suffix : rosterById[0].suffix;
}
REPLACE_FUNCTION(ADDR_GetKartArchivePostfix, kartArchivePostfix);

// Mii::IsMiiId(CharacterId): no ID is a Mii any more.
static bool isMiiId(s32 id) {
    (void)id;
    return false;
}
REPLACE_FUNCTION(ADDR_IsMiiId, isMiiId);

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
