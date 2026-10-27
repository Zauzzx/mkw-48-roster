// The character select screen with up to 48 buttons.
//
// CtrlMenuCharacterSelect::Load allocates the buttons and calls LoadButton
// for each. We make Load create rosterCount buttons, none of them Mii
// buttons, and replace LoadButton so button i shows character
// rosterButtonToId[i], placed by record "Button<i>" of our own
// button/ctrl/CharacterSelect48.brctr (written by tools/pack_ui.py). Cursor
// movement follows the buttons' screen positions, so rows need no extra code.
//
// Build with --vanilla-select to leave the vanilla screen alone (e.g. before
// the UI files from tools/pack_ui.py are installed).

#ifndef ROSTER_VANILLA_SELECT
#include "addresses.h"
#include "hooks.h"
#include "roster_table.h"

// CtrlMenuCharacterSelect fields
#define CTRL_SELECTED 0x174   // CharacterId per hud slot
#define CTRL_BUTTONS 0x1B0    // ButtonDriver array
#define CTRL_ON_CLICK 0x1B8   // handler objects for driver (non-Mii) buttons
#define CTRL_ON_SELECT 0x1CC
#define CTRL_ON_DESELECT 0x1E0
// ButtonDriver fields
#define BUTTON_SIZE 0x260
#define BUTTON_CHARACTER 0x240
#define BUTTON_IS_MII 0x254

#define PAGE_CHARACTER_SELECT 0x6B

typedef s32 (*snprintf_t)(char *buf, u32 size, const char *fmt, ...);
typedef u8 (*GetLocalPlayerCount_t)(void);
typedef void (*PushButtonLoad_t)(void *button, const char *folder, const char *ctr, const char *variant,
                                 u32 playerBitfield, bool r8, bool inaccessible);
typedef void (*SetPaneVisibility_t)(void *ctrl, const char *pane, bool visible);
typedef void (*SetPicturePane_t)(void *ctrl, const char *target, const char *source);
typedef void (*SetHandler2_t)(void *button, void *handler);
typedef void (*SetHandler3_t)(void *button, void *handler, u32 r5);
typedef void (*SetButtonU32_t)(void *button, u32 value);
typedef void (*SetButtonColours_t)(void *button, u32 hudSlot, u32 alpha);
typedef void *(*GetPageById_t)(u32 pageId);
typedef void (*OnButtonDriverSelect_t)(void *page, void *button, s32 id, u8 hudSlot);
typedef const char *(*GetCharacterIconPaneName_t)(s32 id);
typedef bool (*IsCharacterUnlocked_t)(s32 id);

#define CALL(type, name) ((type)ADDR_##name)

// Load: isMii argument to LoadButton -> "li r5, 0".
PATCH_WRITE32(ADDR_CharacterSelectLoad_IsMiiArg, 0x38A00000);

static const char *const iconPanes[] = {"chara", "chara_shadow", "chara_light_01", "chara_light_02", "chara_c_down"};

static bool buttonUnlocked(s32 i) {
    return i < (s32)rosterCount && CALL(IsCharacterUnlocked_t, IsCharacterUnlocked)(rosterButtonToId[i]);
}

