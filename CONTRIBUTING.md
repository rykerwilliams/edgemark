# Contributing to Edgemark

## Run it locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest
EDGEMARK_DB=./dev.db uvicorn app.main:app --reload --port 8080
python -m pytest -q
```

The front end is plain HTML/CSS/JS in `app/static/`. There's no build step:
edit and reload. The API is documented at `/docs` while the server runs.

## Where things live

| File | What it owns |
|---|---|
| `app/logic.py` | Pure logic, no I/O: decklist/cube parsing, copy planning (`desired_copies`), painted-vs-desired diff (`diff_card`), mark-id encoding. **Put new rules here and unit test them.** |
| `app/main.py` | FastAPI routes, SQLite schema and migrations, Archidekt/CubeCobra fetching. |
| `app/static/app.js` | UI: rendering, the sleeve-edge SVG (`sleeveSVG`), mark labels (`markInfo`). |
| `guide/` | 3D-printable marking guide. `edgemark_guide.scad` is the source of truth; regenerate STLs with OpenSCAD. |
| `docs/DESIGN.md` | Every design decision, its limits, and where to change it. |
| `docs/FAQ.md` | User-facing answers, cross-referenced to DESIGN.md. |

## Rules that protect painted sleeves

People paint real sleeves based on what Edgemark says. A bug here costs paint
and time, so:

1. **Deck ids are never reused.** Create decks through `_new_deck_id()`.
2. **Mark ids are stable.** Deck stripe = deck id, variant dot =
   `-(deck_id*100 + idx)`. Changing the encoding needs a migration of
   `cards.physical` (see DESIGN.md D14).
3. **Slot and corner changes move marks.** Anything that changes where a mark
   sits must show up as clear-and-repaint work, never silently.
4. **Schema changes go in `migrate()`** in `main.py` and must work on an
   existing database. Add a column with a default. Don't rebuild tables that hold
   user data.

## Changing a design decision

1. Open a "Feature or design change" issue naming the DESIGN.md entry.
2. Update that entry in the same PR: new decision on top, old reasoning under
   **History**.
3. Update FAQ.md if users would notice.

## Releases

Every push to `main` publishes `ghcr.io/rykerwilliams/edgemark:latest`.
Tag `vX.Y.Z` to publish a versioned image. Note any painted-sleeve migration in
the release notes.

## License

Contributions are accepted under the same licenses as the files they change
("inbound = outbound"): AGPL-3.0-or-later for code and docs, CC BY-SA 4.0 for
`guide/`. Opening a pull request means you agree to that, and that you have the
right to contribute the work. New source files start with an SPDX line, e.g.
`# SPDX-License-Identifier: AGPL-3.0-or-later`.
