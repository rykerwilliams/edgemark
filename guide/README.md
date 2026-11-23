# Edgemark marking guide (3D print)

A two-part jig that puts every mark in the same place on every sleeve. Its 24
windows at 2.6 mm pitch match Edgemark's slots 1–24 (side A). For slots 25–48
(side B), flip the sleeve over and use the same window, slot 25 = window 1.

| File | What |
|---|---|
| `edgemark_guide_base.stl` | Base with a pocket for the sleeve, side walls and a top stop |
| `edgemark_guide_plate_topleft.stl` | Window plate, slot 1 at the top-left corner (Edgemark default) |
| `edgemark_guide_plate_topright.stl` | Window plate for the top-right starting corner |
| `edgemark_guide.scad` | Parametric OpenSCAD source with engraved numbers (4, 8, …, 24 and 28…48) |
| `make_guide.py` | Python fallback generator (same shape, no engraved numbers) |

## Print

* PLA or PETG, 0.2 mm layers, 3 walls, no supports. Print both parts flat side
  down, as exported.
* Overall 80.8 × 42 mm. Base 3.5 mm tall, plate 3 mm plus 1.6 mm pegs.
* Optional: 8 × 6×2 mm neodymium disc magnets (4 per part) glued into the
  pockets. **Check polarity** so the plate snaps onto the base. Without
  magnets, the two pegs still register the plate and you hold it down by hand.

## Use

1. Slide the Perfect Fit inner sleeve (card inside, face up) into the base until
   its top edge touches the stop.
2. Drop the plate on. The long windows are slots 4, 8, 12, 16, 20 and 24. The
   big hole marks slot 1 and the small one slot 13.
3. Dab each slot Edgemark lists for that card through its window. The deck
   stripe goes at the very top edge. A variant dot goes in the lower half of
   the same window.
4. Lift the plate straight up, slide the sleeve out and let it dry fully before
   it goes into the outer sleeve.

## Fit tweaks

Sleeve brands vary by about ±0.5 mm. If the pocket is loose or tight, change
`SLEEVE_W` (Python) or `sleeve_w` (SCAD) and regenerate. If the plate doesn't
hold the card flat, lower `RIM` from 0.5 to 0.3. Print one test with a
cheap card first.
