# Character select screen: reverse-engineering notes (USA, RMCE01)

How the vanilla character select screen builds, lays out and reacts to its
driver buttons. It is written for the replacement that creates up to 48
`ButtonDriver` buttons laid out in rows.

All addresses are USA runtime addresses, with StaticR.rel linked at file base
`8050BF60` (.text `8050C034`, .bss `809B8F20`). PAL addresses come from
Pulsar's headers and were mapped with its `versions.txt`. The pseudo-C below
is a paraphrase of behaviour, not decompiled game code. Names follow Pulsar's
GameSource headers where they exist.

## Objects and fields

`Pages::CharacterSelect` (page 0x6B, 0x918 bytes):

| Offset | Field |
| --- | --- |
| +0x044 | MiiGroup of the local players' Miis |
| +0x08 | non-zero when this is a multiplayer / online-style flow (checked before the Mii name logic) |
| +0x35C | per hud slot: "player has a Mii selected" flags |
| +0x654 | next control slot index (incremented by every `Page::AddControl`) |
| +0x6C4 | embedded `CtrlMenuCharacterSelect` (0x230 bytes) |
| +0x8F4 | per hud slot: `Mii*` for that player |
| +0x904 | local player count (from `GetLocalPlayerCount`) |
| +0x90C | timer (CountDown*), cleared in OnInit |
| +0x910 | `CharaName[playerCount]`, 0x178 each (name plates) |
| +0x914 | `DriverModelControl[playerCount]`, 0x188 each (3D previews) |

`CtrlMenuCharacterSelect` (LayoutUIControl, 0x230 bytes):

| Offset | Field |
| --- | --- |
| +0x174 | `CharacterId selected[hudSlot]`, u32 per hud slot (written on select) |
| +0x184 | timer, cleared by Load |
| +0x188 | local player count |
| +0x18C | `bool unlocked[3][8]`: weight-major grid, 24 bytes (light, medium, heavy × 8) |
| +0x1A4 | Mii flag A (= IsCharacterUnlocked(0x18)) |
| +0x1A5 | Mii flag B (= IsCharacterUnlocked(0x1A)) |
| +0x1A8 | "half columns" count H: buttons per row = 2·H. Value 2, 3 or 4 (see Load) |
| +0x1AC | number of buttons created |
| +0x1B0 | `ButtonDriver*` array (stride 0x260) |
| +0x1B4 | last selected Mii button |
| +0x1B8 / +0x1CC / +0x1E0 | click / select / deselect handlers for driver buttons (→ OnButtonClick 807DD56C, OnButtonSelect 807DD664, OnButtonDeselect 807DD744) |
| +0x1F4 / +0x208 / +0x21C | the same three handlers for Mii buttons (→ OnMiiButtonClick 807DD7F0, OnMiiButtonSelect 807DD93C, OnMiiButtonDeselect) |

`CtrlMenuCharacterSelect::ButtonDriver` (a `PushButton`, 0x260 bytes):

| Offset | Field |
| --- | --- |
| +0x240 | `buttonId`; for driver buttons this holds the **CharacterId** |
| +0x244 | localPlayerBitfield (PushButton) |
| +0x248 / +0x24C | panes looked up by PushButton::Load |
| +0x254 | u8: 1 if this is a Mii button |
| +0x258 | float written in InitSelf (a constant loaded from 808A3168) |
| +0x25C | black_base pane |

Constructor 807DC778, destructor 807DC7B4, ButtonDriver::InitSelf 807DDD80,
SetButtonColours 807DE0A0, ResetButtonColours 807DDE6C.

## Where the controls get built

`Pages::CharacterSelect::OnInit` (PAL 8083D55C, USA **80822AFC**):
- Clears the timer and stores `GetLocalPlayerCount()` into +0x904.
- Fetches or loads each local player's Mii into +0x8F4. Offline it uses
  `MiiGroup::GetMii`; it falls back to LoadOfficialMii / LoadDefaultMii and
  copies into the other group.
- Allocates `CharaName[n]` (`new[]` 0x178 each → +0x910) and
  `DriverModelControl[n]` (0x188 each → +0x914) with `__construct_new_array`.
