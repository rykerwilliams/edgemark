# Edgemark design decisions

Marking sleeves so one copy of a card can serve several decks is an old player
trick (see [Background](../README.md#background)). Most setups people describe
are built around Commander. Edgemark aims to cover a whole collection across
formats. This file records each design choice: what we decided, why, what
other approaches do, what the choice limits, and where in the code to change it. Treat it as a decision log. When a decision
changes, update its entry (keep the old reasoning under "History") rather than
deleting it.

Status values: **Adopted** (in the code), **Proposed** (agreed direction, not
built), **Open** (needs a decision).

---

## 1. Physical marking model

### D1. Marks go on the Perfect Fit inner sleeve, double-sleeved — Adopted
* **Decision:** Paint the inner sleeve on the card-face side, let it dry fully,
  then put it in an outer sleeve. The card itself is never marked.
* **Why:** Standard double-sleeving. The outer sleeve protects the paint, and
  cards keep their value, which matters for signed and old cards.
* **Limits:** Every deck that shares a copy must use **the same outer sleeve**.
  Otherwise a shared card stands out when it moves into another deck. Edgemark
  doesn't model or enforce sleeve type.
* **To change:** A `sleeve` attribute on pools (planned in D9) would let the app
  warn when decks in one pool use different outer sleeves.

### D2. Slots run down the long edges, numbered per pool — Adopted
* **Decision:** Each deck owns one slot *within its pool*. Slots 1–30 run
  down the **left long edge** of the card face, 31–60 down the **right long
  edge** (or the right edge holds sideboard marks, see D18). Slot 1 is nearest
  the card's top by default (Settings: "Slot 1 is nearest the …"). Marks are
  about 3 mm deep, so they sit in the card's border. The top strip (name and
  mana cost) is never marked.
* **Why:** Marks on the top strip would cover the name and cost. The left edge
  is what shows when you fan a hand or a stack, so main-deck marks are
  readable exactly when you sort or de-sideboard. A long edge (89 mm) fits 30
  slots at 2.6 mm, more than the short edge. Decks in different pools never
  share a sleeve, so slot numbers can repeat across pools.
* **Other approaches:** A single colour dot per deck (fine for a handful of
  decks), coloured stickers, or a different sleeve colour per shared card.
  Position-based slots scale further than colour alone.
* **Limits:**
  * 60 decks per pool (30 with sideboard marks on).
  * Slot numbers repeat across pools, so a copy that strays into the wrong
    pool's box reads as the wrong deck. Keep pools in separate boxes.
  * Changing `slot1_end` or `slots_per_edge` after painting invalidates every
    painted mark.
* **To change:** `slots_per_edge` and `slot1_end` are settings. The printed
  guide's `long_slots`, `pitch` and `SLOT1_AT_BOTTOM` in
  `guide/edgemark_guide.scad` must match. A pool colour band (e.g. one mark on
  the bottom edge per pool) would guard against strays.
* **History:** v0 put 24 slots along the top edge and called the other 24
  "side B" on the card back. Marks on the back of the inner sleeve are hidden
  behind the card and the opaque outer sleeve, and the top strip covers the
  name and cost, so both were dropped before anyone painted. Slots were also
  global then (48 in total across all pools).

### D3. Colour is a pen colour and doesn't identify the deck — Adopted
* **Decision:** Position (slot) identifies the deck. Colour is a second cue
  that makes a box easier to scan.
* **Why:** Pen sets have about 12–24 usable colours, far fewer than 48 decks.
  Relying on position is robust and colour-blind friendly.
* **Practical notes:** Stick to colours found in standard paint pen sets.
  Avoid metallic colours (they can rub onto outer sleeves) and black
  (invisible on most card backs).
* **Limits:** Two decks can share a colour, so you must read the position.
* **To change:** `settings.pens` holds the palette. A "colour-unique" mode could
  refuse duplicate colours when the palette allows it.

### D4. Variant marks go on the bottom edge — Adopted
* **Decision:** A split deck keeps its slot. A card in **all** variants gets
  only the deck's mark. A card in **some** variants also gets the mark of each
  variant using that copy, at the variant's own position on the **bottom
  edge** (B1–B20), in the variant's colour. Positions are allocated per pool,
  so two split decks sharing a copy never collide. Max 8 variants per deck.
  Builds kept as separate Archidekt decks can be imported together as one
  deck with variants (`POST /api/decks/builds`), with the deck and build names
  taken from their shared name prefix (`logic.split_build_names()`).
* **Why:** Uses no deck slots, keeps long-edge windows for deck marks, and
  each bottom position means exactly one variant in its pool.
* **Limits:** 20 variant positions per pool. Reading a variant needs the
  legend (Slots tab or printed guide), since position B3 means different
  things in different pools.
* **To change:** `bottom_positions` (setting) and `bottom_slots` (SCAD).
  Positions are assigned in `_assign_variant_pos()`; drawing is the `B` edge
  in `sleeveSVG()`.
* **History:** v0 drew variants as dots under the deck's stripe in the same
  window. That shared window space with the stripe and doesn't work with
  3 mm side-edge marks.

### D5. The printed guide: two magnetic jigs, one plate per edge — Adopted
* **Decision:** A **long jig** (one base, a LEFT plate and a RIGHT plate with
  30 windows each) and a **bottom jig** (base and BOTTOM plate with 20
  windows). The sleeve lies face up with the edge being marked against the
  stop. Plates are located by two pegs and held by optional 6×2 mm magnets.
  Windows are 1.5 × 3 mm, open to the edge. Position 1 has a big index hole,
  every fifth a small one, and the plates are engraved with numbers, the edge
  name and an arrow to the card's top.
* **Why:** A jig puts every mark in the same place on every sleeve, and the
  magnetic hold lets you mark one-handed. Separate LEFT and RIGHT plates
  count from opposite ends, so a sideboard mark lands exactly level with the
  deck's main mark.
* **Limits:** Sized for 64 × 89 mm Perfect Fit inners. The plates assume
  `SLOT1_AT_BOTTOM = false`. Re-export them if you change that setting.
* **To change:** All dimensions are parameters at the top of
  `guide/edgemark_guide.scad`.
* **History:** v0 was one plate with 24 windows along the top edge.

### D6. Pools: decks that are never sleeved at the same time share copies — Adopted
* **Decision:** Every deck belongs to a named pool. Within a pool, copy *i* of
  a card carries the mark of every deck that runs at least *i* copies
  (quantity tiers). A pool needs `max(qty)` copies. A **dedicated** deck is a
  pool of one.
* **Why:** Commander-focused setups usually assume one table, so every deck
  shares with every other. A whole collection includes decks you play side by side (two Old School decks at an
  event, a cube while a constructed deck is built), signed decks that must keep
  specific copies, and different formats.
* **Limits:**
  * Pools are all-or-nothing: two decks in a pool always share, decks in
    different pools never do. You can't say "A shares with B and B with C,
    but not A with C."
  * Copies are counted by **card name**, not by printing. See D8.
* **To change (Proposed):** Replace pools with **conflict groups**: a deck
  pair is "shareable unless marked as played together." The planner would then
  colour a conflict graph instead of grouping by pool. `desired_copies()` is
  the only function that knows about pools. Keep its output shape
  (`{name, copies: [frozenset(mark ids)]}`) and the rest of the app won't
  notice.

### D7. Painted state is stored and diffed against the plan — Adopted
* **Decision:** For each card the database stores what's *actually painted* (a
  list of mark sets, one per sleeve). The work list is
  `diff(painted, desired)`, matched greedily by largest overlap, so a list
  change produces the fewest add/clear marks rather than a repaint.
