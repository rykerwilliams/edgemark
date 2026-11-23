# Edgemark design decisions

Edgemark started as a whole-collection take on [PRISM](https://prismmtg.com),
a sleeve-marking system built for Commander. This file records each design
choice: what we decided, why, what PRISM does, what the choice limits, and
where in the code to change it. Treat it as a decision log. When a decision
changes, update its entry (keep the old reasoning under "History") rather than
deleting it.

Status values: **Adopted** (in the code), **Proposed** (agreed direction, not
built), **Open** (needs a decision).

---

## 1. Physical marking model

### D1. Marks go on the Perfect Fit inner sleeve, double-sleeved — Adopted
* **Decision:** Paint the inner sleeve on the card-face side, let it dry fully,
  then put it in an outer sleeve. The card itself is never marked.
* **Why:** Same as PRISM. The outer sleeve protects the paint, and cards keep
  their value, which matters for signed and old cards.
* **Limits:** Every deck that shares a copy must use **the same outer sleeve**.
  Otherwise a shared card stands out when it moves into another deck. Edgemark
  doesn't model or enforce sleeve type.
* **To change:** A `sleeve` attribute on pools (planned in D9) would let the app
  warn when decks in one pool use different outer sleeves.

### D2. Slot = fixed position on the top edge; 24 per side, 48 total — Adopted
* **Decision:** Each deck owns one slot. Slots 1–24 are on side A (card
  face), 25–48 on side B (card back). Slot 1 is at the starting corner chosen in
  Settings (top-left or top-right).
* **Why:** Matches PRISM's 48-slot layout and fits a 64 mm sleeve at a
  2.6 mm pitch with a 1.5 mm window, readable with a fine paint pen.
* **PRISM:** 48 decks per PRISM, 96 with dot splits.
* **Limits:**
  * Hard cap of `2 × slots_per_side` decks per database. A big cube import can
    use up slots fast (one per tag).
  * Slots are **global**, even though decks in different pools never share
    a sleeve, so in principle they could reuse slots.
  * Changing the starting corner or `slots_per_side` after painting
    invalidates every painted mark. The app warns but can't migrate paint.
* **To change:**
  * `slots_per_side` is a setting. The printed guide's pitch is a parameter in
    `guide/edgemark_guide.scad` and `make_guide.py`. Change both together.
  * **Per-pool slot namespaces** (Proposed): let pools reuse slots, so you get
    48 per pool instead of 48 in total. Needs: a `UNIQUE(pool, slot)` rule
    instead of a global unique slot, the slot picker filtered by pool, and the
    print legend grouped by pool. Risk: a card that moves between pools by
    mistake would read as the wrong deck. Mitigate with a pool colour band
    (see D4).

### D3. Colour is a pen colour and doesn't identify the deck — Adopted
* **Decision:** Position (slot) identifies the deck. Colour is a second cue
  that makes a box easier to scan.
* **Why:** Pen sets have about 12–24 usable colours, far fewer than 48 decks.
  Relying on position is robust and colour-blind friendly.
* **PRISM:** Defaults to colours found in standard paint pen sets, and advises
  avoiding metallic colours (they rub onto outer sleeves) and black (invisible
  on most card backs).
* **Limits:** Two decks can share a colour, so you must read the position.
* **To change:** `settings.pens` holds the palette. A "colour-unique" mode could
  refuse duplicate colours when the palette allows it.

### D4. Variant marks are dots under the stripe, in the same window — Adopted
* **Decision:** A split deck keeps one slot. A card in **all** variants gets the
  stripe only. A card in **some** variants also gets a dot per variant, in the
  lower half of the same window, coloured by variant. Max 8 variants.
* **Why:** Uses no extra slots, works with the 24-window guide as printed,
  and reads at a glance: "stripe + yellow dot = Fling build."
* **PRISM:** Two methods: **Stripes** (side B marks on the opposite edge, 2–8
  variants) and **Dots** (coloured dots beside the side A stripe, exactly 2
  variants).
* **Limits:** Variant identity depends on dot colour alone, and the dot shares
  window space with the stripe (needs a fine tip). No side-B stripe option.
* **To change:** Mark shapes come from one place:
  * Backend: `logic.variant_mark()` / `split_mark()`.
  * Frontend: `markInfo()` and the `m.dot` branch of `sleeveSVG()`.
  Adding a "stripe on side B" variant style means a per-deck `variant_style`
  field and teaching `markInfo()` to return a side-B position. The planner
  (`desired_copies`) doesn't care how a mark is drawn.

### D5. The printed guide is a two-part magnetic jig — Adopted
* **Decision:** A base with a sleeve pocket and top stop, plus a window plate
  located by two pegs and held by optional 6×2 mm magnets. Long windows at
  4/8/12/16/20/24, round markers at slots 1 and 13, engraved numbers.
* **Why:** Open-source take on PRISM's Spirit Guide (an alignment tool
  with magnetic hold for one-handed marking). Original geometry, no PRISM
  branding.
* **Limits:** Sized for 64 mm Perfect Fit inners. One plate per starting corner.
* **To change:** All dimensions are parameters at the top of
  `guide/edgemark_guide.scad`.

