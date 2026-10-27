// Race HUD speedometer, ported from Pulsar's CtrlRaceSpeedo
// (github.com/MelgMKW/Pulsar, PulsarEngine/UI/CtrlRaceBase/Speedometer.cpp,
// MIT). One control per local player shows the kart's speed with picture
// digits: layout "PULSpeedo" in Race.szs/game_image, added by
// tools/pack_assets.py together with the digit textures (which the
// Speedometer Recolor Pack's colours replace).
//
// The control is a CtrlRaceBase with Init and OnUpdate overridden. CtrlRaceBase
// has no constructor of its own (it's inlined), so we construct a
// LayoutUIControl and give it a copy of CtrlRaceBase's vtable with our two
// functions in it.

#include "addresses.h"
#include "hooks.h"
#include "roster_table.h"

#define CTRL_SIZE 0x198      // sizeof(CtrlRaceBase)
#define CTRL_ANIMATOR 0x98   // UIAnimator
#define CTRL_HUD_SLOT 0x190
#define VTABLE_WORDS (0x50 / 4)
#define VT_DTOR 2
#define VT_INIT 3
#define VT_ON_UPDATE 7

// Kart data, from Pulsar's GameSource headers
#define KARTMGR_PLAYERS 0x20
#define PLAYER_BODY 0x24     // pointers (0x1C) + kartBody (0x8)
#define PLAYER_MOVEMENT 0x44 // pointers (0x1C) + kartMovement (0x28)
#define BODY_PHYSICS_HOLDER 0x90
#define HOLDER_PHYSICS 0x4
#define PHYSICS_SPEED2 0xB0
#define PHYSICS_SPEED3 0xC8
#define PHYSICS_ENGINE_SPEED 0x14C
#define MOVEMENT_SPEED_LIMIT 0x2C
#define RACEDATA_LOCAL_PLAYERS 0x26 // racesScenario (0x20) + localPlayerCount (0x6)

typedef void (*OSReport_t)(const char *fmt, ...);
typedef s32 (*snprintf_t)(char *buf, u32 size, const char *fmt, ...);
typedef void (*InitControlGroup_t)(void *page, u32 count);
typedef void (*AddControl_t)(void *page, u8 idx, void *control, u32 zIdx);
typedef void *(*New_t)(u32 size);
typedef void (*Method_t)(void *self);
typedef void (*LoaderCtor_t)(void *loader, void *control);
typedef void (*LoaderDtor_t)(void *loader, s32 deleteFlag);
typedef void (*LoaderLoad_t)(void *loader, const char *folder, const char *ctr, const char *variant,
                             const char **anims);
typedef void *(*GetGroup_t)(void *animator, u32 id);
typedef void (*PlayAtFrame_t)(void *group, u32 anim, float frame);
typedef void (*HudSlotColorEnable_t)(void *self, const char *pane, bool enable);
typedef u8 (*GetPlayerId_t)(void *self);
typedef float (*PSVECMag_t)(const float *v);

#define CALL(type, name) ((type)ADDR_##name)

// Built for size: the payload has to fit the 0x2460-byte boot code area.
#define SMALL __attribute__((minsize))

static u32 vtable[VTABLE_WORDS];

// Frames of the digit animation: 0-9, then empty and the dot.
#define EMPTY 10
#define DOT 11

SMALL static void animate(u8 *self, const u32 *frames) {
    for (u32 i = 0; i < 7; i++) {
        void *group = CALL(GetGroup_t, UIAnimator_GetAnimationGroupById)(self + CTRL_ANIMATOR, i);
        CALL(PlayAtFrame_t, AnimationGroup_PlayAtFrameAndDisable)(group, 0, frames ? (float)frames[i] : 0.0f);
    }
}

SMALL static void speedoInit(u8 *self) {
    static const char *const panes[] = {"speed0", "speed1", "speed2", "speed3", "speed4", "speed5", "speed6", "kmh"};
    for (u32 i = 0; i < sizeof(panes) / sizeof(panes[0]); i++)
        CALL(HudSlotColorEnable_t, CtrlRaceBase_HudSlotColorEnable)(self, panes[i], true);
    CALL(Method_t, LayoutUIControl_Init)(self);
}

SMALL static void speedoUpdate(u8 *self) {
    CALL(Method_t, CtrlRaceBase_UpdatePausePosition)(self);
    u8 id = CALL(GetPlayerId_t, CtrlRaceBase_GetPlayerId)(self);
    u8 *mgr = *(u8 **)ADDR_KartManager_sInstance;
    u8 *player = (*(u8 ***)(mgr + KARTMGR_PLAYERS))[id];
    u8 *holder = *(u8 **)(*(u8 **)(player + PLAYER_BODY) + BODY_PHYSICS_HOLDER);
    u8 *physics = *(u8 **)(holder + HOLDER_PHYSICS);
    const float *a = (float *)(physics + PHYSICS_ENGINE_SPEED), *b = (float *)(physics + PHYSICS_SPEED2),
                *c = (float *)(physics + PHYSICS_SPEED3);
    float sum[3] = {a[0] + b[0] + c[0], a[1] + b[1] + c[1], a[2] + b[2] + c[2]};
    float speed = CALL(PSVECMag_t, PSVECMag)(sum);
    float cap = *(float *)(*(u8 **)(player + PLAYER_MOVEMENT) + MOVEMENT_SPEED_LIMIT);
    if (speed > cap)
        speed = cap;
    if (!(speed >= 0.0f)) // NaN
        speed = 0.0f;

    u32 decimals = rosterSpeedoDecimals;
    u32 v = (u32)(s32)(speed * 1000.0f);
    u32 f[7] = {v % 1000000 / 100000, v % 100000 / 10000, v % 10000 / 1000, decimals >= 1 ? DOT : EMPTY,
                decimals >= 1 ? v % 1000 / 100 : EMPTY, decimals >= 2 ? v % 100 / 10 : EMPTY,
                decimals >= 3 ? v % 10 : EMPTY};
    // Left-align: drop leading zeros (keep one digit before the dot).
    u32 shift = v < 10000 ? 2 : v < 100000 ? 1 : 0;
    for (u32 i = 0; i < 7; i++)
        f[i] = i + shift < 7 ? f[i + shift] : EMPTY;
    animate(self, f);
}

