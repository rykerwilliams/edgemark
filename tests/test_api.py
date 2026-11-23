# SPDX-License-Identifier: AGPL-3.0-or-later
import importlib
import os

import pytest
from fastapi.testclient import TestClient


def M(deck_id):
    return f"d{deck_id}"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EDGEMARK_DB", str(tmp_path / "t.db"))
    import app.main as m
    importlib.reload(m)
    with TestClient(m.app) as c:
        yield c


def test_full_flow(client):
    a = client.post("/api/decks", json={"name": "UR", "decklist": "4 Brainstorm\n1 Ancestral Recall\n10 Island", "pool": "Eternal"}).json()["id"]
    b = client.post("/api/decks", json={"name": "UB", "decklist": "2 Brainstorm\n1 Ancestral Recall", "pool": "Eternal"}).json()["id"]
    st = client.get("/api/state").json()
    assert [d["slot"] for d in st["decks"]] == [1, 2]
    bs = next(c for c in st["cards"] if c["key"] == "brainstorm")
    assert bs["need"] == 4 and not bs["done"]
    # check off everything shown
    items = [{"key": c["key"], "name": c["name"], "frm": x["from"], "to": x["to"], "count": x["count"]}
             for c in st["cards"] for x in c["actions"]]
    client.post("/api/mark", json={"items": items})
    st = client.get("/api/state").json()
    assert all(c["done"] for c in st["cards"])
    # swap: UB cuts 2 Brainstorm for 2 Ponder -> clears only, plus new marks on Ponder
    pv = client.post("/api/swaps/preview", json={"deck_id": b, "out_name": "Brainstorm", "in_name": "Ponder", "qty": 2}).json()
    names = {c["name"]: c for c in pv["cards"]}
    assert names["Brainstorm"]["actions"][0]["clear"] == [M(b)]
    assert names["Ponder"]["actions"][0]["add"] == [M(b)]
    sid = client.post("/api/swaps", json={"deck_id": b, "out_name": "Brainstorm", "in_name": "Ponder", "qty": 2}).json()["id"]
    client.post(f"/api/swaps/{sid}/apply")
    st = client.get("/api/state").json()
    bs = next(c for c in st["cards"] if c["key"] == "brainstorm")
    assert bs["actions"] == [{"from": [M(a), M(b)], "to": [M(a)], "add": [], "clear": [M(b)], "count": 2}]
    # delete deck -> its marks become clears
    client.delete(f"/api/decks/{a}")
    st = client.get("/api/state").json()
    anc = next(c for c in st["cards"] if c["key"] == "ancestral recall")
    assert anc["actions"][0]["clear"] == [M(a)]
    # collection + backup round trip
    client.post("/api/collection", json={"text": "3 Ponder", "location": "Shared box"})
    st = client.get("/api/state").json()
    p = next(c for c in st["cards"] if c["key"] == "ponder")
    assert p["owned"] == 3 and p["location"] == "Shared box"
    dump = client.get("/api/backup").json()
    client.post("/api/restore", json=dump)
    assert client.get("/api/state").json()["decks"][0]["name"] == "UB"
    assert "Brainstorm" in client.get("/api/export.csv").text
    assert client.get("/api/overlap").status_code == 200


