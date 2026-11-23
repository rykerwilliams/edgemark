// SPDX-License-Identifier: CC-BY-SA-4.0
// Edgemark marking guide (https://github.com/rykerwilliams/edgemark)
//
// Marks go in the border of the card face, never on the top strip (name and
// mana cost):
//   * left long edge   main-deck slots 1-30
//   * right long edge  slots 31-60, or sideboard marks level with the left slot
//   * bottom edge      variant positions B1-B20
//
// Two jigs, each a base plus a window plate:
//   long jig    one base, LEFT plate and RIGHT plate (30 windows each)
//   bottom jig  one base, BOTTOM plate (20 windows)
// The sleeve lies card face up with the edge being marked pushed against the
// stop at the far side. The arrow on each plate points to the card's top.
//
// Render one part at a time (F6), then export STL:
//   PART = "long_base" | "left_plate" | "right_plate" | "bottom_base" | "bottom_plate"

PART = "left_plate";
SLOT1_AT_BOTTOM = false;   // match Edgemark Settings: "Slot 1 is nearest the ..."

// ---- sleeve and slots (must match Edgemark Settings) ----
sleeve_len = 89.0;   // Perfect Fit inner, long side
sleeve_wid = 64.0;   // Perfect Fit inner, short side
clear      = 0.8;    // total clearance along the edge
pitch      = 2.6;    // slot spacing
long_slots = 30;     // "Slots per long edge"
bottom_slots = 20;   // "Variant positions on the bottom edge"
win_w      = 1.5;    // window width (pen tip up to ~1 mm)
win_l      = 3.0;    // window depth from the edge = mark depth (stays in the border)

// ---- body ----
side   = 8.0;   // end walls (hold 6x2 mm magnets)
stop   = 5.0;   // stop wall the marked edge rests against
cover  = 26.0;  // how far the plate reaches over the card
base_t = 3.0;
rim    = 0.5;   // wall height above the card bed (card + inner ~0.4)
plate_t = 3.0;
mag_d = 6.3; mag_h = 2.2; peg_d = 3.0; peg_h = 1.6; peg_hole_d = 3.4;
$fn = 48;

function edge_len(kind) = (kind == "bottom" ? sleeve_wid : sleeve_len) + clear;
function out_w(kind) = edge_len(kind) + 2 * side;
out_l = cover + stop;
function slots(kind) = kind == "bottom" ? bottom_slots : long_slots;
function sx(kind, i) = side + (edge_len(kind) - (slots(kind) - 1) * pitch) / 2 + i * pitch;
function magnets(kind) = [[side/2, 8], [side/2, 20], [out_w(kind)-side/2, 8], [out_w(kind)-side/2, 20]];
function pegs(kind) = let(dx = kind == "bottom" ? 15 : 25) [[out_w(kind)/2 - dx, cover + stop/2], [out_w(kind)/2 + dx, cover + stop/2]];

// With the marked edge at the far side, card face up:
//   left edge  -> the card's top points right
//   right edge -> the card's top points left
//   bottom     -> the card is upside down, its left side points right
// so position 1 is counted from the right end for LEFT and BOTTOM plates.
function from_right(p) = p == "left" ? !SLOT1_AT_BOTTOM : p == "right" ? SLOT1_AT_BOTTOM : true;

module base(kind) {
  W = out_w(kind);
  difference() {
    union() {
      cube([W, out_l, base_t]);
      translate([0, 0, base_t]) cube([side, out_l, rim]);
      translate([W - side, 0, base_t]) cube([side, out_l, rim]);
      translate([0, cover, base_t]) cube([W, stop, rim]);
    }
    for (m = magnets(kind)) translate([m[0], m[1], base_t + rim - mag_h]) cylinder(d = mag_d, h = mag_h + 1);
    for (p = pegs(kind)) translate([p[0], p[1], base_t + rim - peg_h - 0.4]) cylinder(d = peg_hole_d, h = peg_h + 1);
    translate([W / 2, 0, base_t - 1.2]) cylinder(d = 22, h = 3);   // finger notch
  }
}

module engrave(x, y, s, size) {
  translate([x, y, plate_t - 0.6]) linear_extrude(1)
    text(s, size = size, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
}

module plate(p) {
  kind = p == "bottom" ? "bottom" : "long";
  W = out_w(kind); n = slots(kind); fr = from_right(p);
  function k(pos) = fr ? n - pos : pos - 1;   // pos is 1-based
  title = p == "left" ? "LEFT EDGE" : p == "right" ? "RIGHT EDGE" : "BOTTOM EDGE";
  difference() {
    cube([W, out_l, plate_t]);
    // paint windows, open right up to the card edge
    for (pos = [1:n]) translate([sx(kind, k(pos)) - win_w / 2, cover - win_l, -1]) cube([win_w, win_l + 0.01, plate_t + 2]);
    // index holes (not for paint): big at position 1, small at every 5th
    translate([sx(kind, k(1)), cover - win_l - 3, -1]) cylinder(d = 2.4, h = plate_t + 2);
    for (pos = [5:5:n]) translate([sx(kind, k(pos)), cover - win_l - 2.4, -1]) cylinder(d = 1.1, h = plate_t + 2);
    // numbers on the stop strip
    engrave(sx(kind, k(1)), cover + stop / 2, "1", 2.4);
    for (pos = [5:5:n]) engrave(sx(kind, k(pos)), cover + stop / 2,
                                 p == "bottom" ? str("B", pos) : str(pos), p == "bottom" ? 1.9 : 2.4);
    // title and the direction of the card's top
    engrave(W / 2, 9, title, 4);
    engrave(W / 2, 3.6, p == "bottom" ? "card upside down" : (fr ? "card top -->" : "<-- card top"), 2.6);
    for (m = magnets(kind)) translate([m[0], m[1], -1]) cylinder(d = mag_d, h = mag_h + 1);
  }
  for (q = pegs(kind)) translate([q[0], q[1], -peg_h]) cylinder(d = peg_d, h = peg_h + 0.01);
}

// print orientation: bases as modelled, plates flat face down
if (PART == "long_base") base("long");
else if (PART == "bottom_base") base("bottom");
else translate([0, 0, plate_t]) mirror([0, 0, 1])
  plate(PART == "left_plate" ? "left" : PART == "right_plate" ? "right" : "bottom");
