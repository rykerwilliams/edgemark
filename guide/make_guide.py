# SPDX-License-Identifier: CC-BY-SA-4.0
"""Generate the Edgemark marking guide STLs (base + window plate).

Usage: python make_guide.py [out_dir]
Needs: pip install manifold3d trimesh numpy
All sizes in mm. Change the constants to fit your sleeves.
"""
import sys
from pathlib import Path

import numpy as np
import trimesh
from manifold3d import Manifold

# --- sleeve and slots (must match Edgemark settings: 24 slots per side) ---
SLEEVE_W = 64.0        # Perfect Fit inner width
CLEAR = 0.8            # total side clearance
SLOTS = 24
PITCH = 2.6            # slot spacing
WIN_W = 1.5            # window width (pen tip <= ~1 mm)
WIN_L = 6.0            # normal window length
WIN_L_LONG = 9.0       # every 4th slot
# --- body ---
POCKET_W = SLEEVE_W + CLEAR
SIDE = 8.0             # side wall width (holds 6x2 mm magnets)
STOP = 5.0             # top stop wall depth
POCKET_L = 37.0        # how much of the card sits under the plate
OUT_W = POCKET_W + 2 * SIDE
OUT_L = POCKET_L + STOP
BASE_T = 3.0
RIM = 0.5              # wall height above the card bed (card+inner ~0.4)
PLATE_T = 3.0
MAG_D, MAG_H = 6.3, 2.2
PEG_D, PEG_H, PEG_HOLE_D = 3.0, 1.6, 3.4


def box(x, y, z, w, l, h):
    return Manifold.cube([w, l, h]).translate([x, y, z])


def cyl(x, y, z, d, h):
    return Manifold.cylinder(h, d / 2, d / 2, 48).translate([x, y, z])


def slot_x(i):
    """Centre x of slot i (0-based) counted from the left of the pocket."""
    return SIDE + (POCKET_W - (SLOTS - 1) * PITCH) / 2 + i * PITCH


MAGNETS = [(SIDE / 2, 10.0), (SIDE / 2, 28.0), (OUT_W - SIDE / 2, 10.0), (OUT_W - SIDE / 2, 28.0)]
PEGS = [(OUT_W / 2 - 22, POCKET_L + STOP / 2), (OUT_W / 2 + 22, POCKET_L + STOP / 2)]


def base():
    b = box(0, 0, 0, OUT_W, OUT_L, BASE_T)
    b += box(0, 0, BASE_T, SIDE, OUT_L, RIM)                       # left wall
    b += box(OUT_W - SIDE, 0, BASE_T, SIDE, OUT_L, RIM)            # right wall
    b += box(0, POCKET_L, BASE_T, OUT_W, STOP, RIM)                # top stop
    top = BASE_T + RIM
    for x, y in MAGNETS:
        b -= cyl(x, y, top - MAG_H, MAG_D, MAG_H + 1)
    for x, y in PEGS:
        b -= cyl(x, y, top - PEG_H - 0.4, PEG_HOLE_D, PEG_H + 1)
    # finger notch at the open end so the sleeve slides out easily
    b -= cyl(OUT_W / 2, 0, BASE_T - 1.2, 22, 3)
    return b


def plate(start_right=False):
    p = box(0, 0, 0, OUT_W, OUT_L, PLATE_T)
    edge_y = POCKET_L  # the sleeve's top edge sits here
    for i in range(SLOTS):
        n = i + 1
        k = SLOTS - 1 - i if start_right else i
        L = WIN_L_LONG if n % 4 == 0 else WIN_L
        p -= box(slot_x(k) - WIN_W / 2, edge_y - L, -1, WIN_W, L + 0.01, PLATE_T + 2)
    # slot-1 marker: round hole above slot 1, plus a second at slot 13 (start of the second dozen)
    for n, d in ((1, 2.4), (13, 1.6)):
        k = SLOTS - n if start_right else n - 1
        p -= cyl(slot_x(k), edge_y - WIN_L_LONG - 3.2, -1, d, PLATE_T + 2)
    # big viewing window so you can see which card is in the jig
    p -= box(SIDE + 6, 5, -1, POCKET_W - 12, edge_y - WIN_L_LONG - 15, PLATE_T + 2)
    for x, y in MAGNETS:
        p -= cyl(x, y, -1, MAG_D, MAG_H + 1)
    for x, y in PEGS:
        p += cyl(x, y, -PEG_H, PEG_D, PEG_H + 0.01)
    # print orientation: flat face down (pegs and magnet pockets up)
    return p.mirror([0, 0, 1]).translate([0, 0, PLATE_T])


def save(m: Manifold, path: Path):
    mesh = m.to_mesh()
    t = trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts))
    assert t.is_watertight, path
    t.export(path)
    ext = t.bounds[1] - t.bounds[0]
    print(f"{path.name}: {ext[0]:.1f} x {ext[1]:.1f} x {ext[2]:.1f} mm, {len(t.faces)} faces, watertight")


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    save(base(), out / "edgemark_guide_base.stl")
    save(plate(False), out / "edgemark_guide_plate_topleft.stl")
    save(plate(True), out / "edgemark_guide_plate_topright.stl")