def test_variants_tokens_cube(client):
    d = client.post("/api/decks", json={"name": "Atog", "decklist": "4 Brainstorm\n2 Mana Drain"}).json()["id"]
    v = client.post(f"/api/decks/{d}/variants", json={"name": "Fling build", "decklist": "2 Brainstorm\n1 Fling"}).json()["idx"]
    assert v == 2
    st = client.get("/api/state").json()
    deck = st["decks"][0]
    assert [x["name"] for x in deck["variants"]] == ["Base", "Fling build"]
    fl = next(c for c in st["cards"] if c["key"] == "fling")
    assert fl["batches"] == [{"marks": sorted([M(d), f"d{d}.v2"]), "count": 1}]
    # whole-deck list edits are refused once split
    r = client.patch(f"/api/decks/{d}", json={"decklist": "1 X"})
    assert r.status_code == 400
    client.patch(f"/api/decks/{d}", json={"decklist": "3 Brainstorm\n1 Fling", "variant": 2})
    assert "3 Brainstorm" in client.get(f"/api/decks/{d}/list?variant=2").text
    # swap inside a variant
    pv = client.post("/api/swaps/preview", json={"deck_id": d, "variant": 1, "out_name": "Mana Drain", "in_name": "Counterspell", "qty": 2}).json()
    assert {c["name"] for c in pv["cards"]} == {"Mana Drain", "Counterspell"}
    sid = client.post("/api/swaps", json={"deck_id": d, "variant": 1, "out_name": "Mana Drain", "in_name": "Counterspell", "qty": 2}).json()["id"]
    client.post(f"/api/swaps/{sid}/apply")
    assert "2 Counterspell" in client.get(f"/api/decks/{d}/list?variant=1").text
    # tokens
    t = client.post("/api/tokens", json={"name": "Treasure", "back": "Clue", "qty": 2, "deck_ids": [d]}).json()["id"]
    st = client.get("/api/state").json()
    tk = next(c for c in st["cards"] if c["key"] == "treasure // clue")
    assert tk["need"] == 2 and tk["batches"][0]["marks"] == [M(d)]
    # back to plain deck when one variant remains
    client.delete(f"/api/decks/{d}/variants/2")
    st = client.get("/api/state").json()
    assert st["decks"][0]["variants"] == []
    assert "2 Counterspell" in client.get(f"/api/decks/{d}/list").text
    # deleting the deck drops it from tokens
    client.delete(f"/api/decks/{d}")
    assert client.get("/api/state").json()["tokens"][0]["deck_ids"] == []
    client.delete(f"/api/tokens/{t}")
    # cube via CSV
    csv = 'name,tags\nBlack Lotus,"Power;Artifact"\nBrainstorm,Blue\nTime Walk,Power\nFiller,'
    tags = client.post("/api/cubecobra/tags", json={"csv": csv, "name": "Vint"}).json()
    assert tags["tags"][0] == {"tag": "Power", "count": 2} and tags["untagged"] == 1
    r = client.post("/api/cubecobra/import", json={"csv": csv, "name": "Vint", "tags": ["Power", "Artifact"]}).json()
    st = client.get("/api/state").json()
    assert sorted(x["name"] for x in st["decks"]) == ["Vint: Artifact", "Vint: Power", "Vint: other"]
    lotus = next(c for c in st["cards"] if c["key"] == "black lotus")
    assert lotus["need"] == 1 and len(lotus["batches"][0]["marks"]) == 2


def test_deck_ids_never_reused(client):
    a = client.post("/api/decks", json={"name": "A", "decklist": "1 Black Lotus"}).json()["id"]
    b = client.post("/api/decks", json={"name": "B", "decklist": "1 Mox Pearl"}).json()["id"]
    client.post("/api/mark", json={"items": [{"key": "mox pearl", "name": "Mox Pearl", "frm": [], "to": [M(b)], "count": 1}]})
    client.delete(f"/api/decks/{b}")
    c = client.post("/api/decks", json={"name": "C", "decklist": "1 Mox Pearl"}).json()["id"]
    assert c not in (a, b)
    pearl = next(x for x in client.get("/api/state").json()["cards"] if x["key"] == "mox pearl")
    # old B mark must be cleared and C painted, not silently inherited by C
    assert not pearl["done"]
    assert any(M(b) in x["clear"] for x in pearl["actions"]) and any(M(c) in x["add"] for x in pearl["actions"])



def test_pools_slots_and_sideboard_marks(client):
    # slots are numbered per pool
    a = client.post("/api/decks", json={"name": "OS1", "pool": "Old School", "decklist": "1 Pyroblast\n\nSideboard\n2 Pyroblast"}).json()["id"]
    b = client.post("/api/decks", json={"name": "PM1", "pool": "Premodern", "decklist": "4 Brainstorm"}).json()["id"]
    st = client.get("/api/state").json()
    assert {d["name"]: d["slot"] for d in st["decks"]} == {"OS1": 1, "PM1": 1}
    assert {p["name"]: p["capacity"] for p in st["pools"]} == {"Old School": 60, "Premodern": 60}
    # turning on sideboard marks halves capacity and splits roles
    assert client.patch("/api/pools/Old School", json={"sideboard_marks": True}).status_code == 200
    st = client.get("/api/state").json()
    assert next(p for p in st["pools"] if p["name"] == "Old School")["capacity"] == 30
    pyro = next(c for c in st["cards"] if c["key"] == "pyroblast")
    assert pyro["batches"] == [{"marks": [M(a)], "count": 1}, {"marks": [f"d{a}.sb"], "count": 2}]
    # a deck on a right-edge slot blocks turning sideboard marks on
    client.post("/api/decks", json={"name": "PM2", "pool": "Premodern", "slot": 40, "decklist": "1 Opt"})
    r = client.patch("/api/pools/Premodern", json={"sideboard_marks": True})
    assert r.status_code == 400 and "PM2" in r.json()["detail"]
    # moving a deck to another pool takes a free slot there
    client.patch(f"/api/decks/{b}", json={"pool": "Old School"})
    moved = next(d for d in client.get("/api/state").json()["decks"] if d["id"] == b)
    assert moved["pool"] == "Old School" and moved["slot"] == 2
    # slot outside the pool's range is refused
    assert client.patch(f"/api/decks/{b}", json={"slot": 31}).status_code == 400
    # CSV shows physical positions
    csv = client.get("/api/export.csv").text
    assert "L1" in csv and "R1sb" in csv