* **Why:** This makes re-syncing, swaps, deleted decks and "marks to clear"
  fall out of one mechanism, instead of special cases such as a separate
  marks-to-clear list that can't be rebuilt.
* **Limits:** Sleeves of one card are interchangeable. Edgemark doesn't know
  *which* physical sleeve is which, only how many carry each mark set. The
  greedy matcher is near-optimal, not proven minimal.
* **To change:** `logic.diff_card()` can be swapped for an optimal assignment
  (Hungarian algorithm) without changing callers. Per-sleeve identity would
  need a `sleeves` table, which D8 needs too.

### D8. Cards are keyed by normalised name, not printing — Adopted (known gap)
* **Decision:** `logic.norm(name)` (case-folded, `//` normalised) is the card
  key everywhere: decklists, collection, painted state.
* **Why:** Decklist sites disagree on printings, and marking cares about
  function, not edition.
* **Limits:** This matters for this collection: **signed copies**, specific
  Premodern printings, foils, and artist-specific signing plans all need
  printing-level identity. Today a signed deck works around it by being
  `dedicated`.
* **To change (Proposed):** Add an optional `printing` field (set code +
  collector number, or Scryfall id) to `deck_cards`, collection rows and painted
  sleeves, and widen the key to `(name, printing | *)`, where `*` means any.
  A deck that cares about a printing then gets only matching copies.

### D9. Basic lands are skipped by default — Adopted
* **Why:** Every deck has them and nobody marks them. It's a setting
  (`skip_basics`).
* **To change:** Make it per pool (Old School players may care about specific
  basics), e.g. `pools.skip_basics`.

### D10. Sideboards count; maybeboards don't — Adopted
* **Why:** In 60-card formats the sideboard is physically in the box.
  Per-deck toggle `include_side`.
* **Limits:** Archidekt category handling uses a heuristic (`Sideboard` kept,
  `Maybeboard` and categories excluded from the deck dropped).

