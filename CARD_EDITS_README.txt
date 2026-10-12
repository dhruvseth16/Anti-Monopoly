Edit these 4 cards by hand (config/competitor_cards.yaml and config/monopolist_cards.yaml).
They are flavour-only cards (no game effect). Replace `effect: null` with an explicit "no effect":

  comp_006, comp_012, mono_019, mono_021:

    effect:
      type: none

Reason: `null` means "not digitised yet" everywhere else in the project (Hard Rule 5), so the engine and
validator refuse it. `type: none` says "I read the card; it has no effect".
