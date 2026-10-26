"""The game's 48 character IDs and what each one is used for in the vanilla game.

IDs 0x00-0x17 are the 24 regular drivers. IDs 0x18-0x2C are Mii outfits and
0x2D-0x2F are the menu-preview models of Peach, Daisy and Rosalina (the menu
swaps to them in MenuModelBRRESHandle::BindDriverBRRES). This mod turns all 24
into more roster slots, and gives the payload its own menu-model lookup so
those three still preview correctly. The weight class is fixed per ID, because the game picks the
vehicle set (small/medium/large) from it.
"""

# (id, vanilla use, weight, vanilla file suffix or None)
IDS = [
    (0x00, "Mario", "medium", "mr"),
    (0x01, "Baby Peach", "small", "bpc"),
    (0x02, "Waluigi", "large", "wl"),
    (0x03, "Bowser", "large", "kp"),
    (0x04, "Baby Daisy", "small", "bds"),
    (0x05, "Dry Bones", "small", "ka"),
    (0x06, "Baby Mario", "small", "bmr"),
    (0x07, "Luigi", "medium", "lg"),
    (0x08, "Toad", "small", "ko"),
    (0x09, "Donkey Kong", "large", "dk"),
    (0x0A, "Yoshi", "medium", "ys"),
    (0x0B, "Wario", "large", "wr"),
    (0x0C, "Baby Luigi", "small", "blg"),
    (0x0D, "Toadette", "small", "kk"),
    (0x0E, "Koopa Troopa", "small", "nk"),
    (0x0F, "Daisy", "medium", "ds"),
    (0x10, "Peach", "medium", "pc"),
    (0x11, "Birdo", "medium", "ca"),
    (0x12, "Diddy Kong", "medium", "dd"),
    (0x13, "King Boo", "large", "kt"),
    (0x14, "Bowser Jr.", "medium", "jr"),
    (0x15, "Dry Bowser", "large", "bk"),
    (0x16, "Funky Kong", "large", "fk"),
    (0x17, "Rosalina", "large", "rs"),
    (0x18, "Mii small outfit A (male)", "small", None),
    (0x19, "Mii small outfit A (female)", "small", None),
    (0x1A, "Mii small outfit B (male)", "small", None),
    (0x1B, "Mii small outfit B (female)", "small", None),
    (0x1C, "Mii small outfit C (male)", "small", None),
    (0x1D, "Mii small outfit C (female)", "small", None),
    (0x1E, "Mii medium outfit A (male)", "medium", None),
    (0x1F, "Mii medium outfit A (female)", "medium", None),
    (0x20, "Mii medium outfit B (male)", "medium", None),
    (0x21, "Mii medium outfit B (female)", "medium", None),
    (0x22, "Mii medium outfit C (male)", "medium", None),
    (0x23, "Mii medium outfit C (female)", "medium", None),
    (0x24, "Mii large outfit A (male)", "large", None),
    (0x25, "Mii large outfit A (female)", "large", None),
    (0x26, "Mii large outfit B (male)", "large", None),
    (0x27, "Mii large outfit B (female)", "large", None),
    (0x28, "Mii large outfit C (male)", "large", None),
    (0x29, "Mii large outfit C (female)", "large", None),
    (0x2A, "Mii medium", "medium", None),
    (0x2B, "Mii small", "small", None),
    (0x2C, "Mii large", "large", None),
    (0x2D, "Peach menu-preview model (pc_menu)", "medium", None),
    (0x2E, "Daisy menu-preview model (ds_menu)", "medium", None),
    (0x2F, "Rosalina menu-preview model (rs_menu)", "large", None),
]

MAX_CHARACTERS = len(IDS)  # 48
VANILLA = {vanilla: (i, weight, suffix) for i, vanilla, weight, suffix in IDS if suffix}
FREE_IDS = [(i, weight) for i, _, weight, suffix in IDS if suffix is None]
WEIGHTS = ("small", "medium", "large")
