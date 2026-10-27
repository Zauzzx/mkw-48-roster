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
        # Centre a short last row instead of leaving it left-aligned.
        x0 = -(in_row - 1) * cell_w / 2
        out.append(Placement(round(x0 + col * cell_w, 2), round(ROSTER_TOP - cell_h * (row + 0.5), 2), round(scale, 3)))
    return out


def preview_row(players, aspect="4:3"):
    """Driver preview placements across the top half: one per local player."""
    w = SCREEN_W[aspect]
    cell = w / players
    # The model's origin is at its feet, so stand it just above the roster and
    # let it grow upward; full size for one player, shrinking to fit a cell.
    scale = min(cell / 256, 1.0)
    y = ROSTER_TOP + 20
    return [Placement(round(-w / 2 + cell * (i + 0.5), 2), round(y, 2), round(scale, 3)) for i in range(players)]
