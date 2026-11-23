import importlib
import os

import pytest
from fastapi.testclient import TestClient


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
    assert names["Brainstorm"]["actions"][0]["clear"] == [b]
    assert names["Ponder"]["actions"][0]["add"] == [b]
    sid = client.post("/api/swaps", json={"deck_id": b, "out_name": "Brainstorm", "in_name": "Ponder", "qty": 2}).json()["id"]
    client.post(f"/api/swaps/{sid}/apply")
    st = client.get("/api/state").json()
    bs = next(c for c in st["cards"] if c["key"] == "brainstorm")
    assert bs["actions"] == [{"from": [a, b], "to": [a], "add": [], "clear": [b], "count": 2}]
    # delete deck -> its marks become clears
    client.delete(f"/api/decks/{a}")
    st = client.get("/api/state").json()
    anc = next(c for c in st["cards"] if c["key"] == "ancestral recall")
    assert anc["actions"][0]["clear"] == [a]
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
    assert fl["batches"] == [{"marks": sorted([d, -(d * 100 + 2)]), "count": 1}]
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
    assert tk["need"] == 2 and tk["batches"][0]["marks"] == [d]
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
