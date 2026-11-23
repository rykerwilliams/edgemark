"""Edgemark server: FastAPI + SQLite. Run: uvicorn app.main:app --host 0.0.0.0 --port 8080"""
from __future__ import annotations

import base64
import json
import os
import secrets
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import logic

DB_PATH = Path(os.environ.get("EDGEMARK_DB", "/data/edgemark.db"))
AUTH = os.environ.get("EDGEMARK_AUTH", "")  # "user:password" turns on basic auth
STATIC = Path(__file__).parent / "static"
UA = {"User-Agent": "Edgemark/1.0 (personal sleeve-marking tool)"}

@asynccontextmanager
async def lifespan(_app):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as con:
        con.executescript(SCHEMA)
        migrate(con)
    yield


app = FastAPI(title="Edgemark", lifespan=lifespan)
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS decks(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, format TEXT DEFAULT '',
  pool TEXT DEFAULT 'Main', dedicated INTEGER DEFAULT 0, active INTEGER DEFAULT 1,
  include_side INTEGER DEFAULT 1, slot INTEGER, color TEXT DEFAULT '#d33',
  source TEXT DEFAULT 'paste', source_id TEXT DEFAULT '', synced REAL, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS deck_cards(
  deck_id INTEGER, name TEXT, qty INTEGER, board TEXT DEFAULT 'main');
CREATE TABLE IF NOT EXISTS cards(
  key TEXT PRIMARY KEY, name TEXT, owned INTEGER, location TEXT DEFAULT '',
  notes TEXT DEFAULT '', physical TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS swaps(
  id INTEGER PRIMARY KEY, deck_id INTEGER, out_name TEXT, in_name TEXT,
  qty INTEGER DEFAULT 1, status TEXT DEFAULT 'queued', created REAL, applied REAL, variant INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS log(id INTEGER PRIMARY KEY, at REAL, text TEXT);
CREATE TABLE IF NOT EXISTS deck_variants(
  deck_id INTEGER, idx INTEGER, name TEXT, color TEXT,
  source TEXT DEFAULT 'paste', source_id TEXT DEFAULT '', synced REAL,
  PRIMARY KEY(deck_id, idx));
CREATE TABLE IF NOT EXISTS tokens(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, back TEXT DEFAULT '',
  qty INTEGER DEFAULT 1, deck_ids TEXT DEFAULT '[]', notes TEXT DEFAULT '');
"""
TABLES = ("decks", "deck_cards", "deck_variants", "tokens", "cards", "swaps", "settings")


def migrate(con):
    cols = {r[1] for r in con.execute("PRAGMA table_info(deck_cards)")}
    if "variant" not in cols:
        con.execute("ALTER TABLE deck_cards ADD COLUMN variant INTEGER DEFAULT 0")
    cols = {r[1] for r in con.execute("PRAGMA table_info(swaps)")}
    if "variant" not in cols:
        con.execute("ALTER TABLE swaps ADD COLUMN variant INTEGER DEFAULT 0")

DEFAULT_SETTINGS = {
    "start_corner": "top-left",  # where slot 1 sits on side A
    "slots_per_side": 24,
    "skip_basics": True,
    "locations": ["Shared box", "Binder", "Bulk", "Out for signing"],
    "pens": ["#e53935", "#fb8c00", "#fdd835", "#43a047", "#00acc1", "#1e88e5",
             "#5e35b1", "#d81b60", "#ffffff", "#8d6e63", "#c0ca33", "#ff80ab"],
}


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    if AUTH:
        h = request.headers.get("authorization", "")
        ok = False
        if h.lower().startswith("basic "):
            try:
                ok = secrets.compare_digest(base64.b64decode(h[6:]).decode(), AUTH)
            except Exception:
                ok = False
        if not ok:
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Edgemark"'})
    return await call_next(request)


# ------------------------------------------------------------------ helpers

def get_settings(con) -> dict:
    s = dict(DEFAULT_SETTINGS)
    for r in con.execute("SELECT key, value FROM settings"):
        if r["key"] in DEFAULT_SETTINGS:
            s[r["key"]] = json.loads(r["value"])
    return s


def load_variants(con) -> dict[int, list[dict]]:
    out: dict[int, list] = {}
    for r in con.execute("SELECT * FROM deck_variants ORDER BY deck_id, idx"):
        out.setdefault(r["deck_id"], []).append(dict(r))
    return out


def load_tokens(con) -> list[dict]:
    out = []
    for r in con.execute("SELECT * FROM tokens ORDER BY name"):
        t = dict(r)
        t["deck_ids"] = json.loads(t["deck_ids"] or "[]")
        t["full_name"] = f"{t['name']} // {t['back']}" if t["back"] else t["name"]
        out.append(t)
    return out


def load_decks(con) -> list[logic.Deck]:
    cards: dict[int, list] = {}
    for r in con.execute("SELECT deck_id, name, qty, board, variant FROM deck_cards"):
        cards.setdefault(r["deck_id"], []).append(
            {"name": r["name"], "qty": r["qty"], "board": r["board"], "variant": r["variant"] or 0})
    for t in load_tokens(con):
        for did in t["deck_ids"]:
            cards.setdefault(did, []).append({"name": t["full_name"], "qty": t["qty"], "board": "token", "variant": 0})
    variants = load_variants(con)
    return [
        logic.Deck(id=r["id"], name=r["name"], slot=r["slot"] or 0, color=r["color"],
                   pool=r["pool"] or "Main", dedicated=bool(r["dedicated"]),
                   active=bool(r["active"]), include_side=bool(r["include_side"]),
                   cards=cards.get(r["id"], []),
                   variants=[{"idx": v["idx"], "name": v["name"], "color": v["color"]} for v in variants.get(r["id"], [])])
        for r in con.execute("SELECT * FROM decks ORDER BY slot, id")
    ]


def load_cards(con) -> dict[str, dict]:
    out = {}
    for r in con.execute("SELECT * FROM cards"):
        d = dict(r)
        d["physical"] = [frozenset(x) for x in json.loads(d["physical"] or "[]")]
        out[r["key"]] = d
    return out


def save_physical(con, key, name, physical):
    payload = json.dumps([sorted(p) for p in physical])
    con.execute(
        "INSERT INTO cards(key, name, physical) VALUES(?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET physical=excluded.physical", (key, name, payload))


def log(con, text):
    con.execute("INSERT INTO log(at, text) VALUES(?,?)", (time.time(), text))


def plan(con, decks=None) -> dict:
    s = get_settings(con)
    decks = decks if decks is not None else load_decks(con)
    want = logic.desired_copies(decks, s["skip_basics"])
    have = load_cards(con)
    rows = []
    for key in sorted(set(want) | {k for k, v in have.items() if v["physical"]}):
        w = want.get(key)
        h = have.get(key, {})
        phys = h.get("physical", [])
        desired = w["copies"] if w else []
        actions = logic.diff_card(phys, desired)
        need = len(desired)
        owned = h.get("owned")
        rows.append({
            "key": key, "name": (w or h)["name"], "need": need, "owned": owned,
            "short": max(0, need - owned) if owned is not None else 0,
            "location": h.get("location", ""), "notes": h.get("notes", ""),
            "pool_card": any(len(c) > 1 for c in desired),
            "batches": logic.batches(desired), "painted": logic.batches(phys),
            "actions": actions, "done": not actions,
        })
    return {"cards": rows, "settings": s}


def deck_json(con, d: sqlite3.Row, variants: dict) -> dict:
    def count(board, v=None):
        q = "SELECT COALESCE(SUM(qty),0) FROM deck_cards WHERE deck_id=? AND board=?"
        args = [d["id"], board]
        if v is not None:
            q += " AND variant=?"
            args.append(v)
        return con.execute(q, args).fetchone()[0]
    out = dict(d)
    vs = variants.get(d["id"], [])
    for v in vs:
        v["main_count"], v["side_count"] = count("main", v["idx"]), count("side", v["idx"])
    if vs:
        out.update(main_count=max(v["main_count"] for v in vs), side_count=max(v["side_count"] for v in vs))
    else:
        out.update(main_count=count("main"), side_count=count("side"))
    out["variants"] = vs
    return out


# ------------------------------------------------------------------ routes

@app.get("/api/state")
def state():
    with db() as con:
        p = plan(con)
        variants = load_variants(con)
        decks = [deck_json(con, d, variants) for d in con.execute("SELECT * FROM decks ORDER BY slot, id")]
        swaps = [dict(r) for r in con.execute("SELECT * FROM swaps ORDER BY id DESC LIMIT 200")]
        return {"decks": decks, "cards": p["cards"], "settings": p["settings"], "swaps": swaps,
                "tokens": load_tokens(con)}


class SettingsIn(BaseModel):
    values: dict


@app.put("/api/settings")
def put_settings(body: SettingsIn):
    with _lock, db() as con:
        for k, v in body.values.items():
            if k in DEFAULT_SETTINGS:
                con.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (k, json.dumps(v)))
        return get_settings(con)


class DeckIn(BaseModel):
    name: str | None = None
    format: str | None = None
    pool: str | None = None
    dedicated: bool | None = None
    active: bool | None = None
    include_side: bool | None = None
    slot: int | None = None
    color: str | None = None
    notes: str | None = None
    decklist: str | None = None  # plain text; replaces the list when given
    archidekt: str | None = None  # URL or id; replaces the list when given
    variant: int | None = None  # which variant's list decklist/archidekt replaces


def _free_slot(con) -> int:
    s = get_settings(con)
    used = {r[0] for r in con.execute("SELECT slot FROM decks WHERE slot IS NOT NULL")}
    for i in range(1, 2 * s["slots_per_side"] + 1):
        if i not in used:
            return i
    raise HTTPException(400, "All slots are taken; free one or raise slots per side in Settings.")


async def fetch_archidekt(ref: str) -> tuple[str, dict]:
    did = logic.archidekt_deck_id(ref)
    if not did:
        raise HTTPException(400, "That doesn't look like an Archidekt deck link or id.")
    async with httpx.AsyncClient(timeout=20, headers=UA, follow_redirects=True) as c:
        r = await c.get(f"https://archidekt.com/api/decks/{did}/")
    if r.status_code == 404:
        raise HTTPException(404, f"Archidekt deck {did} not found (is it private?).")
    if r.status_code >= 400:
        raise HTTPException(502, f"Archidekt answered {r.status_code}.")
    return did, logic.parse_archidekt(r.json())


def _new_deck_id(con) -> int:
    """Deck ids are never reused: painted marks reference them (see DESIGN.md D14)."""
    row = con.execute("SELECT value FROM settings WHERE key='deck_seq'").fetchone()
    seq = max(json.loads(row[0]) if row else 0,
              con.execute("SELECT COALESCE(MAX(id),0) FROM decks").fetchone()[0])
    con.execute("INSERT OR REPLACE INTO settings VALUES('deck_seq', ?)", (json.dumps(seq + 1),))
    return seq + 1


def _replace_cards(con, deck_id, cards, variant=None):
    """Replace a deck's list, or only one variant's list when variant is given."""
    if variant is None:
        con.execute("DELETE FROM deck_cards WHERE deck_id=?", (deck_id,))
    else:
        con.execute("DELETE FROM deck_cards WHERE deck_id=? AND variant=?", (deck_id, variant))
    con.executemany("INSERT INTO deck_cards(deck_id, name, qty, board, variant) VALUES(?,?,?,?,?)",
                    [(deck_id, c["name"], c["qty"], c["board"], variant or 0) for c in cards])


def _has_variants(con, deck_id) -> bool:
    return con.execute("SELECT 1 FROM deck_variants WHERE deck_id=?", (deck_id,)).fetchone() is not None


@app.post("/api/decks")
async def create_deck(body: DeckIn):
    parsed = None
    src, sid = "paste", ""
    if body.archidekt:
        sid, parsed = await fetch_archidekt(body.archidekt)
        src = "archidekt"
    cards = parsed["cards"] if parsed else logic.parse_decklist(body.decklist or "")
    if not cards:
        raise HTTPException(400, "No cards found in that list.")
    with _lock, db() as con:
        slot = body.slot or _free_slot(con)
        if con.execute("SELECT 1 FROM decks WHERE slot=?", (slot,)).fetchone():
            raise HTTPException(400, f"Slot {slot} is already used.")
        pens = get_settings(con)["pens"]
        color = body.color or pens[(slot - 1) % len(pens)]
        cur = con.execute(
            "INSERT INTO decks(id, name, format, pool, dedicated, active, include_side, slot, color, source, source_id, synced, notes)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_new_deck_id(con), body.name or (parsed or {}).get("name") or "New deck", body.format or (parsed or {}).get("format", ""),
             body.pool or "Main", int(bool(body.dedicated)), 1, int(body.include_side is not False),
             slot, color, src, sid, time.time(), body.notes or ""))
        _replace_cards(con, cur.lastrowid, cards)
        log(con, f"Added deck {cur.lastrowid} ({len(cards)} cards)")
        return {"id": cur.lastrowid}


@app.patch("/api/decks/{deck_id}")
async def update_deck(deck_id: int, body: DeckIn):
    parsed = None
    if body.archidekt:
        sid, parsed = await fetch_archidekt(body.archidekt)
    with _lock, db() as con:
        d = con.execute("SELECT * FROM decks WHERE id=?", (deck_id,)).fetchone()
        if not d:
            raise HTTPException(404, "No such deck")
        fields = body.model_dump(exclude_none=True, exclude={"decklist", "archidekt", "variant"})
        split = _has_variants(con, deck_id)
        if split and (parsed or body.decklist is not None) and not body.variant:
            raise HTTPException(400, "This deck is split into variants: edit a variant's list instead.")
        if "slot" in fields and con.execute("SELECT 1 FROM decks WHERE slot=? AND id<>?", (fields["slot"], deck_id)).fetchone():
            raise HTTPException(400, f"Slot {fields['slot']} is already used.")
        for k, v in fields.items():
            con.execute(f"UPDATE decks SET {k}=? WHERE id=?", (int(v) if isinstance(v, bool) else v, deck_id))
        v = body.variant if split else None
        if parsed:
            _replace_cards(con, deck_id, parsed["cards"], v)
            if v:
                con.execute("UPDATE deck_variants SET source='archidekt', source_id=?, synced=? WHERE deck_id=? AND idx=?", (sid, time.time(), deck_id, v))
            else:
                con.execute("UPDATE decks SET source='archidekt', source_id=?, synced=? WHERE id=?", (sid, time.time(), deck_id))
        elif body.decklist is not None:
            cards = logic.parse_decklist(body.decklist)
            if not cards:
                raise HTTPException(400, "No cards found in that list.")
            _replace_cards(con, deck_id, cards, v)
            con.execute("UPDATE decks SET synced=? WHERE id=?", (time.time(), deck_id))
        return {"ok": True}


@app.post("/api/decks/{deck_id}/sync")
async def sync_deck(deck_id: int):
    with db() as con:
        d = con.execute("SELECT * FROM decks WHERE id=?", (deck_id,)).fetchone()
        vs = [dict(r) for r in con.execute("SELECT * FROM deck_variants WHERE deck_id=? AND source='archidekt'", (deck_id,))]
        split = _has_variants(con, deck_id)
    if not d:
        raise HTTPException(404, "No such deck")
    if split:
        if not vs:
            raise HTTPException(400, "None of this deck's variants come from Archidekt.")
        for v in vs:
            _, parsed = await fetch_archidekt(v["source_id"])
            with _lock, db() as con:
                _replace_cards(con, deck_id, parsed["cards"], v["idx"])
                con.execute("UPDATE deck_variants SET synced=? WHERE deck_id=? AND idx=?", (time.time(), deck_id, v["idx"]))
        return {"ok": True, "synced": len(vs)}
    if d["source"] != "archidekt":
        raise HTTPException(400, "Only Archidekt decks can be re-synced.")
    _, parsed = await fetch_archidekt(d["source_id"])
    with _lock, db() as con:
        _replace_cards(con, deck_id, parsed["cards"])
        con.execute("UPDATE decks SET synced=? WHERE id=?", (time.time(), deck_id))
    return {"ok": True}


@app.get("/api/decks/{deck_id}/list")
def deck_list(deck_id: int, variant: int | None = None):
    with db() as con:
        if variant:
            rows = con.execute("SELECT name, qty, board FROM deck_cards WHERE deck_id=? AND variant=? ORDER BY board, name", (deck_id, variant)).fetchall()
        else:
            rows = con.execute("SELECT name, SUM(qty) AS qty, board FROM deck_cards WHERE deck_id=? GROUP BY name, board ORDER BY board, name", (deck_id,)).fetchall()
    main = [f"{r['qty']} {r['name']}" for r in rows if r["board"] == "main"]
    side = [f"{r['qty']} {r['name']}" for r in rows if r["board"] == "side"]
    return PlainTextResponse("\n".join(main + (["", "Sideboard"] + side if side else [])))


@app.delete("/api/decks/{deck_id}")
def delete_deck(deck_id: int):
    # Paint stays on sleeves: those marks surface as "to clear" automatically.
    with _lock, db() as con:
        con.execute("DELETE FROM deck_cards WHERE deck_id=?", (deck_id,))
        con.execute("DELETE FROM deck_variants WHERE deck_id=?", (deck_id,))
        con.execute("DELETE FROM decks WHERE id=?", (deck_id,))
        for t in load_tokens(con):
            if deck_id in t["deck_ids"]:
                con.execute("UPDATE tokens SET deck_ids=? WHERE id=?", (json.dumps([x for x in t["deck_ids"] if x != deck_id]), t["id"]))
        log(con, f"Deleted deck {deck_id}")
    return {"ok": True}


@app.get("/api/archidekt/user/{username}")
async def archidekt_user(username: str):
    """List a user's public decks (tries the known listing endpoints)."""
    urls = [
        f"https://archidekt.com/api/decks/v3/?ownerUsername={username}&pageSize=100",
        f"https://archidekt.com/api/decks/cards/?owner={username}&ownerexact=true&pageSize=100",
    ]
    async with httpx.AsyncClient(timeout=20, headers=UA, follow_redirects=True) as c:
        for u in urls:
            try:
                r = await c.get(u)
                if r.status_code != 200:
                    continue
                data = r.json()
                res = data.get("results", data if isinstance(data, list) else [])
                decks = [{"id": x.get("id"), "name": x.get("name"),
                          "format": logic.ARCHIDEKT_FORMATS.get(x.get("deckFormat"), "")}
                         for x in res if isinstance(x, dict) and x.get("id")]
                if decks:
                    return {"decks": decks}
            except Exception:
                continue
    raise HTTPException(502, "Couldn't list that user's decks. Paste individual deck links instead.")


class CardIn(BaseModel):
    owned: int | None = None
    clear_owned: bool = False
    location: str | None = None
    notes: str | None = None


@app.patch("/api/cards/{key:path}")
def update_card(key: str, body: CardIn):
    with _lock, db() as con:
        con.execute("INSERT OR IGNORE INTO cards(key, name) VALUES(?,?)", (key, key))
        if body.clear_owned:
            con.execute("UPDATE cards SET owned=NULL WHERE key=?", (key,))
        for k in ("owned", "location", "notes"):
            v = getattr(body, k)
            if v is not None:
                con.execute(f"UPDATE cards SET {k}=? WHERE key=?", (v, key))
    return {"ok": True}


class ApplyIn(BaseModel):
    key: str
    name: str
    frm: list[int]
    to: list[int]
    count: int


class BulkIn(BaseModel):
    items: list[ApplyIn]


@app.post("/api/mark")
def mark(body: BulkIn):
    """Check off work: each item says `count` sleeves went from `frm` to `to`."""
    with _lock, db() as con:
        cards = load_cards(con)
        for it in body.items:
            phys = cards.get(it.key, {}).get("physical", [])
            phys = logic.apply_action(phys, it.frm, it.to, it.count)
            save_physical(con, it.key, it.name, phys)
            cards.setdefault(it.key, {})["physical"] = phys
        log(con, f"Checked off {len(body.items)} mark actions")
    return {"ok": True}


class UndoIn(BaseModel):
    key: str
    physical: list[list[int]]


@app.post("/api/mark/set")
def set_physical(body: UndoIn):
    with _lock, db() as con:
        row = con.execute("SELECT name FROM cards WHERE key=?", (body.key,)).fetchone()
        save_physical(con, body.key, row["name"] if row else body.key, [frozenset(p) for p in body.physical if p])
    return {"ok": True}


class CollectionIn(BaseModel):
    text: str
    location: str | None = None
    mode: str = "set"  # set | add


@app.post("/api/collection")
def import_collection(body: CollectionIn):
    items = logic.parse_collection(body.text)
    with _lock, db() as con:
        for it in items:
            k = logic.norm(it["name"])
            con.execute("INSERT OR IGNORE INTO cards(key, name, owned) VALUES(?,?,0)", (k, it["name"]))
            if body.mode == "add":
                con.execute("UPDATE cards SET owned=COALESCE(owned,0)+? WHERE key=?", (it["qty"], k))
            else:
                con.execute("UPDATE cards SET owned=? WHERE key=?", (it["qty"], k))
            if body.location:
                con.execute("UPDATE cards SET location=? WHERE key=?", (body.location, k))
        log(con, f"Collection import: {len(items)} cards ({body.mode})")
    return {"count": len(items)}


class SwapIn(BaseModel):
    deck_id: int
    out_name: str = ""
    in_name: str = ""
    qty: int = 1
    variant: int = 0  # for a split deck: which variant the swap changes


def _swap_decks(con, swaps: list[dict]) -> list[logic.Deck]:
    decks = load_decks(con)
    by_id = {d.id: d for d in decks}
    for sw in swaps:
        d = by_id.get(sw["deck_id"])
        if not d:
            continue
        cards = [dict(c) for c in d.cards]
        if sw["out_name"]:
            left = sw["qty"]
            for c in cards:
                if left and logic.norm(c["name"]) == logic.norm(sw["out_name"]) and c["board"] == "main" and c.get("variant", 0) == sw.get("variant", 0):
                    take = min(left, c["qty"])
                    c["qty"] -= take
                    left -= take
            cards = [c for c in cards if c["qty"] > 0]
        if sw["in_name"]:
            for c in cards:
                if logic.norm(c["name"]) == logic.norm(sw["in_name"]) and c["board"] == "main" and c.get("variant", 0) == sw.get("variant", 0):
                    c["qty"] += sw["qty"]
                    break
            else:
                cards.append({"name": sw["in_name"], "qty": sw["qty"], "board": "main", "variant": sw.get("variant", 0)})
        d.cards = cards
    return decks


@app.post("/api/swaps/preview")
def preview_swap(body: SwapIn):
    with db() as con:
        queued = [dict(r) for r in con.execute("SELECT * FROM swaps WHERE status='queued' ORDER BY id")]
        before = {r["key"]: r for r in plan(con, _swap_decks(con, queued))["cards"]}
        after = {r["key"]: r for r in plan(con, _swap_decks(con, queued + [body.model_dump()]))["cards"]}
        keys = {logic.norm(body.out_name), logic.norm(body.in_name)} - {""}
        out = []
        for k in keys:
            a = after.get(k) or before.get(k)
            if not a:
                continue
            out.append({"name": a["name"], "actions": a["actions"],
                        "before": before.get(k, {}).get("batches", []), "after": a["batches"]})
        no_new = all(not any(x["add"] for x in c["actions"]) for c in out)
        return {"cards": out, "no_new_marks": no_new}


@app.post("/api/swaps")
def queue_swap(body: SwapIn):
    with _lock, db() as con:
        cur = con.execute("INSERT INTO swaps(deck_id, out_name, in_name, qty, variant, created) VALUES(?,?,?,?,?,?)",
                          (body.deck_id, body.out_name, body.in_name, body.qty, body.variant, time.time()))
        return {"id": cur.lastrowid}


@app.post("/api/swaps/{swap_id}/apply")
def apply_swap(swap_id: int):
    with _lock, db() as con:
        sw = con.execute("SELECT * FROM swaps WHERE id=? AND status='queued'", (swap_id,)).fetchone()
        if not sw:
            raise HTTPException(404, "No queued swap with that id")
        d = {x.id: x for x in _swap_decks(con, [dict(sw)])}[sw["deck_id"]]
        real = [c for c in d.cards if c["board"] != "token"]
        if d.variants:
            for v in d.variants:
                _replace_cards(con, d.id, [c for c in real if c.get("variant", 0) == v["idx"]], v["idx"])
        else:
            _replace_cards(con, d.id, real)
        con.execute("UPDATE swaps SET status='applied', applied=? WHERE id=?", (time.time(), swap_id))
        log(con, f"Applied swap {swap_id}")
    return {"ok": True}


@app.delete("/api/swaps/{swap_id}")
def delete_swap(swap_id: int):
    with _lock, db() as con:
        con.execute("DELETE FROM swaps WHERE id=?", (swap_id,))
    return {"ok": True}


# ------------------------------------------------------------------ variants

class VariantIn(BaseModel):
    name: str | None = None
    color: str | None = None
    decklist: str | None = None
    archidekt: str | None = None


def _next_color(con, deck_id) -> str:
    pens = get_settings(con)["pens"]
    mine = {r[0].lower() for r in con.execute("SELECT color FROM deck_variants WHERE deck_id=?", (deck_id,))}
    mine.add(con.execute("SELECT color FROM decks WHERE id=?", (deck_id,)).fetchone()[0].lower())
    others = {r[0].lower() for r in con.execute("SELECT color FROM decks")}
    # prefer a pen no deck stripe uses; dots only have to differ within the deck
    return next((p for p in pens if p.lower() not in mine | others), None) or next((p for p in pens if p.lower() not in mine), pens[0])


@app.post("/api/decks/{deck_id}/variants")
async def add_variant(deck_id: int, body: VariantIn):
    """Split a deck (its current list becomes variant 1) or add one more variant."""
    parsed, sid = None, ""
    if body.archidekt:
        sid, parsed = await fetch_archidekt(body.archidekt)
    cards = parsed["cards"] if parsed else logic.parse_decklist(body.decklist or "")
    if not cards:
        raise HTTPException(400, "No cards found for the new variant.")
    with _lock, db() as con:
        d = con.execute("SELECT * FROM decks WHERE id=?", (deck_id,)).fetchone()
        if not d:
            raise HTTPException(404, "No such deck")
        rows = con.execute("SELECT idx FROM deck_variants WHERE deck_id=? ORDER BY idx", (deck_id,)).fetchall()
        if not rows:
            # the existing list becomes variant 1
            con.execute("UPDATE deck_cards SET variant=1 WHERE deck_id=?", (deck_id,))
            con.execute("INSERT INTO deck_variants(deck_id, idx, name, color, source, source_id, synced) VALUES(?,?,?,?,?,?,?)",
                        (deck_id, 1, "Base", _next_color(con, deck_id), d["source"], d["source_id"], d["synced"]))
            rows = [(1,)]
        if len(rows) >= logic.MAX_VARIANTS:
            raise HTTPException(400, f"A deck can have at most {logic.MAX_VARIANTS} variants.")
        idx = max(r[0] for r in rows) + 1
        if idx > 99:
            raise HTTPException(400, "Too many variants have been created on this deck.")
        con.execute("INSERT INTO deck_variants(deck_id, idx, name, color, source, source_id, synced) VALUES(?,?,?,?,?,?,?)",
                    (deck_id, idx, body.name or (parsed or {}).get("name") or f"Variant {idx}",
                     body.color or _next_color(con, deck_id), "archidekt" if parsed else "paste", sid, time.time()))
        _replace_cards(con, deck_id, cards, idx)
        log(con, f"Deck {deck_id}: added variant {idx}")
        return {"idx": idx}


@app.patch("/api/decks/{deck_id}/variants/{idx}")
async def update_variant(deck_id: int, idx: int, body: VariantIn):
    parsed, sid = None, ""
    if body.archidekt:
        sid, parsed = await fetch_archidekt(body.archidekt)
    with _lock, db() as con:
        if not con.execute("SELECT 1 FROM deck_variants WHERE deck_id=? AND idx=?", (deck_id, idx)).fetchone():
            raise HTTPException(404, "No such variant")
        if body.name is not None:
            con.execute("UPDATE deck_variants SET name=? WHERE deck_id=? AND idx=?", (body.name, deck_id, idx))
        if body.color is not None:
            con.execute("UPDATE deck_variants SET color=? WHERE deck_id=? AND idx=?", (body.color, deck_id, idx))
        if parsed:
            _replace_cards(con, deck_id, parsed["cards"], idx)
            con.execute("UPDATE deck_variants SET source='archidekt', source_id=?, synced=? WHERE deck_id=? AND idx=?", (sid, time.time(), deck_id, idx))
        elif body.decklist is not None:
            cards = logic.parse_decklist(body.decklist)
            if not cards:
                raise HTTPException(400, "No cards found in that list.")
            _replace_cards(con, deck_id, cards, idx)
    return {"ok": True}


@app.delete("/api/decks/{deck_id}/variants/{idx}")
def delete_variant(deck_id: int, idx: int):
    """Remove a variant. With one left, the deck goes back to a plain deck."""
    with _lock, db() as con:
        con.execute("DELETE FROM deck_cards WHERE deck_id=? AND variant=?", (deck_id, idx))
        con.execute("DELETE FROM deck_variants WHERE deck_id=? AND idx=?", (deck_id, idx))
        left = con.execute("SELECT * FROM deck_variants WHERE deck_id=?", (deck_id,)).fetchall()
        if len(left) == 1:
            v = left[0]
            con.execute("UPDATE deck_cards SET variant=0 WHERE deck_id=?", (deck_id,))
            con.execute("UPDATE decks SET source=?, source_id=?, synced=? WHERE id=?", (v["source"], v["source_id"], v["synced"], deck_id))
            con.execute("DELETE FROM deck_variants WHERE deck_id=?", (deck_id,))
        log(con, f"Deck {deck_id}: removed variant {idx}")
    return {"ok": True}


# ------------------------------------------------------------------ tokens

class TokenIn(BaseModel):
    name: str | None = None
    back: str | None = None
    qty: int | None = None
    deck_ids: list[int] | None = None
    notes: str | None = None


@app.post("/api/tokens")
def add_token(body: TokenIn):
    if not (body.name or "").strip():
        raise HTTPException(400, "Give the token a name.")
    with _lock, db() as con:
        cur = con.execute("INSERT INTO tokens(name, back, qty, deck_ids, notes) VALUES(?,?,?,?,?)",
                          (body.name.strip(), (body.back or "").strip(), max(1, body.qty or 1),
                           json.dumps(body.deck_ids or []), body.notes or ""))
        return {"id": cur.lastrowid}


@app.patch("/api/tokens/{token_id}")
def update_token(token_id: int, body: TokenIn):
    with _lock, db() as con:
        for k, v in body.model_dump(exclude_none=True).items():
            if k == "deck_ids":
                v = json.dumps(v)
            if k == "qty":
                v = max(1, v)
            con.execute(f"UPDATE tokens SET {k}=? WHERE id=?", (v, token_id))
    return {"ok": True}


@app.delete("/api/tokens/{token_id}")
def delete_token(token_id: int):
    with _lock, db() as con:
        con.execute("DELETE FROM tokens WHERE id=?", (token_id,))
    return {"ok": True}


# ------------------------------------------------------------------ CubeCobra

async def fetch_cube(ref: str) -> dict:
    cid = logic.cubecobra_id(ref)
    if not cid:
        raise HTTPException(400, "That doesn't look like a CubeCobra link or cube id.")
    async with httpx.AsyncClient(timeout=30, headers=UA, follow_redirects=True) as c:
        r = await c.get(f"https://cubecobra.com/cube/api/cubeJSON/{cid}")
        if r.status_code == 200:
            try:
                cube = logic.parse_cubecobra(r.json())
                if cube["cards"]:
                    cube["id"] = cid
                    return cube
            except ValueError:
                pass
        r = await c.get(f"https://cubecobra.com/cube/download/csv/{cid}")
        if r.status_code == 200 and "," in r.text[:200]:
            cube = logic.parse_cube_csv(r.text)
            if cube["cards"]:
                cube.update(id=cid, name=cid)
                return cube
    raise HTTPException(502, "Couldn't load that cube from CubeCobra. Paste its CSV export instead.")


class CubeIn(BaseModel):
    cube: str | None = None  # CubeCobra link or id
    csv: str | None = None   # pasted CSV export (fallback)
    tags: list[str] = []
    untagged: bool = True    # cards with none of the chosen tags get a "rest" deck
    whole: bool = False      # whole cube as one deck instead of per-tag decks
    pool: str | None = None
    name: str | None = None


async def _load_cube(body: CubeIn) -> dict:
    if body.csv:
        cube = logic.parse_cube_csv(body.csv)
        if body.name:
            cube["name"] = body.name
        return cube
    if body.cube:
        return await fetch_cube(body.cube)
    raise HTTPException(400, "Give a CubeCobra link or paste the cube's CSV.")


@app.post("/api/cubecobra/tags")
async def cube_tags(body: CubeIn):
    cube = await _load_cube(body)
    counts: dict[str, int] = {}
    for c in cube["cards"]:
        for t in dict.fromkeys(c["tags"]):
            counts[t] = counts.get(t, 0) + 1
    return {"name": cube["name"], "cards": len(cube["cards"]),
            "untagged": sum(1 for c in cube["cards"] if not c["tags"]),
            "tags": sorted(({"tag": t, "count": n} for t, n in counts.items()), key=lambda x: (-x["count"], x["tag"].lower()))}


@app.post("/api/cubecobra/import")
async def cube_import(body: CubeIn):
    cube = await _load_cube(body)
    name = body.name or cube["name"]
    if body.whole or not body.tags:
        lists = {name: [{"name": k[0], "qty": k[1], "board": "main"} for k in _count_names(cube["cards"]).items()]}
    else:
        lists = logic.cube_tag_lists(cube, body.tags, f"{name}: other" if body.untagged else None)
    pool = body.pool or f"Cube: {name}"
    created = []
    with _lock, db() as con:
        s = get_settings(con)
        free = 2 * s["slots_per_side"] - con.execute("SELECT COUNT(*) FROM decks").fetchone()[0]
        if len(lists) > free:
            raise HTTPException(400, f"That needs {len(lists)} slots but only {free} are free. Pick fewer tags.")
        for title, cards in lists.items():
            slot = _free_slot(con)
            color = s["pens"][(slot - 1) % len(s["pens"])]
            label = title if body.whole or title.startswith(f"{name}:") else f"{name}: {title}"
            cur = con.execute(
                "INSERT INTO decks(id, name, format, pool, dedicated, active, include_side, slot, color, source, source_id, synced, notes)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (_new_deck_id(con), label, "Cube", pool, 0, 1, 1, slot, color, "cubecobra", cube.get("id", ""), time.time(), ""))
            _replace_cards(con, cur.lastrowid, cards)
            created.append(cur.lastrowid)
        log(con, f"Cube import {name}: {len(created)} decks")
    return {"created": created, "pool": pool}


def _count_names(cards):
    out: dict[str, int] = {}
    disp: dict[str, str] = {}
    for c in cards:
        k = logic.norm(c["name"])
        disp.setdefault(k, c["name"])
        out[k] = out.get(k, 0) + 1
    return {disp[k]: n for k, n in out.items()}


@app.get("/api/overlap")
def overlap():
    with db() as con:
        s = get_settings(con)
        return logic.overlap_matrix(load_decks(con), s["skip_basics"])


@app.get("/api/export.csv")
def export_csv():
    with db() as con:
        p = plan(con)
        decks = {d.id: d for d in load_decks(con)}
    def tag(ids):
        return " ".join(f"{decks[i].slot}" for i in ids if i in decks)
    lines = ["Card,Need,Owned,Short,Location,Batches (slots x copies),Work left"]
    for c in p["cards"]:
        b = "; ".join(f"[{tag(x['marks'])}] x{x['count']}" for x in c["batches"])
        w = "; ".join(f"+[{tag(a['add'])}] -[{tag(a['clear'])}] x{a['count']}" for a in c["actions"])
        row = [c["name"], c["need"], "" if c["owned"] is None else c["owned"], c["short"], c["location"], b, w]
        lines.append(",".join('"' + str(v).replace('"', '""') + '"' for v in row))
    return Response("\n".join(lines), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=edgemark.csv"})


@app.get("/api/backup")
def backup():
    with db() as con:
        dump = {t: [dict(r) for r in con.execute(f"SELECT * FROM {t}")]
                for t in TABLES}
    return JSONResponse(dump, headers={"Content-Disposition": "attachment; filename=edgemark-backup.json"})


@app.post("/api/restore")
async def restore(request: Request):
    data = await request.json()
    with _lock, db() as con:
        for t in TABLES:
            con.execute(f"DELETE FROM {t}")
            allowed = {r[1] for r in con.execute(f"PRAGMA table_info({t})")}
            for row in data.get(t, []):
                row = {k: v for k, v in row.items() if k in allowed}
                if not row:
                    continue
                cols = ",".join(row)
                con.execute(f"INSERT INTO {t}({cols}) VALUES({','.join('?' * len(row))})", list(row.values()))
        log(con, "Restored backup")
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