SMALL static void speedoCreate(void *page, u32 index, u32 count) {
    u32 type = count == 3 ? 4 : count;
    for (u32 i = 0; i < count; i++) {
        u8 *self = CALL(New_t, operator_new)(CTRL_SIZE);
        for (u32 k = 0; k < CTRL_SIZE; k++)
            self[k] = 0;
        CALL(Method_t, LayoutUIControl_ctor)(self);
        *(u32 **)self = vtable;
        CALL(AddControl_t, Page_AddControl)(page, index + i, self, 0);

        char variant[16];
        u32 pos = count == 1 && rosterSpeedoRight ? 1 : i;
        CALL(snprintf_t, snprintf)(variant, sizeof(variant), "Speedo_%d_%d", (int)type, (int)pos);
        self[CTRL_HUD_SLOT] = i;
        static const char *anims[] = {"Hundreds", "Hundreds", NULL, "Tens", "Tens", NULL, "Units", "Units", NULL,
                                      "Dot", "Dot", NULL, "Tenths", "Tenths", NULL, "Hundredths", "Hundredths",
                                      NULL, "Thousandths", "Thousandths", NULL, NULL};
        __attribute__((aligned(4))) u8 loader[0x28];
        CALL(LoaderCtor_t, ControlLoader_ctor)(loader, self);
        CALL(LoaderLoad_t, ControlLoader_Load)(loader, "game_image", "PULSpeedo", variant, anims);
        CALL(LoaderDtor_t, ControlLoader_dtor)(loader, -1);
        animate(self, NULL);
    }
}

// Replaces the `bl Page::InitControlGroup` in RaceHUD::OnInit: make room for
// the speedometers after the HUD's own controls, then add them.
SMALL static void buildRaceControls(void *page, u32 baseCount) {
    u32 count = 0;
    u8 *racedata = *(u8 **)ADDR_Racedata_sInstance;
    if (racedata)
        count = racedata[RACEDATA_LOCAL_PLAYERS];
    if (count > 4)
        count = 4;
    CALL(InitControlGroup_t, Page_InitControlGroup)(page, baseCount + count);
    if (count)
        speedoCreate(page, baseCount, count);
}

// CtrlRaceBase's vtable address, read from the `lis rX, hi` / `addi rY, rX, lo`
// at the top of its destructor.
SMALL static u32 *findVtable(void) {
    const u32 *code = (const u32 *)ADDR_CtrlRaceBase_dtor;
    for (u32 i = 0; i < 16; i++) {
        u32 lis = code[i];
        if (lis >> 26 != 15 || (lis >> 16 & 31) != 0)
            continue;
        u32 reg = lis >> 21 & 31;
        for (u32 j = i + 1; j < i + 4 && j < 16; j++)
            if (code[j] >> 26 == 14 && (code[j] >> 16 & 31) == reg)
                return (u32 *)((lis << 16) + (s32)(s16)code[j]);
        return NULL;
    }
    return NULL;
}

SMALL void speedo_setup(void) {
    OSReport_t report = (OSReport_t)ADDR_OSReport;
    if (!rosterSpeedo)
        return;
    u32 *base = findVtable();
    u32 call = *(u32 *)ADDR_RaceHUD_InitControlGroupCall;
    u32 expected = 0x48000001 | ((ADDR_Page_InitControlGroup - ADDR_RaceHUD_InitControlGroupCall) & 0x03FFFFFC);
    // The vtable's destructor slot must point back at the destructor we read it from.
    if (!base || base[VT_DTOR] != ADDR_CtrlRaceBase_dtor || call != expected) {
        report("[mkw-48-roster] speedometer off: vtable %08x, call %08x\n", (u32)base, call);
        return;
    }
    for (u32 i = 0; i < VTABLE_WORDS; i++)
        vtable[i] = base[i];
    vtable[VT_INIT] = (u32)speedoInit;
    vtable[VT_ON_UPDATE] = (u32)speedoUpdate;
    hook_write32(ADDR_RaceHUD_InitControlGroupCall,
                 0x48000001 | (((u32)buildRaceControls - ADDR_RaceHUD_InitControlGroupCall) & 0x03FFFFFC));
    report("[mkw-48-roster] speedometer on (CtrlRaceBase vtable %08x)\n", (u32)base);
}