- Calls `Pages::Menu::OnInit` (8081ECA4). That ends up calling
  `CreateControl(i)` for each control the page declares.

`Pages::CharacterSelect::CreateExternalControl` (**80822E1C**) just returns
NULL. The real work is in `CreateControl(u32 id)` (**80822E24**), which runs
with n = player count:
- `id < n`: `Page::AddControl(slot++, &models[id])`, then
  `DriverModelControl::Load(models[id], "CharacterSelectModel", id)`
  (806363F8). This is the 3D preview, placed by `model/ctrl/CharacterSelectModel.brctr`
  variants 1P_1Div, 1P_2Div, … .
- `n <= id < 2n`: name plate `id-n`. It picks the variant
  "CharacterSelectName", "CharacterSelectName%dP2" or "CharacterSelectName%dP4"
  by player count, `AddControl`s it, and loads it with ControlLoader from
  `control/CharacterSelectName.brctr`. For more than 2 players it writes a
  different float at +0x7C.
- `id == 2n`: `AddControl(slot++, &ctrlMenuCharSelect)`, then
  **`CtrlMenuCharacterSelect::Load(this+0x6C4, playerCount)`** (807DC518).

## CtrlMenuCharacterSelect::Load: USA 807DC518 (PAL 807E25A8)

```c
void Load(CtrlMenuCharacterSelect *self, u32 playerCount) {
    self->timer = 0;                                         // +0x184
    // 1. unlock grid, weight-major, 3 x 8, from the 24-entry button table
    //    buttonIdToCharacterId (808A3108)
    for (w = 0; w < 3; w++) for (i = 0; i < 8; i++)
        self->unlocked[w][i] = IsCharacterUnlocked(table[w*8 + i]);   // 8080A274
    self->miiA = IsCharacterUnlocked(0x18);                  // +0x1A4
    self->miiB = IsCharacterUnlocked(0x1A);                  // +0x1A5

    // 2. how wide each row is: H = ceil(maxUnlockedInAnyWeight / 2)
    m = max(count(weight 0), count(weight 1), count(weight 2));   // GetUnlockedCharacterCountByWeight
    self->H = (m + 1) / 2;                                   // +0x1A8
    if (GetUnlockedCharacterCountByWeight(3) != 0)          // any Mii unlocked
        self->H = clamp(self->H, 3, 4);

    // 3. position the whole control
    ControlLoader l(self);
    l.Load("control", "CharacterSelectNULL",
           playerCount > 2 ? "CharacterSelectNULLCenter" : "CharacterSelectNULL", 0);

    // 4. allocate buttons: 3 weight rows of up to 2H each, plus the Mii buttons
    n = self->H * 6 + GetUnlockedCharacterCountByWeight(3);  // +0x1AC
    self->buttons = new ButtonDriver[n];                    // new[] n*0x260 (+0x10 header),
                                                             // __construct_new_array(ct 807DC778, dt 807DC7B4)
    self->InitControlGroup(n);                               // UIControl::InitControlGroup 8060BE48
    self->playerCount = GetLocalPlayerCount();               // +0x188
    for (i = 0; i < n; i++) {
        self->AddControl(i, &self->buttons[i]);              // UIControl::AddControl 8060BE58
        LoadButton(self, i, /*isMii=*/ i >= self->H * 6);
        for (p = 0; p < playerCount; p++) self->buttons[i].ResetButtonColours(p);
    }
}
```

Baked-in sizes:
- The unlock grid is 3 × 8 (loop bounds 3 and 8). The array holds 24 + 2 bytes.
- The button count is `6·H + miiCount` (6 = 3 weights × 2 halves). With
  everything unlocked that's 8 per weight → H = 4 → 24 driver buttons + 2 Mii
  buttons = 26, matching `unlockedCharactersCount = 0x1A`.
- H is clamped to [3,4] whenever a Mii is unlocked. With few unlocks and no
  Mii button, H can be 2. Example: a fresh-ish save with 4 per weight gives
  H = 2, 12 buttons, layout `CharacterSelect2_*`. That's what the debug-boot
  screenshot shows.

## CtrlMenuCharacterSelect::LoadButton: USA 807DC898 (PAL 807E2928)

