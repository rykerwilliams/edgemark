from app import logic
from app.logic import Deck, desired_copies, diff_card, apply_action, parse_decklist, parse_archidekt

F = frozenset


def deck(i, cards, pool="Main", dedicated=False):
    return Deck(id=i, name=f"D{i}", slot=i, color="#f00", pool=pool, dedicated=dedicated,
                cards=[{"name": n, "qty": q, "board": b} for n, q, b in cards])


def test_quantity_tiers_in_one_pool():
    a = deck(1, [("Brainstorm", 4, "main")])
    b = deck(2, [("Brainstorm", 2, "main")])
    c = deck(3, [("Brainstorm", 1, "side")])
    want = desired_copies([a, b, c])["brainstorm"]["copies"]
    assert want == [F({1, 2, 3}), F({1, 2}), F({1}), F({1})]


def test_pools_and_dedicated_do_not_share():
    a = deck(1, [("Swords to Plowshares", 4, "main")], pool="Old School")
    b = deck(2, [("Swords to Plowshares", 4, "main")], pool="Premodern")
    c = deck(3, [("Swords to Plowshares", 1, "main")], pool="Premodern")
    d = deck(4, [("Swords to Plowshares", 1, "main")], dedicated=True)
    want = desired_copies([a, b, c, d])["swords to plowshares"]["copies"]
    assert len(want) == 4 + 4 + 1
    assert want.count(F({1})) == 4 and want.count(F({2, 3})) == 1 and want.count(F({4})) == 1


def test_basics_skipped():
    a = deck(1, [("Island", 10, "main"), ("Snow-Covered Island", 2, "main")])
    assert desired_copies([a]) == {}
    assert desired_copies([a], skip_basics=False)["island"]["copies"] == [F({1})] * 10


def test_fresh_marking_then_done():
    want = [F({1, 2}), F({1})]
    acts = diff_card([], want)
    assert sorted((a["to"], a["count"]) for a in acts) == [([1], 1), ([1, 2], 1)]
    phys = []
    for a in acts:
        phys = apply_action(phys, a["from"], a["to"], a["count"])
    assert diff_card(phys, want) == []


def test_swap_out_creates_clear_not_repaint():
    # Deck 2 drops its copy: sleeve {1,2} should just clear mark 2.
    phys = [F({1, 2}), F({1})]
    acts = diff_card(phys, [F({1}), F({1})])
    assert acts == [{"from": [1, 2], "to": [1], "add": [], "clear": [2], "count": 1}]


def test_extra_sleeve_cleared_entirely():
    acts = diff_card([F({3})], [])
    assert acts == [{"from": [3], "to": [], "add": [], "clear": [3], "count": 1}]
    assert apply_action([F({3})], [3], [], 1) == []


def test_tier_shift_minimal_work():
    # Deck 3 adds 1 copy: best is adding mark 3 to the {1,2} sleeve.
    phys = [F({1, 2}), F({1})]
    acts = diff_card(phys, [F({1, 2, 3}), F({1})])
    assert acts == [{"from": [1, 2], "to": [1, 2, 3], "add": [3], "clear": [], "count": 1}]


def test_parse_plain_with_sideboard_and_sets():
    text = """Deck
4 Brainstorm (ICE) 61
1x Ancestral Recall *F*
3 Force of Will [ALL]

Sideboard
2 Pyroblast
Maybeboard
1 Black Lotus"""
    got = {(c["name"], c["board"]): c["qty"] for c in parse_decklist(text)}
    assert got == {("Brainstorm", "main"): 4, ("Ancestral Recall", "main"): 1,
                   ("Force of Will", "main"): 3, ("Pyroblast", "side"): 2}


def test_parse_mtgo_blank_line_sideboard_and_sb_prefix():
    got = parse_decklist("4 Lightning Bolt\n20 Mountain\n\n3 Red Elemental Blast\nSB: 1 Pyroblast")
    sides = {c["name"]: c["board"] for c in got}
    assert sides == {"Lightning Bolt": "main", "Mountain": "main",
                     "Red Elemental Blast": "side", "Pyroblast": "side"}


def test_parse_dek_xml():
    x = '<?xml version="1.0"?><Deck><Cards CatID="1" Quantity="4" Sideboard="false" Name="Brainstorm" /><Cards Quantity="2" Sideboard="true" Name="Pyroblast"/></Deck>'
    got = {(c["name"], c["board"]): c["qty"] for c in parse_decklist(x)}
    assert got == {("Brainstorm", "main"): 4, ("Pyroblast", "side"): 2}


def test_parse_mwdeck():
    got = parse_decklist("// NAME : Test\n4 [ICE] Brainstorm\nSB: 2 [ALL] Pyroblast")
    assert {(c["name"], c["board"]) for c in got} == {("Brainstorm", "main"), ("Pyroblast", "side")}


def test_split_card_names_normalised():
    assert logic.norm("Fire//Ice") == logic.norm("Fire // Ice")


def test_archidekt_payload():
    data = {
        "id": 5, "name": "Old School UR", "deckFormat": 7,
        "categories": [{"name": "Maybeboard", "includedInDeck": False},
                       {"name": "Sideboard", "includedInDeck": False},
                       {"name": "Considering", "includedInDeck": False},
                       {"name": "Spells", "includedInDeck": True}],
        "cards": [
            {"quantity": 4, "categories": ["Spells"], "card": {"oracleCard": {"name": "Lightning Bolt"}}},
            {"quantity": 2, "categories": ["Sideboard"], "card": {"oracleCard": {"name": "Pyroblast"}}},
            {"quantity": 1, "categories": ["Maybeboard"], "card": {"oracleCard": {"name": "Mox Ruby"}}},
            {"quantity": 1, "categories": ["Considering"], "card": {"oracleCard": {"name": "Fireball"}}},
            {"quantity": 1, "categories": [], "card": {"oracleCard": {"name": "Black Lotus"}}},
        ],
    }
    p = parse_archidekt(data)
    assert p["name"] == "Old School UR" and p["format"] == "Custom"
    assert {(c["name"], c["board"], c["qty"]) for c in p["cards"]} == {
        ("Lightning Bolt", "main", 4), ("Pyroblast", "side", 2), ("Black Lotus", "main", 1)}


