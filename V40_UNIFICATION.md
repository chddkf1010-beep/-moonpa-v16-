# v40 phase 1 — web baseline integration

Base: 981858a91e090054b357d19d4c3f459f7375da0e. This branch retains the original web engine, named fighters, portraits, notables, honors, terrain, browser snapshot format and monthly controls. No replacement with the separate local HTTP code.

First selective port from v38/v39: retire new regular, expedition, elite and livelihood missions and automated errands in live campaigns. Historical generation stays unchanged. An already committed legacy battle can finish; return old expedition crews at a safe boundary without refunding past costs. Retain historical records, existing abilities and old save fields. New passive income and landless support use the v38 initial values, only during weeks 1–51. Forecast shows normal-week income; AI budget counts the new income once. Values are provisional: long-run economic balance needs testing.

Not yet ported: v39 two-way incoming transfer bids, v38 full-season persistent journal, v27–36 combat/economic/map/facility changes, local action-journal save migration. No direct v39 save import. No new equipment, fortune events or special items. Old mission-specific tests describe retired behavior; do not treat those as supported current gameplay.

Validation: new tests plus selected existing identity tests. No main-branch change or deployment from this integration branch.