```c
void LoadButton(CtrlMenuCharacterSelect *self, int i, bool isMii) {
    players = GetLocalPlayerCount();
    rowLen  = 2 * self->H;
    char btn[16], ctr[32];
    snprintf(btn, 16, "Button%d", i % rowLen);
    if (players == 1 || !isMii)
        snprintf(ctr, 32, "CharacterSelect%d_%d", self->H, i / rowLen);
    else
        snprintf(ctr, 32, "CharacterSelect%d_%d_Mii", self->H, i / rowLen);
    // => BRCTR file button/ctrl/CharacterSelect<H>_<row>.brctr, record "Button<col>"
    ButtonDriver *b = &self->buttons[i];
    PushButton::Load(b, "button", ctr, btn, /*playerBitfield*/ 0x1F,
                     /*r8*/ isMii == 0, /*inaccessible*/ false);       // 805B5874
    b->characterId = GetCorrectButtonDriverId(self, i / rowLen, i);   // +0x240
    b->isMii = isMii;                                                 // +0x254
    iconPane = GetCharacterIconPaneName(b->characterId);              // 8083BE80
    if (players == 1 || !b->isMii) SetPaneVisibility(b, "ok_null", false);
    else hide "ok_null_1p" .. "ok_null_4p";
    if (iconPane) {
        for pane in {"chara","chara_shadow","chara_light_01","chara_light_02","chara_c_down"}:
            SetPicturePane(b, pane, iconPane);                        // 8060CCD0
        if (isMii) set handlers +0x1F4/+0x208/+0x21C (Mii click/select/deselect)
        else       set handlers +0x1B8/+0x1CC/+0x1E0
                   // SetOnClickHandler 805B5E24, SetOnSelectHandler 805B5E3C,
                   // SetOnDeSelectHandler 805B5E44
    } else {   // locked: GetCorrectButtonDriverId returned -1
        all five panes -> "cha_26_hatena" (the "?" icon);
        PushButton::SetPlayerBitfield(b, 0);   // nobody can select it
    }
    if (i == 0)  // initial cursor for every player
        for (p = 0; p < players; p++) {
            PushButton::SelectInitial(b, p);   // 805B5E4C
            self->selected[p] = b->characterId;
            b->SetButtonColours(p, 0xB4);
            Pages::CharacterSelect::GetPageById(0x6B)->OnButtonDriverSelect(b, b->characterId, p);
        }
}
```

The row index passed to `GetCorrectButtonDriverId` is `i / rowLen`. It doubles
as the **weight** (0 light, 1 medium, 2 heavy, 3 = Mii row), so one screen row
is one weight class. That's the vanilla "columns per weight" look, since H
is at most 4 and 2H = 8 buttons fill one weight.

PushButton::Load (805B5874) stores the player bitfield at +0x244, then runs a
ControlLoader with ("button", ctrName, variant). The BRCTR placement record
named `variant` sets the button's position and scale (format below). It then
looks up panes, sets up a ControlManipulator for the enabled hud slots and
registers it with the page's ControlsManipulatorManager. That's how the cursor
moves between buttons: the manipulator uses the buttons' **screen
positions**, so a new layout only needs new BRCTR placements, not new
navigation code.

## GetCorrectButtonDriverId: USA 807DDC1C (PAL 807E3CAC)

Maps (row/weight, flat index) to a CharacterId, skipping locked characters so
unlocked ones pack to the left.

```c
CharacterId GetCorrectButtonDriverId(self, int weight, int i) {
    if (weight == 3) {                       // Mii row
        if (!IsCharacterUnlocked(0x1E)) i++; // skip outfit A if locked
        return 0x1E + 2 * (i % self->H);     // 0x1E/0x20: medium Mii outfits, male
    }
    rowLen = 2 * self->H;
    col = i % rowLen;
    if (col < rowLen && self->unlocked[weight][col])
        return table[weight*8 + col];        // 808A3108
    // otherwise: count how many locked entries come before col, and walk
    // the rest of the 8-entry weight row to find the n-th unlocked one
    ...
    return -1;                               // nothing left: locked "?" button
}
```