def test_variant_bottom_positions_unique_per_pool(client):
    a = client.post("/api/decks", json={"name": "A", "decklist": "1 Bolt"}).json()["id"]
    b = client.post("/api/decks", json={"name": "B", "decklist": "1 Bolt"}).json()["id"]
    client.post(f"/api/decks/{a}/variants", json={"decklist": "1 Shock"})
    client.post(f"/api/decks/{b}/variants", json={"decklist": "1 Shock"})
    st = client.get("/api/state").json()
    pos = sorted(v["pos"] for d in st["decks"] for v in d["variants"])
    assert pos == [1, 2, 3, 4]


def test_old_integer_marks_are_migrated(tmp_path, monkeypatch):
    import importlib, json, sqlite3
    dbp = tmp_path / "old.db"
    monkeypatch.setenv("EDGEMARK_DB", str(dbp))
    import app.main as m
    importlib.reload(m)
    with TestClient(m.app):
        pass
    con = sqlite3.connect(dbp)
    con.execute("INSERT INTO cards(key, name, physical) VALUES('bolt','Bolt',?)", (json.dumps([[1, 2], [-102]]),))
    con.commit(); con.close()
    with TestClient(m.app) as c:
        con = sqlite3.connect(dbp)
        phys = json.loads(con.execute("SELECT physical FROM cards WHERE key='bolt'").fetchone()[0])
        assert phys == [["d1", "d2"], ["d1.v2"]]


def test_add_builds_from_archidekt(client, monkeypatch):
    import app.main as m
    lists = {
        "111": {"name": "UR Atog - Base", "format": "Custom", "cards": [
            {"name": "Lightning Bolt", "qty": 4, "board": "main"}, {"name": "Brainstorm", "qty": 4, "board": "main"}]},
        "222": {"name": "UR Atog - Fling", "format": "Custom", "cards": [
            {"name": "Lightning Bolt", "qty": 4, "board": "main"}, {"name": "Fling", "qty": 4, "board": "main"}]},
    }

    async def fake_fetch(ref):
        if ref not in lists:
            raise m.HTTPException(404, "not found")
        return ref, lists[ref]
    monkeypatch.setattr(m, "fetch_archidekt", fake_fetch)
    r = client.post("/api/decks/builds", json={"refs": ["111", "222"], "pool": "Old School"}).json()
    assert r["name"] == "UR Atog" and r["builds"] == ["Base", "Fling"]
    st = client.get("/api/state").json()
    d = st["decks"][0]
    assert d["name"] == "UR Atog" and [v["name"] for v in d["variants"]] == ["Base", "Fling"]
    assert [v["source_id"] for v in d["variants"]] == ["111", "222"]
    bolt = next(c for c in st["cards"] if c["key"] == "lightning bolt")
    fling = next(c for c in st["cards"] if c["key"] == "fling")
    assert bolt["batches"] == [{"marks": [M(d["id"])], "count": 4}]
    assert fling["batches"] == [{"marks": sorted([M(d["id"]), f"d{d['id']}.v2"]), "count": 4}]
    # a bad link creates nothing
    assert client.post("/api/decks/builds", json={"refs": ["111", "999"]}).status_code == 404
    assert len(client.get("/api/state").json()["decks"]) == 1
    # needs at least two builds
    assert client.post("/api/decks/builds", json={"refs": ["111"]}).status_code == 400
