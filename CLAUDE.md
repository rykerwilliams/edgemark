# Edgemark: notes for coding agents

Read `CONTRIBUTING.md` (layout and the painted-sleeve rules) and
`docs/DESIGN.md` (decisions D1–D19 and open questions O1–O6) before changing
behaviour.

- Test: `python -m pytest -q`. New planning or parsing logic goes in
  `app/logic.py` with unit tests in `tests/test_logic.py`. API flows go in
  `tests/test_api.py`.
- Never reuse deck ids (`_new_deck_id()`), never change mark-id encoding
  without a migration, and put schema changes in `migrate()`.
- When you change a design decision, update its DESIGN.md entry in the same
  commit.
- UI values from users or imports are untrusted. Pass them through `esc()`
  before they go into HTML.
- Licensing: code is AGPL-3.0-or-later, `guide/` is CC-BY-SA-4.0. New files
  start with the matching SPDX line. Keep the source link in the Guide tab.
- Regenerate guide STLs from `guide/edgemark_guide.scad` with OpenSCAD, not by
  hand.
