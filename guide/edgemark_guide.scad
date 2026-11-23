// SPDX-License-Identifier: CC-BY-SA-4.0
// Edgemark marking guide (https://github.com/rykerwilliams/edgemark)
// Edgemark marking guide: base + window plate. Same geometry as make_guide.py,
// plus engraved slot numbers on the plate. All sizes in mm.
// Render one part at a time: set PART to "base" or "plate", then F6 and export STL.

PART = "plate";        // "base" | "plate"
START_RIGHT = false;   // true if Edgemark's starting corner is top-right
SIDE_B_LABELS = true;  // also engrave 25-48 under 1-24

sleeve_w = 64.0; clear = 0.8; slots = 24; pitch = 2.6;
win_w = 1.5; win_l = 6.0; win_l_long = 9.0;
pocket_w = sleeve_w + clear; side = 8.0; stop = 5.0; pocket_l = 37.0;
out_w = pocket_w + 2*side; out_l = pocket_l + stop;
base_t = 3.0; rim = 0.5; plate_t = 3.0;
mag_d = 6.3; mag_h = 2.2; peg_d = 3.0; peg_h = 1.6; peg_hole_d = 3.4;
$fn = 48;

magnets = [[side/2,10],[side/2,28],[out_w-side/2,10],[out_w-side/2,28]];
pegs = [[out_w/2-22, pocket_l+stop/2],[out_w/2+22, pocket_l+stop/2]];
function sx(i) = side + (pocket_w - (slots-1)*pitch)/2 + i*pitch;
function k(n) = START_RIGHT ? slots-n : n-1;   // n = 1-based slot number

module base() {
  difference() {
    union() {
      cube([out_w, out_l, base_t]);
      translate([0,0,base_t]) cube([side, out_l, rim]);
      translate([out_w-side,0,base_t]) cube([side, out_l, rim]);
      translate([0,pocket_l,base_t]) cube([out_w, stop, rim]);
    }
    for (m = magnets) translate([m[0],m[1],base_t+rim-mag_h]) cylinder(d=mag_d, h=mag_h+1);
    for (p = pegs) translate([p[0],p[1],base_t+rim-peg_h-0.4]) cylinder(d=peg_hole_d, h=peg_h+1);
    translate([out_w/2,0,base_t-1.2]) cylinder(d=22, h=3);
  }
}

module plate() {
  difference() {
    cube([out_w, out_l, plate_t]);
    for (n = [1:slots]) {
      L = n % 4 == 0 ? win_l_long : win_l;
      translate([sx(k(n))-win_w/2, pocket_l-L, -1]) cube([win_w, L+0.01, plate_t+2]);
    }
    translate([sx(k(1)), pocket_l-win_l_long-3.2, -1]) cylinder(d=2.4, h=plate_t+2);
    translate([sx(k(13)), pocket_l-win_l_long-3.2, -1]) cylinder(d=1.6, h=plate_t+2);
    translate([side+6, 5, -1]) cube([pocket_w-12, pocket_l-win_l_long-15, plate_t+2]);
    for (m = magnets) translate([m[0],m[1],-1]) cylinder(d=mag_d, h=mag_h+1);
    // engraved numbers above the windows (0.6 mm deep), every 4th slot
    for (n = [4:4:slots]) {
      translate([sx(k(n)), pocket_l+1.0, plate_t-0.6])
        linear_extrude(1) text(str(n), size=2.4, halign="center", font="Liberation Sans:style=Bold");
      if (SIDE_B_LABELS)
        translate([sx(k(n)), pocket_l-win_l_long-7.5, plate_t-0.6])
          linear_extrude(1) text(str(n+slots), size=1.8, halign="center", font="Liberation Sans");
    }
    translate([sx(k(1)), pocket_l+1.0, plate_t-0.6])
      linear_extrude(1) text("1", size=2.4, halign="center", font="Liberation Sans:style=Bold");
  }
  for (p = pegs) translate([p[0],p[1],-peg_h]) cylinder(d=peg_d, h=peg_h+0.01);
}

if (PART == "base") base();
else translate([0,0,plate_t]) mirror([0,0,1]) plate();  // printed face-down