Baked in: the weight row length 8 (the `8 - rowLen` loop and the `*8`/`<<5`
table stride), the Mii base ID 0x1E, the Mii stride 2.

## GetUnlockedCharacterCountByWeight: USA 807DDB5C (PAL 807E3BEC)

`weight` 0–2: counts the 8 bools at `unlocked[weight][0..7]` (fully unrolled,
8 loads). `weight` 3: counts the two Mii flags at +0x1A4/+0x1A5.

## GetUnlockedStatus: USA 807DC80C (PAL 807E289C)

This is the same 3×8 + 2 Mii-flag fill as step 1 of Load, as a separate
function. Pulsar notes it is also inlined.

## InitSelf: USA 807DCC88 (PAL 807E2D18)

- For each of the 12 racedata player slots (2 × 6 unrolled; struct 0xF0 at
  `*(809B8F68)`+…), if +0xC28 is set, writes -1 to +0xC24, i.e. clears the
  previous character.
- For every button `i < count(+0x1AC)`:
  - ResetButtonColours for each player.
  - Writes the float at +0x258.
  - Hides the "ok_null" pane (single player or non-Mii) or the
    "ok_null_1p".."ok_null_4p" panes (multiplayer Mii).
- Initial cursor:
  - For every button i and each player p, it compares `button.characterId`
    with the character the player had last time. That's
    `SectionParams(*(809BD508))->+0x98 …+0x12C`, per player stride 4.
  - It also accepts the case where both are Mii IDs. It uses the helpers at
    8080A27C (`id-0x18` range check, i.e. "is a Mii id") and 8080A2B0.
  - On a match it calls `PushButton::SelectInitial(p)`, stores
    `selected[p]`, `SetButtonColours(p, 0xB4)` and the page's
    `OnButtonDriverSelect`.
- No sizes are baked in except the 6-iteration unrolled player loop (12 slots)
  and the use of +0x1AC as the button count.

## OnButtonSelect: USA 807DD664 (PAL 807E36F4)

```c
void OnButtonSelect(self, ButtonDriver *b, u32 hud) {
    self->selected[hud] = b->characterId;           // +0x174 + 4*hud
    b->SetButtonColours(hud, 0xB4);                 // highlight
    Pages::CharacterSelect::GetPageById(0x6B)->OnButtonDriverSelect(b, b->characterId, hud);
}
```

## OnButtonClick: USA 807DD56C (PAL 807E35FC)

```c
void OnButtonClick(self, ButtonDriver *b, u32 hud) {
    id = b->characterId;
    b->SetButtonColours(hud, 0xFF);                 // "OK" colour
    b->SetMessage(hud + 0x9FB);                     // "OK"-style BMG per player
    page = GetPageById(0x6B);
    page->OnButtonDriverClick(b, id, hud);          // 80823548
    FUN_80863EF0(*(809BFF90), hud, id);             // sound/effect manager (not identified)
}
```

OnMiiButtonClick (807DD7F0) instead opens the MiiSelect page (0x60) when
there are multiple players or when online. Otherwise it does the same
SetButtonColours, SetMessage and OnButtonDriverClick.

## Pages::CharacterSelect::OnButtonDriverSelect: USA 80823B94 (PAL 8083E5F4)

```c
void OnButtonDriverSelect(page, ButtonDriver *b, CharacterId id, u8 hud) {
    if (Mii::IsMiiId(id)) {                        // 0x18..0x2C
        bonus = (id-0x1A <= 1 || id-0x20 <= 1 || id-0x26 <= 1) ? 2 : 0;  // outfit B
        id = bonus + MiiToCharacterId(page->miiGroup.GetMii(hud));       // 8084E7CC
    }
    if (page->+0x08) {
        if (IsMiiId(id) && page->miiSelected[hud])        // +0x35C
            names[hud].SetMessage(MiiNameBmg(id, 1), &textInfoWithMii(page->+0x8F4[hud]));
        else
            names[hud].SetMessage(GetCharacterNameBmg(id, 0));           // 8081B874
        models[hud].RequestModel(id);                     // DriverModelControl 806365B0
        models[hud].+0x80 = 0;
    }
}
```

