"""Select-screen geometry: the roster as horizontal rows along the bottom of the
screen, and the driver preview models in a row across the top.

Coordinates are the game's layout units: the origin is the screen centre and
the screen is 608 x 456. That holds on 16:9 too: the game reads the 16:9 values
of a placement record but still lays out 608 units across, stretched to the
wider screen (seen in Dolphin: a 92x45 button drew 111x38 px and 16:9 x values
1.37x too far apart).
"""

from dataclasses import dataclass

SCREEN_H = 456
SCREEN_W = {"4:3": 608, "16:9": 608}
BUTTON_W, BUTTON_H = 92, 45  # vanilla w006_chara button

# The roster area: the bottom part of the screen, leaving a margin for the
# back button and the page's title bar.
ROSTER_TOP = 10
ROSTER_BOTTOM = -165  # above the bottom bar (back button, help text), which covers ~-170 and below
SIDE_MARGIN = 16
NAME_PLATE_H = 33  # common_w027_chara_name plate
PREVIEW_Y = 62  # preview record y: feet just above the name plates (tuned by eye)
PREVIEW_X_GAIN = 1.93  # a preview lands this many times its record x from the centre (2P, measured)


@dataclass
class Placement:
    x: float
    y: float
    scale: float


def grid(count, columns=12, aspect="4:3"):
    """Button placements for `count` buttons, filled left to right, top row first."""
    if count < 1:
        return []
    rows = -(-count // columns)
    usable_w = SCREEN_W[aspect] - 2 * SIDE_MARGIN
    usable_h = ROSTER_TOP - ROSTER_BOTTOM
    cell_w, cell_h = usable_w / columns, usable_h / rows
    scale = min(cell_w / BUTTON_W, cell_h / BUTTON_H, 1.0)
    out = []
    for i in range(count):
        row, col = divmod(i, columns)
        in_row = min(columns, count - row * columns)
        # Centre a short last row, but on the grid's columns: the cursor moves
        # down within a column (wrapping to the top), so a button between two
        # columns could never be reached from above.
        x0 = -(columns - 1) * cell_w / 2 + (columns - in_row) // 2 * cell_w
        out.append(Placement(round(x0 + col * cell_w, 2), round(ROSTER_TOP - cell_h * (row + 0.5), 2), round(scale, 3)))
    return out


def preview_row(players, aspect="4:3"):
    """Driver preview placements across the top half: one per local player."""
    w = SCREEN_W[aspect]
    cell = w / players
    # The model is drawn by a perspective camera, so it moves on screen about
    # 2.1x as far as its record (measured in Dolphin, 1P: y 30 -> feet at -22,
    # y 86.8 -> feet at 98). y 62 at scale 0.9 stands the feet just above the
    # name plate (see name_plate_y) with the head under the title bar.
    # x is perspective-scaled the same way (2P: record x -152 put the model's
    # centre at -293, half off the screen), so it is divided by PREVIEW_X_GAIN
    # to stand each model over its name plate at preview_x.
    scale = min(cell / 256, 0.9)
    y = PREVIEW_Y
    return [Placement(round(preview_x(players, i, aspect) / PREVIEW_X_GAIN, 2), round(y, 2), round(scale, 3))
            for i in range(players)]


def preview_x(players, i, aspect="4:3"):
    """Screen x of player i's preview (and its name plate): centre of its share of the width."""
    cell = SCREEN_W[aspect] / players
    return round(-SCREEN_W[aspect] / 2 + cell * (i + 0.5), 2)


def name_plate_y(scale):
    """Centre of a preview's name plate: between the preview and the roster."""
    return ROSTER_TOP + NAME_PLATE_H * scale / 2 + 2