---

## 2. Sharing and copy planning

### D6. Pools: decks that are never sleeved at the same time share copies — Adopted
* **Decision:** Every deck belongs to a named pool. Within a pool, copy *i* of
  a card carries the stripe of every deck that runs at least *i* copies
  (quantity tiers). A pool needs `max(qty)` copies. A **dedicated** deck is a
  pool of one.
* **Why:** PRISM assumes one Commander table, so everything shares. A whole
  collection includes decks you play side by side (two Old School decks at an
  event, a cube while a constructed deck is built), signed decks that must keep
  specific copies, and different formats.
* **PRISM:** One shared pool per PRISM, with an optional dedicated commander
  copy. Separate collections need separate PRISMs.
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
  fall out of one mechanism, instead of PRISM-style special cases (a separate
  Marks to Clear list that "cannot be rebuilt").
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
* **PRISM:** Same idea: tokens keep their deck selection until changed, and a
  double-sided token gets every needing deck's mark.

### D12. Cube tags become decks in one pool — Adopted
* **Decision:** Each ticked CubeCobra tag becomes a deck (with its own slot) in
  pool `Cube: <name>`, plus an optional "other" deck for untagged cards, or the
  whole cube as one deck.
* **PRISM:** Each ticked tag becomes a deck with its own stripe, in a *new*
  PRISM.
* **Limits:** Uses one slot per tag (see D2). No re-sync for cubes yet.
* **To change:** Store `source='cubecobra'` with the tag list, and add a sync
  path like Archidekt's. Per-pool slots (D2) would remove the slot pressure.

---

## 3. Software architecture

### D13. Self-hosted single container: FastAPI + SQLite + vanilla JS — Adopted
* **Decision:** One Python process serves the API and static files. Data lives
  in one SQLite file in `/data`. No build step for the front end.
* **Why:** Runs anywhere Docker runs (home server, AWS), backups are one file,
  and anyone can read and change it. The server also has to fetch from Archidekt
  and CubeCobra, which browsers can't do directly (CORS).
* **PRISM:** Local-first in the browser, works without an account, cloud
  sync for members, JSON export any time.
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

### D14. Mark ids are integers: deck id, or −(deck × 100 + variant) — Adopted
* **Decision:** A mark set is a `frozenset[int]`. Positive = deck stripe,
  negative = variant dot.
* **Why:** Keeps the old painted data valid when variants arrived, and keeps
  sets sortable and JSON-friendly.
* **Limits:** At most 99 variant indexes per deck (capped at 8 live).
  Painted marks reference deck ids, so **a deck id must never be reused**.
  SQLite would hand out the id of the most recently deleted deck again, so
  `_new_deck_id()` keeps a counter that only goes up (`settings.deck_seq`). Any
  new way of creating decks must use it.
* **To change (Proposed):** If marks gain more kinds (side-B stripes, pool
  bands, printing marks), switch to string mark ids like `d12`, `d12.v3`,
  `p4`, with a one-time migration of `cards.physical`. Only
  `variant_mark/split_mark` (Python) and `splitMark/markInfo` (JS) decode ids.

### D15. Importers are small parse functions with tolerant parsing — Adopted
* **Decision:** Each source is a `parse_*` function in `logic.py` (pure, unit
  tested) plus a fetch wrapper in `main.py`. Archidekt and CubeCobra APIs are
  undocumented, so parsers accept several shapes, and every import has a
  paste/CSV fallback.
* **PRISM:** Imports Moxfield or Archidekt URLs, or manual entry.
* **To change (Proposed):** Formalise an `Importer` interface
  (`match(url) -> bool`, `fetch(ref) -> {name, format, cards}`) and a registry,
  so Moxfield, Deckstats or TappedOut are one file each. Note Moxfield blocks
  unauthenticated API use, so it may need the paste route.

### D16. Auth is optional basic auth; no accounts — Adopted
* **Why:** It's a personal tool on a LAN or behind a reverse proxy.
* **To change:** Put it behind an identity-aware proxy (Cloudflare Access,
  Tailscale, an ALB with OIDC) rather than building accounts in. If multi-user
  lands (D13), read the user from a trusted proxy header.

---

## 4. Open questions

* **O1. Tournament use.** PRISM's FAQ says sleeve-edge marks are tournament
  legal under MTR 3.12, on the basis that they add no thickness and can't be
  identified without seeing the card's face. Our variant dots sit lower on the
  sleeve and might be more visible from the back. Before recommending Edgemark
  for sanctioned play, test it with a judge.
* **O2. Reordering slots.** PRISM lets you move a deck to another slot
  (and reorder several at once, e.g. by colour identity). Edgemark lets you
  change a slot in Edit, but every painted mark for that deck then shows as
  clear-and-repaint. Should "move slot" be a planned migration with its own
  work list?
* **O3. Change history.** PRISM's "Track Changes" shows what changed when a deck
  is added. Edgemark shows only the current diff. Do we want a timeline (the `log`
  table exists but isn't shown)?
* **O4. Spare copies.** PRISM's FAQ suggests selling copies that sharing frees
  up. Edgemark's Collection tab knows `owned − need`. Add a "spares" view?