`8081B874` returns the BMG id of a character's name. It's the place a custom
character needs a name, together with the name BMG files.

## Pages::CharacterSelect::OnButtonDriverClick: USA 80823548 (PAL 8083DFA8)

This is the big confirm handler (0x64C bytes). In order:
1. `SectionParams::CopyMiisToRacedata`.
2. If the ID is a Mii, resolves the outfit/size variant the same way as
   above.
3. Sets the name plate and requests the model. It also calls
   808642B8/80864694 (player-Mii related).
4. Writes the chosen ID into the per-player character slot of the section
   params (+0x12C).
5. `MenuDriverModel::SwitchState` (selection animation).
6. `ControlsManipulatorManager::InitHolders`.
7. Chooses the next page by mode and player count via
   `Pages::Menu::LoadNextPageWithDelayById`: 0x6C (kart select), 0x76, 0x81,
   0x74 (VS teams; also VSTeamsView::AssignTeams), 0x83.
8. `ModelRenderer::LoadKartModelsByCharacter(hud, id)`, which starts loading
   `<postfix>-allkart.szs` and the kart archives.
9. Writes racedata scenario fields +0xC20/+0xC24/+0xC28 per player.
10. In tournaments, uses the competition's fixed character.
11. Calls 808241C8 (random fill of racedata scenario 1 players).

Nothing in it is sized by the button count. The Mii branches key off
`Mii::IsMiiId`, so they turn off when IsMiiId returns false.

## MenuModelBRRESHandle::BindDriverBRRES: USA 8084B138 (PAL 8081E358)

```c
bool BindDriverBRRES(handle, CharacterId id) {
    file = id;
    if (id == 0x10) file = 0x2D;            // Peach    -> pc_menu
    else if (id == 0x0F) file = 0x2E;       // Daisy    -> ds_menu
    else if (id == 0x17) file = 0x2F;       // Rosalina -> rs_menu
    if ((curSection == 0x3D || curSection == 0x3E) && id >= 0x18) {
        // award / ending scenes: Mii model by the player's Mii gender
        name = isFemale ? "ma_mii_f.brres" : "ma_mii_m.brres";
        res = ArchiveMgr::GetFile(archive 2, name);
    } else {
        name = GetPath("%s.brres", GetKartArchivePostfix(file));   // 805A3F9C, 8053C48C
        res = ArchiveMgr::GetFile(archive 6 /* Driver.szs */, name);  // 8053BCC0
    }
    if (!res) return false;
    handle->res = res; ModelDirector::BindBRRESImpl(&handle->res, name, 0, 0);  // 80557478
    return true;
}
```

Callers: MenuDriverModelMgr ctor 8084D040, MenuDriverModel::SetPlayerCharacter
8084DF0C / 8084E514. To give IDs 0x2D–0x2F to new characters, patch the three
compares at 8084B140/8084B168/8084B170, or the three `li` at
8084B17C/84/8C, so the swap targets other IDs or is skipped. A custom
character's menu model is then `<suffix>.brres` inside `Scene/Model/Driver.szs`.

## Everything that assumes 24 + 2

| Where | What |
| --- | --- |
| buttonIdToCharacterId 808A3108 | 24 entries, 3 weights × 8 |
| Load 807DC518 | 3×8 unlock loop; Mii flags for 0x18/0x1A; `n = 6H + miiCount`; H clamp [3,4] |
| GetUnlockedStatus 807DC80C | same 3×8 + 2 |
| GetUnlockedCharacterCountByWeight 807DDB5C | 8 unrolled flags per weight; weight 3 = 2 Mii flags |
| GetCorrectButtonDriverId 807DDC1C | weight row of 8; Mii base 0x1E, stride 2 |
| LoadButton 807DC898 | rowLen = 2H; ctr name `CharacterSelect<H>_<row>` (BRCTR files exist only for H = 2, 3, 4 and rows 0–3) |
| CtrlMenuCharacterSelect layout | `isUnLocked[26]` at +0x18C..+0x1A5, struct ends at 0x230 (grow by allocating your own table, not by extending the struct) |
| GetDriverParamEntry 8058B73C | IDs > 0x17 folded into 3 Mii stat entries (driverParam has 27) |
| BindDriverBRRES 8084B138 | Peach/Daisy/Rosalina → 0x2D/0x2E/0x2F menu models |