### D11. Tokens are "extra cards" attached to decks — Adopted
* **Decision:** A token has a front, an optional back, a quantity and a set of
  decks. It counts for every variant of those decks. A double-sided token is one
  physical card that carries the marks of every deck needing either side.

### D12. Cube tags become decks in one pool — Adopted
* **Decision:** Each ticked CubeCobra tag becomes a deck (with its own slot) in
  pool `Cube: <name>`, plus an optional "other" deck for untagged cards, or the
  whole cube as one deck.
* **Limits:** Uses one slot per tag. No re-sync for cubes yet.
* **To change:** Store `source='cubecobra'` with the tag list, and add a sync
  path like Archidekt's. Each cube is its own pool, so it has its own 60
  slots (D2).

### D18. Sideboard marks: right edge, level with the deck's slot — Adopted
* **Decision:** A per-pool setting. When it's on, a deck's sideboard copies
  get its mark on the **right edge at the same height** as its left-edge
  slot (`d12.sb`). A copy that's main in one deck and sideboard in another
  carries one of each. Within a deck, main copies come first: with 1 main and
  2 sideboard Pyroblasts, copy 1 is main and copies 2–3 are sideboard. For a
  split deck whose variants disagree on a copy, it gets both marks.
* **Why:** Players have long marked sideboard sleeves to reset decks between
  games. "Sideboard" belongs to a deck's use of a copy, not to the copy, so
  a single shared "SB" mark can't work once cards are shared.
* **Limits:** A pool with sideboard marks has 30 deck slots (the right edge
  is taken). Turning it on is refused while any deck in the pool uses a
  right-edge slot.
* **To change:** `pools.sideboard_marks`; planner logic in
  `logic.desired_copies()`.

---

## 3. Software architecture

### D13. Self-hosted single container: FastAPI + SQLite + vanilla JS — Adopted
* **Decision:** One Python process serves the API and static files. Data lives
  in one SQLite file in `/data`. No build step for the front end.
* **Why:** Runs anywhere Docker runs (home server, AWS), backups are one file,
  and anyone can read and change it. The server also has to fetch from Archidekt
  and CubeCobra, which browsers can't do directly (CORS).
* **Alternative:** A local-first browser app (data in the browser, optional
  cloud sync). It's simpler to host, but can't call deck sites' APIs, and data
  is tied to one browser.
* **Limits:** One collection per instance. No offline/phone-only use without
  reaching the server. SQLite is fine for one person, not for many
  concurrent users.
* **To change:**
  * **Multi-user / multi-collection** (Proposed): add a `collection_id`
    column to every table and scope every query. `TABLES` and `load_*()` in
    `main.py` are the only places that read whole tables.
  * **Postgres:** the SQL is portable apart from `INSERT OR IGNORE/REPLACE`
    and `ON CONFLICT` (both have Postgres equivalents). Wrap `db()` in a small
    adapter.

### D14. Mark ids are short strings — Adopted
* **Decision:** A painted sleeve is a set of mark ids: `d12` (deck 12's main
  mark), `d12.sb` (its sideboard mark, D18) and `d12.v3` (its variant 3, D4).
* **Why:** Marks come in three kinds now. Text ids stay readable in backups
  and are easy to extend.
* **Limits:** Painted marks reference deck ids, so **a deck id must never be
  reused**. SQLite would hand out the id of the most recently deleted deck
  again, so `_new_deck_id()` keeps a counter that only goes up
  (`settings.deck_seq`). Any new way of creating decks must use it.
* **To change:** Only `logic.parse_mark()` (Python) and `splitMark()` /
  `markInfo()` (JS) decode ids. A new kind needs a new suffix there and a
  position rule in `markInfo()`.
* **History:** v0 used integers: deck id, or −(deck × 100 + variant).
  `migrate()` converts old painted data with `logic.upgrade_mark()`.

### D15. Importers are small parse functions with tolerant parsing — Adopted
* **Decision:** Each source is a `parse_*` function in `logic.py` (pure, unit
  tested) plus a fetch wrapper in `main.py`. Archidekt and CubeCobra APIs are
  undocumented, so parsers accept several shapes, and every import has a
  paste/CSV fallback.
* **To change (Proposed):** Formalise an `Importer` interface
  (`match(url) -> bool`, `fetch(ref) -> {name, format, cards}`) and a registry,
  so Moxfield, Deckstats or TappedOut are one file each. Note Moxfield blocks
  unauthenticated API use, so it may need the paste route.

### D16. Auth is optional basic auth; no accounts — Adopted
* **Why:** It's a personal tool on a LAN or behind a reverse proxy.
* **To change:** Put it behind an identity-aware proxy (Cloudflare Access,
  Tailscale, an ALB with OIDC) rather than building accounts in. If multi-user
  lands (D13), read the user from a trusted proxy header.

