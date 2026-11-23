"""Pure logic for Edgemark: decklist parsing, mark planning and diffing.

Model
-----
* A deck has a slot (1..N) and a colour. Its mark is that colour at that slot.
* A deck belongs to a *pool*. Decks in the same pool share physical copies
  (you never sleeve two decks of one pool at the same time). Decks in
  different pools - or decks flagged ``dedicated`` - get their own copies.
* For one card in one pool, copy i (1-based) carries the marks of every deck
  in that pool that runs at least i copies (quantity tiers).  So a pool needs
  max(qty) copies, and a dedicated deck needs qty copies with only its mark.
* "Physical" state is what is actually painted: a list of mark-sets, one per
  marked sleeve.  The diff between physical and desired gives the work to do.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

BASICS = {
    "plains", "island", "swamp", "mountain", "forest", "wastes",
    "snow-covered plains", "snow-covered island", "snow-covered swamp",
    "snow-covered mountain", "snow-covered forest", "snow-covered wastes",
}


def norm(name: str) -> str:
    """Canonical card key: case-folded, single spaces, front face kept whole."""
    name = re.sub(r"\s+", " ", name.strip())
    name = re.sub(r"\s*//\s*", " // ", name)
    return name.casefold()


def is_basic(name: str) -> bool:
    return norm(name) in BASICS


# --------------------------------------------------------------- parsing

_LINE = re.compile(
    r"^\s*(?:SB:\s*)?(?P<qty>\d+)\s*x?\s+(?P<name>.+?)\s*$", re.IGNORECASE
)
_SET_TAIL = re.compile(
    r"\s+(\([A-Za-z0-9]{2,6}\)|\[[A-Za-z0-9]{2,6}\])(\s+[A-Za-z0-9\-★]+)?(\s+\*[A-Z]+\*)*\s*$"
)
_TAGS = re.compile(r"\s+(\*[A-Za-z]+\*|\^[^^]*\^|#\S+)")
_SIDE_HEAD = re.compile(r"^\s*(//\s*)?(sideboard|side board|sb)\s*:?\s*$", re.I)
_SKIP_HEAD = re.compile(r"^\s*(//\s*)?(maybeboard|maybe|considering|tokens?)\s*:?\s*$", re.I)
_MAIN_HEAD = re.compile(
    r"^\s*(//\s*)?(main ?deck|deck|mainboard|commander|companion|creatures?|"
    r"lands?|spells?|instants?|sorcer(y|ies)|artifacts?|enchantments?|planeswalkers?)\s*(\(\d+\))?:?\s*$",
    re.I,
)


def clean_name(raw: str) -> str:
    name = raw
    name = _SET_TAIL.sub("", name)
    name = _TAGS.sub("", name)
    name = re.sub(r"\s+\(\w{2,6}\)\s*\d*$", "", name)  # leftover "(SET) 12"
    return name.strip().strip('"')


def parse_decklist(text: str) -> list[dict]:
    """Parse plain text / .dec / .dek / .mwDeck / MTGO / Arena style lists.

    Returns [{name, qty, board}] with board in {"main", "side"}; maybeboard and
    token sections are dropped.  A blank line after a main section switches to
    the sideboard only for MTGO-style lists with no headers at all.
    """
    text = text.replace("\r\n", "\n")
    if text.lstrip().startswith("<?xml") or "<Cards" in text:
        return _parse_dek_xml(text)
    out: dict[tuple[str, str], dict] = {}
    board = "main"
    saw_header = False
    seen_cards = False
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            if seen_cards and not saw_header and board == "main":
                board = "side_pending"
            continue
        if _SIDE_HEAD.match(s):
            board, saw_header = "side", True
            continue
        if _SKIP_HEAD.match(s):
            board, saw_header = "skip", True
            continue
        if _MAIN_HEAD.match(s):
            board, saw_header = "main", True
            continue
        if s.startswith(("//", "#")) or s.lower().startswith(("name ", "about")):
            continue
        is_sb = s.upper().startswith("SB:")
        s = re.sub(r"^\s*\[[^\]]*\]\s*", "", s)  # mwDeck "[SET]" prefix after qty handled below
        m = _LINE.match(line.strip())
        if not m:
            continue
        name = clean_name(re.sub(r"^\[[^\]]*\]\s*", "", m.group("name")))
        if not name:
            continue
        b = board
        if b == "side_pending":
            b = board = "side"
        if is_sb:
            b = "side"
        if b == "skip":
            continue
        seen_cards = True
        key = (norm(name), b)
        if key in out:
            out[key]["qty"] += int(m.group("qty"))
        else:
            out[key] = {"name": name, "qty": int(m.group("qty")), "board": b}
    return [c for c in out.values() if c["qty"] > 0]


def _parse_dek_xml(text: str) -> list[dict]:
    out: dict[tuple[str, str], dict] = {}
    for m in re.finditer(r"<Cards\b([^>]*)/?>", text):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        name = attrs.get("Name")
        if not name:
            continue
        b = "side" if attrs.get("Sideboard", "false").lower() == "true" else "main"
        key = (norm(name), b)
        q = int(attrs.get("Quantity", "1") or 1)
        if key in out:
            out[key]["qty"] += q
        else:
            out[key] = {"name": name, "qty": q, "board": b}
    return list(out.values())


def parse_collection(text: str) -> list[dict]:
    """'4 Brainstorm' lines, or CSV with Quantity/Count + Name columns."""
    lines = [l for l in text.replace("\r\n", "\n").split("\n") if l.strip()]
    if not lines:
        return []
    head = [h.strip().strip('"').lower() for h in _csv_split(lines[0])]
    qcol = next((i for i, h in enumerate(head) if h in ("quantity", "qty", "count")), None)
    ncol = next((i for i, h in enumerate(head) if h in ("name", "card name", "card")), None)
    totals: dict[str, dict] = {}
    if qcol is not None and ncol is not None:
        for l in lines[1:]:
            cells = _csv_split(l)
            if len(cells) <= max(qcol, ncol):
                continue
            try:
                q = int(cells[qcol].strip().strip('"') or 0)
            except ValueError:
                continue
            _add(totals, cells[ncol].strip().strip('"'), q)
    else:
        for c in parse_decklist(text):
            _add(totals, c["name"], c["qty"])
    return list(totals.values())


def _add(totals, name, q):
    if not name:
        return
    k = norm(name)
    if k in totals:
        totals[k]["qty"] += q
    else:
        totals[k] = {"name": name, "qty": q}


def _csv_split(line: str) -> list[str]:
    cells, cur, q = [], "", False
    for ch in line:
        if ch == '"':
            q = not q
            cur += ch
        elif ch == "," and not q:
            cells.append(cur)
            cur = ""
        else:
            cur += ch
    cells.append(cur)
    return cells


def parse_archidekt(data: dict) -> dict:
    """Turn an Archidekt /api/decks/<id>/ payload into {name, format, cards}.

    Tolerant of field drift: maybeboard (and any category excluded from the
    deck other than Sideboard) is dropped; Sideboard is kept as board "side".
    """
    cats = {}
    for c in data.get("categories") or []:
        if isinstance(c, dict) and c.get("name"):
            cats[c["name"]] = c.get("includedInDeck", True)
    out: dict[tuple[str, str], dict] = {}
    for entry in data.get("cards") or []:
        card = entry.get("card") or {}
        oracle = card.get("oracleCard") or {}
        name = oracle.get("name") or card.get("name") or entry.get("name")
        if not name:
            continue
        qty = int(entry.get("quantity") or 0)
        ecats = [c if isinstance(c, str) else (c or {}).get("name", "") for c in entry.get("categories") or []]
        lower = [c.lower() for c in ecats]
        if any("maybe" in c for c in lower):
            continue
        if any(c == "sideboard" for c in lower):
            board = "side"
        elif ecats and all(cats.get(c, True) is False for c in ecats):
            continue  # excluded category, e.g. "Considering"
        else:
            board = "main"
        key = (norm(name), board)
        if key in out:
            out[key]["qty"] += qty
        else:
            out[key] = {"name": name, "qty": qty, "board": board}
    fmt = data.get("deckFormat") or data.get("format")
    return {
        "name": data.get("name") or f"Archidekt {data.get('id', '')}".strip(),
        "format": ARCHIDEKT_FORMATS.get(fmt, str(fmt) if fmt is not None else ""),
        "cards": [c for c in out.values() if c["qty"] > 0],
    }


# Archidekt numeric format ids (best known values; unknown ids pass through)
ARCHIDEKT_FORMATS = {
    1: "Standard", 2: "Modern", 3: "Commander", 4: "Legacy", 5: "Vintage",
    6: "Pauper", 7: "Custom", 8: "Frontier", 9: "Future Standard",
    10: "Penny Dreadful", 11: "1v1 Commander", 12: "Duel Commander",
    13: "Brawl", 14: "Oathbreaker", 15: "Pioneer", 16: "Historic",
    17: "Pauper EDH", 18: "Alchemy", 19: "Explorer", 20: "Historic Brawl",
    21: "Gladiator", 22: "Premodern", 23: "PreDH", 24: "Timeless",
    25: "Canadian Highlander",
}


def archidekt_deck_id(text: str) -> str | None:
    m = re.search(r"archidekt\.com/(?:api/)?decks/(\d+)", text)
    if m:
        return m.group(1)
    m = re.fullmatch(r"\s*(\d+)\s*", text)
    return m.group(1) if m else None


# --------------------------------------------------------------- planning

MAX_VARIANTS = 8


def variant_mark(deck_id: int, idx: int) -> int:
    """Mark id for variant `idx` (1..8) of a deck: a dot under the deck's stripe.

    Deck marks are positive deck ids; variant dots are negative so both fit in
    one sortable int set and old saved data stays valid.
    """
    return -(deck_id * 100 + idx)


def split_mark(m: int) -> tuple[int, int]:
    """-> (deck id, variant idx); idx 0 means the deck's own stripe."""
    return (m, 0) if m > 0 else ((-m) // 100, (-m) % 100)


@dataclass
class Deck:
    id: int
    name: str
    slot: int
    color: str
    pool: str = "Main"
    dedicated: bool = False
    active: bool = True
    include_side: bool = True
    cards: list[dict] = field(default_factory=list)  # {name, qty, board, variant?}
    variants: list[dict] = field(default_factory=list)  # [{idx, name, color}]


def deck_needs(deck: Deck, skip_basics: bool) -> dict[str, tuple[str, dict[int, int]]]:
    """norm name -> (display name, {variant idx: qty}) for one deck.

    A deck without variants reports everything under variant 0. Token rows
    (board "token") belong to the whole deck and count for every variant.
    """
    need: dict[str, list] = {}
    tokens: dict[str, list] = {}
    for c in deck.cards:
        if c["board"] == "side" and not deck.include_side:
            continue
        if skip_basics and is_basic(c["name"]):
            continue
        k = norm(c["name"])
        if c["board"] == "token":
            t = tokens.setdefault(k, [c["name"], 0])
            t[1] = max(t[1], c["qty"])
            continue
        v = c.get("variant", 0) if deck.variants else 0
        ent = need.setdefault(k, [c["name"], {}])
        ent[1][v] = ent[1].get(v, 0) + c["qty"]
    idxs = [v["idx"] for v in deck.variants] or [0]
    for k, (disp, q) in tokens.items():
        ent = need.setdefault(k, [disp, {}])
        for v in idxs:
            ent[1][v] = max(ent[1].get(v, 0), q)
    return {k: (v[0], v[1]) for k, v in need.items()}


def desired_copies(decks: list[Deck], skip_basics: bool = True) -> dict[str, dict]:
    """norm name -> {name, copies: [frozenset(mark ids)], pools: {...}}.

    Within a pool, copy i carries the stripe of every deck running >= i copies
    (in any of its variants). For a split deck it also carries the dot of each
    variant running >= i copies, unless every variant does (then the stripe
    alone says it). Copies are ordered most-marks-first so output is stable.
    """
    per_card: dict[str, dict] = {}
    by_id = {d.id: d for d in decks}
    for d in decks:
        if not d.active:
            continue
        for k, (disp, vq) in deck_needs(d, skip_basics).items():
            ent = per_card.setdefault(k, {"name": disp, "groups": {}})
            group = f"__dedicated__{d.id}" if d.dedicated else f"pool:{d.pool}"
            ent["groups"].setdefault(group, {})[d.id] = vq
    result = {}
    for k, ent in per_card.items():
        copies: list[frozenset] = []
        pools = {}
        for g, per_deck in ent["groups"].items():
            top = max(max(vq.values()) for vq in per_deck.values())
            for i in range(1, top + 1):
                marks = set()
                for did, vq in per_deck.items():
                    if max(vq.values()) < i:
                        continue
                    marks.add(did)
                    variants = by_id[did].variants
                    if variants:
                        having = [v["idx"] for v in variants if vq.get(v["idx"], 0) >= i]
                        if len(having) < len(variants):
                            marks.update(variant_mark(did, x) for x in having)
                copies.append(frozenset(marks))
            pools[g] = top
        copies.sort(key=lambda s: (-len(s), sorted(s)))
        result[k] = {"name": ent["name"], "copies": copies, "pools": pools}
    return result


# --------------------------------------------------------------- cubes

def parse_cubecobra(data: dict) -> dict:
    """CubeCobra cubeJSON -> {name, cards: [{name, tags}]} (mainboard only).

    Handles both the current shape (cards.mainboard) and the older flat list.
    """
    cards = data.get("cards") or []
    if isinstance(cards, dict):
        cards = cards.get("mainboard") or cards.get("Mainboard") or []
    out = []
    for c in cards:
        if not isinstance(c, dict):
            continue
        if str(c.get("board", "")).lower().startswith("maybe") or c.get("maybeboard") in (True, "true"):
            continue
        det = c.get("details") or {}
        name = c.get("name") or det.get("name") or det.get("name_lower")
        if not name:
            continue
        tags = [str(t).strip() for t in (c.get("tags") or []) if str(t).strip()]
        out.append({"name": name, "tags": tags})
    return {"name": data.get("name") or data.get("shortId") or "Cube", "cards": out}


def parse_cube_csv(text: str) -> dict:
    """CubeCobra CSV export (name, ..., maybeboard, ..., tags, ...)."""
    lines = [l for l in text.replace("\r\n", "\n").split("\n") if l.strip()]
    if not lines:
        return {"name": "Cube", "cards": []}
    head = [h.strip().strip('"').lower() for h in _csv_split(lines[0])]
    if "name" not in head:
        # plain list: no tags available
        return {"name": "Cube", "cards": [{"name": c["name"], "tags": []} for c in parse_decklist(text) for _ in range(c["qty"])]}
    ni = head.index("name")
    ti = head.index("tags") if "tags" in head else None
    mi = head.index("maybeboard") if "maybeboard" in head else None
    out = []
    for l in lines[1:]:
        cells = [x.strip().strip('"') for x in _csv_split(l)]
        if len(cells) <= ni or not cells[ni]:
            continue
        if mi is not None and len(cells) > mi and cells[mi].lower() == "true":
            continue
        tags = []
        if ti is not None and len(cells) > ti and cells[ti]:
            tags = [t.strip() for t in re.split(r"[;,]", cells[ti]) if t.strip()]
        out.append({"name": cells[ni], "tags": tags})
    return {"name": "Cube", "cards": out}


def cube_tag_lists(cube: dict, tags: list[str], untagged_name: str | None = None) -> dict[str, list[dict]]:
    """tag -> decklist [{name, qty, board}] for the chosen tags.

    With untagged_name set, cards that carry none of the chosen tags become one
    more list under that name, so every card in the cube gets at least one mark.
    """
    chosen = {t.casefold(): t for t in tags}
    lists: dict[str, dict] = {t: {} for t in tags}
    rest: dict = {}
    for c in cube["cards"]:
        hit = [chosen[t.casefold()] for t in c["tags"] if t.casefold() in chosen]
        targets = [lists[h] for h in dict.fromkeys(hit)] or ([rest] if untagged_name else [])
        for tgt in targets:
            k = norm(c["name"])
            if k in tgt:
                tgt[k]["qty"] += 1
            else:
                tgt[k] = {"name": c["name"], "qty": 1, "board": "main"}
    out = {t: list(v.values()) for t, v in lists.items() if v}
    if untagged_name and rest:
        out[untagged_name] = list(rest.values())
    return out


def cubecobra_id(text: str) -> str | None:
    m = re.search(r"cubecobra\.com/cube/(?:[a-z]+/)*([A-Za-z0-9_\-]+)", text)
    if m:
        return m.group(1)
    m = re.fullmatch(r"\s*([A-Za-z0-9_\-]{3,})\s*", text)
    return m.group(1) if m else None


def diff_card(physical: list[frozenset], desired: list[frozenset]) -> list[dict]:
    """Match painted sleeves to desired sleeves; return grouped actions.

    Each action: {from: [ids], to: [ids], add: [ids], clear: [ids], count}.
    from == [] means "take a fresh, unmarked copy"; to == [] means "this
    sleeve no longer serves any deck: clear it all and return the copy".
    """
    phys = list(physical)
    used = [False] * len(phys)
    pairs = []
    for want in desired:  # desired already sorted most-marks-first
        best, best_score = None, None
        for i, have in enumerate(phys):
            if used[i]:
                continue
            score = (len(have & want), -len(have ^ want))
            if best is None or score > best_score:
                best, best_score = i, score
        if best is not None and (best_score[0] > 0 or not want):
            used[best] = True
            pairs.append((phys[best], want))
        else:
            pairs.append((frozenset(), want))
    for i, have in enumerate(phys):
        if not used[i]:
            pairs.append((have, frozenset()))
    groups: Counter = Counter()
    for have, want in pairs:
        if have == want:
            continue
        groups[(tuple(sorted(have)), tuple(sorted(want)))] += 1
    actions = []
    for (have, want), n in groups.items():
        hs, ws = set(have), set(want)
        actions.append({
            "from": list(have), "to": list(want),
            "add": sorted(ws - hs), "clear": sorted(hs - ws), "count": n,
        })
    actions.sort(key=lambda a: (not a["to"], -len(a["to"]), a["to"]))
    return actions


def apply_action(physical: list[frozenset], frm: list[int], to: list[int], count: int) -> list[frozenset]:
    """Record that `count` sleeves went from mark-set `frm` to `to`."""
    phys = list(physical)
    f, t = frozenset(frm), frozenset(to)
    done = 0
    if f:
        for i, have in enumerate(phys):
            if done >= count:
                break
            if have == f:
                phys[i] = t
                done += 1
    else:
        for _ in range(count):
            phys.append(t)
        done = count
    return [p for p in phys if p]


def batches(copies: list[frozenset]) -> list[dict]:
    c = Counter(copies)
    return sorted(
        ({"marks": sorted(k), "count": n} for k, n in c.items()),
        key=lambda b: (-len(b["marks"]), b["marks"]),
    )


def overlap_matrix(decks: list[Deck], skip_basics: bool = True) -> dict:
    """Count of distinct shared cards between every pair of active decks."""
    act = [d for d in decks if d.active]
    sets = {d.id: {k for k, (_, vq) in deck_needs(d, skip_basics).items() if max(vq.values()) > 0} for d in act}
    ids = [d.id for d in act]
    return {
        "decks": ids,
        "matrix": [[len(sets[a] & sets[b]) for b in ids] for a in ids],
    }