## BRCTR placement records

BRCTR files ("bctr" magic) hold an animation section and a table of 60-byte
placement records. Header: u16 at +0x10 is the offset of the string pool.
Every name below is an offset into that pool.

| Offset | Size | Meaning |
| --- | --- | --- |
| 0x00 | u16 | name offset (e.g. "Button3") |
| 0x02 | u8 | 0 |
| 0x03 | u8 | alpha (255) |
| 0x04 | u16 | 1 (seen in every record) |
| 0x06 | u16 | 0 |
| 0x08 | f32 | unknown (0, 1, 2, 3, 4, 5, 6, 8, 9, 11, 13 seen; same within a row pair; maybe animation delay/order) |
| 0x0C | f32×3 | 4:3 position x, y, z |
| 0x18 | f32×2 | 4:3 scale x, y |
| 0x20 | f32×3 | 16:9 position x, y, z |
| 0x2C | f32×2 | 16:9 scale x, y |
| 0x34 | 8 bytes | zero padding |

Coordinates are layout units: origin at the screen centre, +y up, the 4:3
screen is 608×456. In every vanilla CharacterSelect file the 4:3 and 16:9
values are identical. The whole grid is offset by `control/CharacterSelectNULL`
(+90, +2), or "…NULLCenter" (+72/+80, +2, scale 0.9) for 3–4 players.

`button/ctrl/CharacterSelect4_*.brctr` (H = 4, button w006_chara 92×45):

| File | Records used | Positions (x, y) |
| --- | --- | --- |
| 4_0 (light) | Button0–7 | columns x = -141, -47, 47, 141 × rows y = 140, 90 |
| 4_1 (medium) | Button0–7 | same columns × y = 40, -10 |
| 4_2 (heavy) | Button0–7 | same columns × y = -60, -110 |
| 4_3 (Mii) | Button0–1 | (47, -160), (141, -160) |

Each file also has a Button8 at (100, -50) and, in 4_3, Button2–7 on
leftover positions. These look unused. `CharacterSelect3_*` (H = 3,
w025 buttons) uses 3 columns x = -115, 0, 115 with rows 50 apart.
`CharacterSelect2_*` (H = 2, w026 buttons) uses 2 columns x = ±95, rows 55 apart.

So a weight occupies two screen rows of 2H buttons, and "a row" in code
(`i / rowLen`) is a weight, not a screen line.

## Implications for a 48-button version

- Either replace `Load`, `LoadButton`, `GetCorrectButtonDriverId`,
  `GetUnlockedCharacterCountByWeight` and `GetUnlockedStatus` wholesale, or
  replace Load and LoadButton and keep the others unused.
- The new Load can:
  - keep the ControlLoader call for CharacterSelectNULL;
  - allocate `ButtonDriver[N]` with the same `new[]` + `__construct_new_array(807DC778, 807DC7B4, 0x260)` pattern;
  - call `InitControlGroup(N)`;
  - for each button: `AddControl`, then `PushButton::Load("button", <ctr>, <variant>, 0x1F, 1, 0)`,
    set +0x240 to the CharacterId and +0x254 = 0, set the icon panes, and set
    the +0x1B8/+0x1CC/+0x1E0 handlers;
  - set +0x1AC = N.
- `<ctr>`/`<variant>` must name a BRCTR record for the button's position. We
  can ship a new `CharacterSelect48.brctr` with records `Button0`…`Button47`
  laid out in rows.
- Keep +0x1A8 (H) consistent with whatever OnUpdate and InitSelf read.
  InitSelf only uses +0x1AC. OnUpdate (807DD01C) was not analysed yet.
- Navigation is position-based (ControlManipulator), so rows work without
  extra code.
- Icons: `GetCharacterIconPaneName(id)` (8083BE80) returns a pane name inside
  `character_64x64_common.brlyt` (`cha_NN_*`). Custom characters need new
  picture panes and textures there, plus a patched GetCharacterIconPaneName.