### D17. Container starts as root, fixes /data ownership, then drops root — Adopted
* **Decision:** `entrypoint.py` runs as root just long enough to give the data
  folder to `PUID:PGID` (default 10001), then runs the server as that user.
  With `docker run --user`, it only checks the folder is writable and explains
  the fix if not.
* **Why:** Docker creates bind-mounted host folders (`./data`) owned by root,
  so a container that starts as a non-root user can't create its database.
  v0 shipped with `USER edgemark` and failed on first run with
  "unable to open database file".
* **Limits:** It changes the ownership of files in the mounted folder. Don't
  mount a folder that other programs need to own.
* **To change:** For rootless or Kubernetes setups that forbid starting as
  root, run with `--user` and a pre-owned volume (or an `fsGroup`). The
  entrypoint supports that path.

### D19. Primary setup: a sibling service to Spellbook; solo still supported — Proposed
* **Decision:** The first-class, primary setup is Edgemark next to a self-hosted
  [Spellbook](https://github.com/KyleDerZweite/spellbook) instance, which
  becomes its source of owned printings and decklists. Running Edgemark on its
  own stays a supported setup. Edgemark runs as its own container
  next to Spellbook's containers in one Docker Compose stack and talks to it
  only over Spellbook's versioned HTTP API (`/api/v…/mtg/…`, its ADR-0028).
  Edgemark keeps its own SQLite file for marks, pools, painted state and the
  guide (D7, D13). Spellbook never depends on Edgemark. Solo, or when
  Spellbook can't be reached, Edgemark works as it does today, importing decks
  from Archidekt and the other importers (D15). New features must keep working
  solo, perhaps with less data, rather than requiring Spellbook.
* **Why:** Spellbook is an actively maintained, AGPL-3.0 (license-compatible),
  self-hosted inventory and deck builder whose backend is moving to Python. It
  already tracks owned printings and compares deck needs with inventory, which
  is the input Edgemark's planner needs. Spellbook has no plugin or extension
  system, so a sibling service is the least invasive way to combine them. Our
  fork of Spellbook can stay identical to upstream, which keeps upstream
  updates painless.
* **Alternatives:**
  * Merge Edgemark into a Spellbook fork. One app and one database, but every
    upstream change has to be merged by hand, and Spellbook changes quickly.
  * Contribute sleeve marking upstream as a Spellbook feature. Possible later
    if the maintainer wants it. It would need to follow Spellbook's
    architecture and review process.
* **Limits:** Depends on Spellbook's API staying stable. The versioned API was
  still in an unmerged pull request (PR 276) when this was written.
  Automation needs a non-interactive login (O5).
* **To change:** Add a Spellbook importer alongside the others (D15, ideally
  via the proposed `Importer` interface) and a `spellbook_url` setting. The
  stack layout goes in an example `docker-compose.spellbook.yml`.
* **Upstream candidates:** API tokens (O5), Archidekt import (already planned
  in Spellbook's specification), and Old School and Middle School formats. Each
  one accepted upstream is one less thing our fork carries.

---

## 4. Open questions

* **O1. Tournament use.** Thin paint on the card-face side of an inner sleeve
  adds no thickness and isn't visible from the back. Players report judges
  accepting it for sideboard and cube marks, but it's the head judge's call
  under the Magic Tournament Rules on marked cards. Bottom-edge variant marks
  and right-edge sideboard marks are the same kind of mark on the same face. Before recommending Edgemark
  for sanctioned play, test it with a judge.
* **O2. Reordering slots.** Grouping slots by colour identity or putting
  most-played decks in the easiest-to-see slots is handy. Edgemark lets you
  change a slot in Edit, but every painted mark for that deck then shows as
  clear-and-repaint. Should "move slot" be a planned migration with its own
  work list?
* **O3. Change history.** Edgemark shows only the current diff, not what changed
  over time. Do we want a timeline (the `log`
  table exists but isn't shown)?
* **O4. Spare copies.** Sharing frees up duplicates that can be traded or
  sold. Edgemark's Collection tab knows `owned − need`. Add a "spares" view?
* **O5. Logging in to Spellbook (D19).** Spellbook only has interactive
  username and password logins, and no API tokens. A background service like
  Edgemark, or a deck sync job, needs a token or service account. Propose API
  tokens upstream, or keep a dedicated Spellbook account's session for
  Edgemark?
* **O6. Physical storage overlap (D19).** Spellbook has accepted physical boxes
  that hold quantity allocations per box, tied to its card sorter (its
  ADR-0030). That overlaps Edgemark's card locations and pools. Should
  Edgemark read box contents from Spellbook instead of keeping its own, and
  should pools map onto Spellbook's physical boxes?