static void loadButton(u8 *self, s32 i, bool isMii) {
    (void)isMii;
    u8 players = CALL(GetLocalPlayerCount_t, GetLocalPlayerCount)();
    u8 *button = *(u8 **)(self + CTRL_BUTTONS) + i * BUTTON_SIZE;

    char variant[16];
    CALL(snprintf_t, snprintf)(variant, sizeof(variant), "Button%d", i);
    CALL(PushButtonLoad_t, PushButton_Load)(button, "button", "CharacterSelect48", variant, 0x1F, true, false);

    bool unlocked = buttonUnlocked(i);
    s32 id = unlocked ? rosterButtonToId[i] : -1;
    *(s32 *)(button + BUTTON_CHARACTER) = id;
    *(u8 *)(button + BUTTON_IS_MII) = 0;
    CALL(SetPaneVisibility_t, LayoutUIControl_SetPaneVisibility)(button, "ok_null", false);

    const char *icon = unlocked ? CALL(GetCharacterIconPaneName_t, GetCharacterIconPaneName)(id) : NULL;
    for (u32 p = 0; p < sizeof(iconPanes) / sizeof(iconPanes[0]); p++)
        CALL(SetPicturePane_t, LayoutUIControl_SetPicturePane)(button, iconPanes[p], icon ? icon : "cha_26_hatena");
    if (icon) {
        CALL(SetHandler3_t, PushButton_SetOnClickHandler)(button, self + CTRL_ON_CLICK, 0);
        CALL(SetHandler2_t, PushButton_SetOnSelectHandler)(button, self + CTRL_ON_SELECT);
        CALL(SetHandler2_t, PushButton_SetOnDeSelectHandler)(button, self + CTRL_ON_DESELECT);
    } else {
        CALL(SetButtonU32_t, PushButton_SetPlayerBitfield)(button, 0); // locked: nobody can pick it
    }

    // The cursor starts on the first available character.
    s32 first = 0;
    while (first < (s32)rosterCount - 1 && !buttonUnlocked(first))
        first++;
    if (i != first)
        return;
    void *page = CALL(GetPageById_t, CharacterSelect_GetPageById)(PAGE_CHARACTER_SELECT);
    for (u8 p = 0; p < players; p++) {
        CALL(SetButtonU32_t, PushButton_SelectInitial)(button, p);
        *(s32 *)(self + CTRL_SELECTED + 4 * p) = id;
        CALL(SetButtonColours_t, ButtonDriver_SetButtonColours)(button, p, 0xB4);
        CALL(OnButtonDriverSelect_t, CharacterSelect_OnButtonDriverSelect)(page, button, id, p);
    }
}
REPLACE_FUNCTION(ADDR_CtrlMenuCharacterSelect_LoadButton, loadButton);

// GetCharacterIconPaneName: custom characters use pane "cha_x_<suffix>",
// which tools/pack_ui.py adds to character_64x64_common.brlyt.
static const char *iconPaneName(s32 id);
REPLACE_FUNCTION_ORIG(ADDR_GetCharacterIconPaneName, iconPaneName, GetCharacterIconPaneName_t, origIconPaneName);
static const char *iconPaneName(s32 id) {
    if (id >= 0 && id < ROSTER_MAX && rosterById[id].isCustom)
        return rosterById[id].iconPane;
    return origIconPaneName(id);
}

// The 3D previews: DriverModelControl::SetModelPositionOnAnim places pane
// "model_null" from a table built into the game, so the placement records in
// CharacterSelectModel.brctr (written by tools/pack_ui.py) only reach the
// control itself. For this page's previews, put the pane at the record's
// position and scale instead.
#define PAGE_MODELS 0x914      // DriverModelControl array
#define MODEL_SIZE 0x188
#define CONTROL_BASE_POS 0x04  // float x, y, z, then scale x, y: from the record
#define CONTROL_LAYOUT 0xA8
#define PANE_TRANSLATE 0x2C
#define PANE_SCALE 0x44

typedef void (*SetModelPosition_t)(u8 *self);
typedef u8 *(*GetPaneByName_t)(void *layout, const char *name);

static void setModelPosition(u8 *self);
REPLACE_FUNCTION_ORIG(ADDR_DriverModelControl_SetModelPositionOnAnim, setModelPosition, SetModelPosition_t,
                      origSetModelPosition);
static void setModelPosition(u8 *self) {
    origSetModelPosition(self);
    u8 *page = CALL(GetPageById_t, CharacterSelect_GetPageById)(PAGE_CHARACTER_SELECT);
    if (!page)
        return;
    u8 *models = *(u8 **)(page + PAGE_MODELS);
    u8 players = CALL(GetLocalPlayerCount_t, GetLocalPlayerCount)();
    if (!models || self < models || self >= models + players * MODEL_SIZE)
        return;
    u8 *pane = CALL(GetPaneByName_t, Layout_GetPaneByName)(self + CONTROL_LAYOUT, "model_null");
    if (!pane)
        return;
    float *base = (float *)(self + CONTROL_BASE_POS);
    float *t = (float *)(pane + PANE_TRANSLATE), *s = (float *)(pane + PANE_SCALE);
    t[0] = base[0];
    t[1] = base[1];
    s[0] = base[3];
    s[1] = base[4];
}

void roster_after_hooks(void) {
    // Load: "add r30, r0, r3" (button count) -> "li r30, rosterCount".
    hook_write32(ADDR_CharacterSelectLoad_ButtonCount, 0x3BC00000 | rosterCount);
}
#else
void roster_after_hooks(void) {}
#endif
