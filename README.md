# Edgemark

[![CI](https://github.com/rykerwilliams/edgemark/actions/workflows/ci.yml/badge.svg)](https://github.com/rykerwilliams/edgemark/actions/workflows/ci.yml)
[![License: AGPL v3](https://img.shields.io/badge/code-AGPL--3.0-blue.svg)](LICENSE)
[![Guide: CC BY-SA 4.0](https://img.shields.io/badge/guide-CC%20BY--SA%204.0-lightgrey.svg)](guide/LICENSE)

A sleeve-marking planner for a whole Magic collection, built for every format:
Old School, Premodern, Vintage, cube, signed decks and Commander alike.

Each deck owns a **slot** on the top edge of the inner sleeve and a **pen
colour**. A sleeve carries one mark per deck that uses that copy. Edgemark works
out how many copies you need, which marks go on which sleeves, what to clear
when lists change, and what to buy.

## Background

Marking sleeves so one copy of a card can serve several decks isn't new. Players
have done it by hand for well over a decade:

* Commander players on MTG Salvation traded tips for it: sleeve every deck the
  same, then mark shared cards with a coloured sharpie dot, or with little
  coloured stickers showing which deck each card belongs to.
  ([Sharing cards among commander decks](https://www.mtgsalvation.com/forums/the-game/commander-edh/600936-sharing-cards-among-commander-decks))
* A cube owner on the same forum marked the sleeves of cards shared between
  cubes, so switching meant pulling every marked card into a stack.
  ([Best way to share cards between decks?](https://www.mtgsalvation.com/forums/the-game/commander-edh/545349-best-way-to-share-cards-between-decks))
* Players have long put a small dot on the card-face side of sideboard sleeves
  to find those cards fast between games.
  ([TappedOut: Can I mark my sleeves?](https://tappedout.net/mtg-questions/can-i-mark-my-sleeves))
* A related approach keeps shared staples in a binder, all decks in the same
  sleeves, with placeholders in each deck.
  ([The Mana Base](https://themanabase.com/?p=1293),
  [the "Staples Binder Method"](https://github.com/cognicraft/mtg#the-staples-binder-method))

Edgemark does the bookkeeping those methods leave to you: which decks each copy
belongs to, how many copies each pool needs, and exactly which marks change when
a list changes.

## Concepts

| Term | Meaning |
|---|---|
| Slot | Position 1–24 on side A (card face), 25–48 on side B (card back). Count from the starting corner set in Settings. |
| Pool | Decks that never need to be sleeved at the same time share copies. Copy *n* carries the mark of every deck in the pool that runs at least *n* copies. |
| Dedicated | The deck gets its own copies (signed decks, cubes, anything that stays built). |
| Variant | One deck with several builds (up to 8) sharing its slot. Cards in every build get the stripe only; cards in some builds also get a coloured dot in the lower half of the window, one colour per build. |
| Token | A card no decklist names (token, emblem, dungeon) that should still carry deck marks. Double-sided tokens get the marks of every deck that needs either side. |
| Work | The difference between what's painted and what the decklists need: paint these marks, clear those. |

## Run it

```bash
docker compose up -d --build      # http://<host>:8080
```

Data lives in `./data/edgemark.db` (SQLite). The container gives that folder
to user 10001 when it starts. Set `PUID`/`PGID` (see `docker-compose.yml`) to
make the files belong to your own user instead. Back it up by copying that file or
using **Settings → Download backup**.

To expose it beyond your LAN, set `EDGEMARK_AUTH=user:password` (HTTP basic
auth) and put it behind your usual TLS reverse proxy. On AWS, the same image runs
on ECS/Fargate, App Runner or a small EC2 box. Mount persistent storage
(EBS/EFS) at `/data`.

Or run the published image instead of building:

```bash
docker run -d -p 8080:8080 -v $PWD/data:/data -e PUID=$(id -u) -e PGID=$(id -g) ghcr.io/rykerwilliams/edgemark:latest
```

Without Docker:

```bash
pip install -r requirements.txt
EDGEMARK_DB=./edgemark.db uvicorn app.main:app --port 8080
```

## Importing decks

* **Archidekt**: paste deck links (public or unlisted), or enter your username
  and pick decks. **Re-sync** pulls the latest list, and the Mark tab then shows
  only what changed. Maybeboard and excluded categories are skipped. The
  sideboard is kept (it's physically in the box), and you can turn it off per
  deck.
* **Paste or upload**: plain text, MTGO `.dek` XML, `.dec`, `.mwDeck`, and
  Arena/Moxfield exports, with a `Sideboard` header or `SB:` prefix.
* **CubeCobra**: paste a cube link or its CSV export, tick tags, and each tag
  becomes a deck in one pool, so a card with two tags carries both marks and
  the cube needs one copy. Untagged cards can get a catch-all deck, or you can
  import the whole cube as one deck.
* **Variants**: in a deck's Edit dialog, **Split into variants** turns the
  current list into "Base" and adds another build (from Archidekt or pasted).
  Each variant syncs and swaps on its own.
* **Collection**: paste `4 Brainstorm` lines or a CSV with Quantity and Name
  columns (Archidekt, Deckbox and Moxfield exports all work) to set owned counts
  and a location.

The Archidekt and CubeCobra APIs are public but undocumented. If a deck or cube
won't import, paste its text or CSV export instead.

## Docs

* [docs/DESIGN.md](docs/DESIGN.md): every design decision, what it limits and
  where to change it
* [docs/FAQ.md](docs/FAQ.md): common questions
* [CONTRIBUTING.md](CONTRIBUTING.md): dev setup and the rules that protect
  painted sleeves

## API

Everything the UI does is plain JSON over HTTP. See `/docs` for the generated
OpenAPI page, e.g. `POST /api/decks {"archidekt": "<url>", "pool": "Old School"}`.

## Tests

```bash
pip install pytest && python -m pytest -q
```

## Printable marking guide

`guide/` holds a two-part 3D-printable jig (base + window plate) with 24 windows
at 2.6 mm pitch matching the app's slots. See `guide/README.md`.

## License

Copyleft, so Edgemark and its improvements stay open:

* **Code**: [GNU AGPL-3.0-or-later](LICENSE). Use it, change it and share it.
  If you run a modified version for other people, offer them your source.
* **Printable guide** (`guide/`): [CC BY-SA 4.0](guide/LICENSE). Print, sell
  prints of, and remix it, with credit, under the same license.

See [NOTICE](NOTICE) for attribution. Edgemark is fan-made and not affiliated with
Wizards of the Coast.