def test_archidekt_id():
    assert logic.archidekt_deck_id("https://archidekt.com/decks/19345263/yuriko") == "19345263"
    assert logic.archidekt_deck_id(" 42 ") == "42"
    assert logic.archidekt_deck_id("moxfield.com/decks/abc") is None


def test_collection_csv_and_text():
    csv = 'Quantity,Name,Edition\n4,"Brainstorm",ICE\n2,Brainstorm,MMQ\n1,"Fire // Ice",APC'
    got = {c["name"]: c["qty"] for c in logic.parse_collection(csv)}
    assert got == {"Brainstorm": 6, "Fire // Ice": 1}
    got = {c["name"]: c["qty"] for c in logic.parse_collection("3 Counterspell\n1 Counterspell")}
    assert got == {"Counterspell": 4}


# ---------------------------------------------------------------- variants

def vdeck(i, variants, pool="Main"):
    cards = [{"name": n, "qty": q, "board": "main", "variant": v} for v, lst in variants.items() for n, q in lst]
    return Deck(id=i, name=f"D{i}", slot=i, color="#f00", pool=pool, cards=cards,
                variants=[{"idx": v, "name": f"V{v}", "color": "#0f0"} for v in variants])


def test_variant_marks():
    V = logic.variant_mark
    d = vdeck(3, {1: [("Brainstorm", 4), ("Mana Drain", 2)], 2: [("Brainstorm", 2), ("Fireball", 1)]})
    want = desired_copies([d])
    # copies 1-2 in both variants: stripe only; 3-4 only in variant 1: stripe + dot 1
    assert sorted(want["brainstorm"]["copies"], key=len) == [F({3}), F({3}), F({3, V(3, 1)}), F({3, V(3, 1)})]
    assert want["mana drain"]["copies"] == [F({3, V(3, 1)})] * 2
    assert want["fireball"]["copies"] == [F({3, V(3, 2)})]
    assert logic.split_mark(V(3, 2)) == (3, 2) and logic.split_mark(7) == (7, 0)


def test_variants_share_pool_with_other_decks():
    V = logic.variant_mark
    d = vdeck(3, {1: [("Bolt", 4)], 2: [("Bolt", 1)]}, pool="P")
    e = deck(5, [("Bolt", 2, "main")], pool="P")
    got = desired_copies([d, e])["bolt"]["copies"]
    # copy 1: both variants + deck 5 -> stripes only; copy 2: variant 1 + deck 5; copies 3-4: variant 1 only
    assert sorted(got, key=sorted) == sorted(
        [F({3, 5}), F({3, 5, V(3, 1)}), F({3, V(3, 1)}), F({3, V(3, 1)})], key=sorted)


def test_tokens_count_for_every_variant():
    d = vdeck(2, {1: [("Atog", 1)], 2: [("Fling", 1)]})
    d.cards.append({"name": "Treasure // Clue", "qty": 3, "board": "token", "variant": 0})
    want = desired_copies([d])
    assert want["treasure // clue"]["copies"] == [F({2})] * 3


def test_token_on_plain_deck_and_pool():
    a = deck(1, [], pool="P"); b = deck(2, [], pool="P")
    for x in (a, b):
        x.cards.append({"name": "Goblin", "qty": 2, "board": "token"})
    assert desired_copies([a, b])["goblin"]["copies"] == [F({1, 2})] * 2


# ---------------------------------------------------------------- cubes

def test_cubecobra_json_shapes():
    new = {"name": "My Cube", "cards": {"mainboard": [
        {"details": {"name": "Black Lotus"}, "tags": ["Power", "Artifact"]},
        {"details": {"name": "Brainstorm"}, "tags": []}], "maybeboard": [{"details": {"name": "X"}}]}}
    old = {"name": "Old", "cards": [{"details": {"name": "Brainstorm"}, "tags": ["Blue"]}]}
    assert logic.parse_cubecobra(new)["cards"] == [{"name": "Black Lotus", "tags": ["Power", "Artifact"]}, {"name": "Brainstorm", "tags": []}]
    assert logic.parse_cubecobra(old)["cards"][0]["tags"] == ["Blue"]


def test_cube_csv_and_tag_lists():
    csv = 'name,CMC,Type,maybeboard,tags\n"Black Lotus",0,Artifact,false,"Power;Artifact"\nBrainstorm,1,Instant,false,Blue\nTime Walk,2,Sorcery,false,Power\nJunk,1,Instant,true,Blue\nFiller,1,Creature,false,'
    cube = logic.parse_cube_csv(csv)
    assert [c["name"] for c in cube["cards"]] == ["Black Lotus", "Brainstorm", "Time Walk", "Filler"]
    lists = logic.cube_tag_lists(cube, ["Power", "Blue"], "rest")
    names = {t: sorted(c["name"] for c in l) for t, l in lists.items()}
    assert names == {"Power": ["Black Lotus", "Time Walk"], "Blue": ["Brainstorm"], "rest": ["Filler"]}
    assert logic.cubecobra_id("https://cubecobra.com/cube/list/vintage-ish") == "vintage-ish"
    assert logic.cubecobra_id("https://cubecobra.com/cube/overview/abc123") == "abc123"
