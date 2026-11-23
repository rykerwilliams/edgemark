# Edgemark marking guide (3D print)

Licensed [CC BY-SA 4.0](LICENSE). Credit "Edgemark marking guide by
rykerwilliams" with a link to the repo, and share remixes under the same license.

Two magnetic jigs that put every mark in the same place on every sleeve. Marks
go in the border of the card face, about 3 mm deep. The top strip, with the name
and mana cost, is never marked.

| Edge | Positions | Edgemark label | Jig |
|---|---|---|---|
| Left long edge | slots 1–30 | `L1`–`L30` | long base + **LEFT** plate |
| Right long edge | slots 31–60, or sideboard marks | `R1`–`R30`, `R5 SB` | long base + **RIGHT** plate |
| Bottom edge | variant positions | `B1`–`B20` | bottom base + **BOTTOM** plate |

The LEFT and RIGHT plates count from opposite ends, so `R5 SB` lands exactly
level with `L5`.

| File | What |
|---|---|
| `edgemark_long_base.stl` | Base for the long edges: sleeve pocket, end walls, stop |
| `edgemark_left_plate.stl` | 30 windows for the left edge |
| `edgemark_right_plate.stl` | 30 windows for the right edge |
| `edgemark_bottom_base.stl` | Base for the bottom edge |
| `edgemark_bottom_plate.stl` | 20 windows for the bottom edge |
| `edgemark_guide.scad` | Parametric OpenSCAD source for all five parts |

You only need the bottom jig if you split decks into variants.

## Print

* PLA or PETG, 0.2 mm layers, 3 walls, no supports. Print every part flat
  side down, as exported.
* Long jig 105.8 × 31 mm, bottom jig 80.8 × 31 mm. Bases are 3.5 mm tall,
  plates 3 mm plus 1.6 mm pegs.
* Optional: 6×2 mm neodymium disc magnets, 4 per part, glued into the pockets.
  **Check polarity** so each plate snaps onto its base. Without magnets, the
  pegs still locate the plate and you hold it down by hand.

## Use

1. Lay the inner sleeve (card inside) **face up** in the base, with the edge
   the work list names pushed against the stop at the far side:
   * **L** (left edge): the card's top points right.
   * **R** (right edge): the card's top points left.
   * **B** (bottom edge): the card is upside down.
   The arrow engraved on each plate shows which way the card's top goes.
2. Drop on the matching plate. The big hole marks position 1, small holes mark
   every fifth position, and the numbers are engraved above the windows.
3. Dab each listed position through its window, right at the edge.
4. Lift the plate straight up, slide the sleeve out, and let the paint dry fully
   before the sleeve goes into its outer sleeve.

## Fit tweaks

Sleeve brands vary by about ±0.5 mm. If the pocket is loose or tight, change
`sleeve_len` / `sleeve_wid` in `edgemark_guide.scad` and re-export. If the plate
doesn't hold the card flat, lower `rim` from 0.5 to 0.3. If you set Edgemark's
"Slot 1 is nearest the bottom", set `SLOT1_AT_BOTTOM = true` and re-export the
plates. Print one test and mark a cheap card first.

Export a part with OpenSCAD:

```bash
openscad -o edgemark_left_plate.stl -D 'PART="left_plate"' edgemark_guide.scad
```
