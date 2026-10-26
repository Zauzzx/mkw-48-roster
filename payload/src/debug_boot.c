// Test builds only (tools/build.py --debug-boot): boot straight into the
// character select screen, the way the game's developer boot arguments do,
// so the layout can be checked without navigating the menus.

#ifdef ROSTER_DEBUG_BOOT
#include "addresses.h"
#include "hooks.h"

typedef s32 (*ExtractAllArgs_t)(const void *extractor);

// SECTION_SINGLE_P_TT_CHANGE_CHARA (0x49): time trial character select.
// -l0: first license. -p292: GameCube controller in port 1 (port << 8 | 0x24).
static const char bootArgs[] = "-s73 -l0 -p292";

static s32 bootIntoCharacterSelect(const void *extractor) {
    char *systemManager = *(char **)ADDR_SystemManager_sInstance;
    *(const char **)(systemManager + 0x98) = bootArgs; // SystemManager::ndevArg
    return ((ExtractAllArgs_t)ADDR_NdevArgsExtractor_ExtractAllArgs)(extractor);
}
PATCH_CALL(ADDR_BootSectionCall, bootIntoCharacterSelect);
#endif
