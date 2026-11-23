# Edgemark FAQ

The reasoning behind each answer lives in [DESIGN.md](DESIGN.md) (decision
numbers in brackets).

**What do I mark: the card or the sleeve?**
The Perfect Fit inner sleeve, on the card-face side, along the top edge. The
card is never touched. Let the paint dry fully, then add the outer sleeve.
[D1]

**Do all my decks need the same outer sleeve?**
Every deck *in the same pool* does, because shared cards move between those
decks. Decks in different pools, or dedicated decks, can use anything. [D1, D6]

**What pens work?**
Fine or extra-fine paint pens: oil-based for durability, or Uni Posca PC-1M
(water-based, dries quickly). Avoid soft brush tips, metallic colours (they rub
onto outer sleeves) and black (it barely shows on card backs). Test each pen on
a spare sleeve first. [D3]

**How many decks can I have?**
48 slots per database (24 per side) by default. Split decks don't use extra
slots: variants are dots under the deck's stripe, up to 8 per deck. Cube tags
use one slot each. [D2, D4, D12]

**What's a pool, and why isn't everything shared?**
A pool is a group of decks you never sleeve at the same time, so they can share
copies. Edgemark covers a whole collection, so you might bring two Old School
decks to the same event, keep signed decks intact, or keep a cube built. Put
decks that can share in one pool, and mark decks that keep their own copies as
**dedicated**. [D6]

**How many copies do I need?**
For each pool, as many as its hungriest deck runs. Plus each dedicated deck's
own copies. The Collection tab shows need, owned and short, and builds a buy
list. [D6]

**I changed a decklist. Do I repaint everything?**
No. Edgemark remembers what's painted and lists only the marks to add or
clear. Re-sync from Archidekt, edit the list, or plan the change in Swaps
first. [D7]

**What happens when I delete a deck?**
Its paint is still on the sleeves, so those cards show up under **Marks to
clear** until you clear them and tick them off. [D7]

**Does it care which printing I own?**
Not yet. Cards are matched by name. For signed or printing-specific decks, make
the deck **dedicated** so it keeps its own copies. Printing-level tracking is
planned. [D8]

**Where is my data?**
In one SQLite file in the container's `/data` volume, on your own server. Back
it up by copying the file, or use Settings → Download backup (JSON). Nothing is
sent anywhere except requests to Archidekt and CubeCobra when you import. [D13]

**Can I reorder slots?**
You can change a deck's slot in its Edit dialog. Edgemark then lists the old mark
to clear and the new one to paint on every sleeve. Pick your layout and starting
corner before you paint. [D2, O2]

**Is it tournament legal?**
Possibly. Marks on the card-face side of an inner sleeve add no thickness and
can't be seen from the back, and players report judges allowing them for
sideboard and cube marks. Whether cards count as marked is the head judge's
call, and variant dots sit a little lower on the sleeve.
Check with your head judge before sanctioned play. [O1]

**Why self-hosted instead of a website?**
So it can import from Archidekt and CubeCobra (browsers can't call those
directly), so your data stays yours, and so anyone can change it. [D13]

**Can I change how marks look (side-B variant stripes, different slot counts,
per-pool slots)?**
Yes. That's what DESIGN.md is for. Each decision lists the files and
functions to change. Open an issue first if it changes painted-data
compatibility. [D2, D4, D14]
