# Limits & roadmap

## Limitations and non-goals

- English wording only out of the box; other languages need a phrasebook.
- The offer reader is heuristic (it recognises "% off", "free …", "points", dates in the text). Unusual
  offer text still produces a correct but plainer line.
- Nudgewright does not decide *who* to message or *when*; it writes the line for a send you already chose.
  Consent, frequency caps and quiet hours belong in your sending system.
- No randomness: the same input always gives the same line. Variety comes from the data.
- No AI writer. A language model can be layered on top, with Nudgewright's guardrail check run on its
  output (`nudgewright.check`).
- Planned signals (refill cycles, new arrivals, stock, capacity, local events) are in the catalogue
  but not used yet.

## Roadmap

- Refill-due and "not tried yet" signals from bill history.
- Opening hours, so no line invites people on a closed day.
- More phrasebooks (contributions welcome).
