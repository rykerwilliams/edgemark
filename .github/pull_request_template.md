## What and why

<!-- One or two sentences. Link the issue: Closes #123 -->

## Checklist

- [ ] `python -m pytest -q` passes, with tests for new planning or parsing logic
- [ ] If this changes a design decision, `docs/DESIGN.md` is updated (old reasoning kept under "History")
- [ ] Painted-sleeve compatibility: existing marks read the same, **or** this ships a migration / work list and says so in the release notes
- [ ] New ways of creating decks use `_new_deck_id()` (deck ids are never reused)
- [ ] UI checked at phone width (~390 px) and in dark mode
