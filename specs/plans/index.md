# Plans

Dated `YYYY-MM-DD-<slug>.md` investigation and work logs, one per unit of work.

- [2026-09-20-code-review.md](2026-09-20-code-review.md): full code review of AstroBROT
  (bugs, security, design, CI options). **draft**, review finished; fixes for #4-#6 and #8-#10 are on `develop`. Cross-checked with a Python port
  against `erfa`, TcUnit tests pass on the user-mode runtime, not verified on a telescope.
- [2026-09-21-refraction-model.md](2026-09-21-refraction-model.md): plan for #11 (refraction step at 15 deg, the
  3 % high branch, silent clamping). **implemented, 56 of 56 TcUnit cases pass on the user-mode runtime**; D4 (release) and the telescope check open.
