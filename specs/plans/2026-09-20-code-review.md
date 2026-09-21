# Code review of AstroBROT (develop @ b9ea338)

**Status: draft. Review finished; the body below describes `develop` at the review commit. Since then fixes for #4-#6, #8-#10 and #15-#17 landed on `develop` (`d1d51d9`, `6c46444`, `5a6247e`, `2474443`, `691db41`, `53d0c62`, `d9af836`, `d6c2d35`, `e1f0a49`), and `AstroBROTTests` (TcUnit, 56 cases) passes on the user-mode runtime (re-run 2026-09-21 with the #15-#20 fixes and the refraction change #11 in the working tree). Nothing has been verified on a telescope. Open items: GitHub issues.**

Reviewed at `develop` b9ea338. `origin/main` is 3 commits ahead (visualization profile fix to 4024, a
manual TcBuild workflow, runner labels); those are not part of the review except in the CI section.

Scope: all 21 POUs (~2000 lines of ST), `.github/workflows/release.yml`, the committed `_Boot/`,
`_Libraries/` and `.library` artifacts, `testing/BROT_test.ipynb`, and the public API. Consumers
(BROTLib, IAG50cm) were only sampled at their call sites.

## How this was checked (and what that is worth)

- **Static read** of every POU against the algorithms it cites (IDLAstro, NOVAS F3.1, SOFA, Meeus).
- **Numerical cross-check** with a line-by-line Python port of the ST (arrays parsed straight from the
  `.TcPOU` files, so no transcription errors in the tables), compared against `erfa` (pyerfa, the SOFA
  port used by astropy 7.2.0). Scripts are in `testing/`: `astrobrot_port.py` plus
  `check_time_precess.py`, `check_apparent_vs_erfa.py` and `check_refraction_roundtrip.py`
  (each runs standalone with `python3`, needs `numpy` and `pyerfa`).
- **Limit:** this tests my port, not the compiled ST. A porting slip on my side would show up as a
  false finding, and a TwinCAT-specific behavior (rounding, `LIMIT` on NaN, FB state) would not show up
  at all. Findings are marked **verified (port)**, **read from code**, or **unsure**.
- The erfa comparison used `dut1 = 0` (UT1 = UTC, as the library does) and no refraction, to isolate
  algorithm error from the missing Earth-orientation inputs.

## Findings, worst first

### High

**H1. Default refraction temperature is in Kelvin but is fed to a function that expects Celsius.**
`FB_CO_REFRACT` defaults `temperature` to `283.0 - alpha*altitude` (Kelvin, as in IDL). It then calls
`CO_REFRACT_FORWARD(..., T := temperature)`, which expects Celsius (`T+273.0`) and clamps to
`[-40, 40]`. The default path therefore computes refraction at 40 °C instead of about 10 °C.
*Verified (port).* Refraction comes out too small by about 10 %: 56" at 5° altitude, 30" at 10°,
10" at 30°, 5.7" at 45°. `FB_EQ2HOR`/`FB_HOR2EQ` do not expose pressure or temperature, so every
caller of the top-level blocks gets this. A user-supplied `temperature` is interpreted the other way
(Celsius), so the input has no consistent unit. Also, `temperature = 0.0` means "unset", so 0 °C cannot
be requested. Fix: pick one unit, convert once, document it, and use a separate "unset" mechanism.

**H2. Unbounded `REPEAT ... UNTIL` in `FB_CO_REFRACT` can hang the PLC task.**
The loop exits only when `ABS(last-cur)*3600 < epsilon`. With `epsilon <= 0` (it is a `VAR_INPUT`) it
never exits, and with a NaN/Inf `old_alt` the comparison is always false. *Verified (port) for
`epsilon = 0` and NaN.* On the real controller this ends in a task-exceed watchdog. A NaN altitude is
realistic (an upstream division by zero). Normal input converges in 1 to 5 iterations, so a cap of about
10 iterations costs nothing. Also reject non-finite input.

**H3. `FB_HOR2EQ` defaults `refract_to_observed := TRUE`, which is the wrong direction for an observed altitude.**
HOR2EQ takes measured alt/az, so refraction must be removed (`FALSE`). With the default it is added
again. *Verified (port):* EQ2HOR (refract on) then HOR2EQ with the default gives a 562" round-trip error
at 10° altitude; with `FALSE` the error is 0.0". The notebook never caught this because it ran with
`refract := FALSE`. At least one consumer passes `refract_to_observed` explicitly in the direction that is
the reverse of the IDLAstro convention for one of the two blocks. I could not tell from the call site
whether the altitudes there are observed or geometric. **Owner to check the consumers' call sites** whether
that is intended (details kept out of this public repo).

**H4. The committed `.library` binaries are stale relative to the sources.**
`AstroBROT.library` was last committed 2025-07-25, the sources changed on 2026-01-16 to 2026-01-21. A
string search of both `.library` files (zip archives) finds `FB_PRECESS` and `FB_EQ2HOR`, but not
`FB_HADEC2RADEC`, `FB_RADEC2HADEC`, `FB_IAU2000B` or `Global_Version`. *Partly verified:* I did not
decompile the objects, so absence of a string is strong evidence, not proof. This matches the open
`docs/todo-astrobrot-library-mismatch` branch (IAG50cm fails to resolve the two HADEC blocks).
`release.yml` bumps the version numbers but never rebuilds the library, so a tagged release can carry a
binary that does not match its own source tree. Fix: build the library in CI (a TcBuild job already exists on `main`, see the CI section) and stop
committing the `.library`, or make the release job fail if the binary is older than the sources.

### Medium

**M1. Blocks overwrite their own inputs and keep stale state between calls.** *Read from code.*
- `FB_EQ2HOR` writes `ra` and `dec` (`ra := ra_pre + ...`), `FB_HOR2EQ` writes `alt`, `az`
  (`az := az - 180.0`, `new_alt => alt`), `FB_CO_ABERRATION` writes `eps`, `FB_CO_REFRACT` writes
  `temperature` and `pressure`.
- The README's usage pattern ("set the input coordinates, call once per PLC cycle") is where this bites:
  if the caller assigns `fb.ra := x` once and calls cyclically, the corrections accumulate every cycle.
  Calls with a full parameter list (what BROTLib and IAG50cm do) are safe.
- `d_ra_nut`, `d_dec_nut`, `d_psi`, `d_ra_abr`, `d_dec_abr` are instance variables that are only
  written when `nutate`/`aberration` is TRUE. Toggling a flag to FALSE at runtime keeps applying the last
  value (about 17" for nutation).

**M2. `FB_PRECESS` only works when one epoch is exactly 2000.0.** It follows NOVAS `PRECES`, which has
that contract, but the README says "precession between epochs". *Verified (port):*
`precess(10, 20, 2010, 2020)` returns exactly what `precess(10, 20, 2000, 2010)` returns. Nothing
signals the misuse, and the test is a floating-point `=` on `equinox2`. Fix: precess via J2000 in two
steps, or reject other pairs. When the contract is respected the block is accurate: max separation vs
`erfa.bp06` precession is 7 mas over 1980 to 2040 (300 random samples).

**M3. `FB_CO_NUTATE.d_ra` is not wrapped.** It returns `ra2 - ra` with `ra2` in [0, 360).
*Verified (port):* `ra = -5` gives `d_ra = 360.0004`; near RA 0/360 the sign flips by 360. The
end result of `FB_HADEC2RADEC` is still right, but only because `FB_PRECESS` wraps at the very end
(`ra_out := last - ha` is unwrapped and can be in (-360, 360)). Anyone using `d_ra` directly gets
garbage near the wrap. Fix: wrap the difference to ±180.

**M4. The refraction model has a step at 15° and silently clamps inputs.**
*Verified (port):* the two branches give 221.06" below and 226.46" above 15° (a 5.4" jump). `a` is
clamped to [0, 90], `P` to [600, 1200], `T` to [-40, 40] with no flag, so a below-horizon altitude gets
the horizon refraction. The comment says "accurate to 0.5 arcsec". I could not reproduce that:
against `erfa.refco` (10 °C, 1010 hPa) the code is 0.8" high at 10°, 3.0" high at 30° and 1.0" high at
60°. `erfa`'s own model is only an approximation, so **unsure which is closer to the truth**. I did
not check the equation numbers (7.90/7.91) against the book.

**M5. No UT1-UTC, polar motion, or diurnal aberration.** *Read from code, magnitude from theory.*
`JD2LST` treats `jd` as UT1. UT1-UTC reaches 0.9 s, which is up to about 13.5" of RA at the
equator, larger than every algorithmic error found below. No input exists to correct it. The doc
comments do not say what time scale `jd` is. The same `jd` also drives precession/nutation (TT), where
the 69 s offset is negligible. If pointing better than roughly 10" matters, add a `dut1` input.

**M6. Test coverage is thin and the recorded conclusion is probably wrong.**
- `testing/BROT_test.ipynb` needs a live PLC (hard-coded AmsNetId), has no pass/fail thresholds, and
  covers only `JD2LST`, `EQ2HOR`, `HOR2EQ` and a round trip, all with `refract := FALSE`.
- Not covered at all: `FB_RADEC2HADEC`/`FB_HADEC2RADEC` (the blocks IAG50cm uses), `FB_PRECESS`,
  refraction, `FB_SUNPOS`, poles, zenith, RA wrap, and negative or out-of-range inputs.
- The notebook and the README both record "azimuth outliers up to 40"" and call the errors systematic.
  *Inference, not proven:* azimuth error in raw degrees is amplified by 1/cos(alt) near the zenith, so
  a coordinate difference is not a sky separation. My port has 0.34" maximum great-circle error against
  `erfa` over 2000 random cases (2024 to 2029, all declinations), so the algorithm itself does not
  produce 40". Compare as great-circle separation and rerun on the PLC before trusting either number.
- TcUnit v1.2.0 is in `_Libraries/` but not referenced; `E_TestState.ERROR` is unused.

**M7. Duplicated pipeline, which is how M1 and M3 spread.** *Read from code.* The obliquity polynomial is
copy-pasted in four blocks (`FB_CO_NUTATE`, `FB_CO_ABERRATION`, `FB_HADEC2RADEC`, `FB_HOR2EQ`), the
`last := lmst + d_psi*COS(eps)/3600` step in four, and `J_now := (jd-jd2000)/365.25 + 2000.0` in four.
`FB_RADEC2HADEC`/`FB_HADEC2RADEC` were adapted from EQ2HOR/HOR2EQ by copy instead of being composed
(`EQ2HOR` = `RADEC2HADEC` + `HADEC2ALTAZ` + refraction). Two nutation model calls happen per HOR2EQ and
HADEC2RADEC call (`FB_IAU2000B` directly and again inside `FB_CO_NUTATE`).

**M8. The next release would have failed half way, because `main` had diverged from `develop`. Resolved 2026-09-20: `origin/main` was merged into `develop` (bf588dc) and pushed.** *Read from code,
divergence verified with `git rev-list`.* `origin/main` has 3 commits that `origin/develop` lacks (0 the other
way). `release.yml` pushes its version-bump commit to `develop` first, then runs
`git merge --ff-only develop` on `main`. After the bump, `develop` is no longer an ancestor-descendant of
`main`, so the merge fails and the job stops with the bump already on `develop`, `main` not updated and no
tag. Merging `main` into `develop` fixed the divergence. Nothing prevents it from recurring if `main` gets
commits directly, and I did not run the workflow.

### Low

- **L1. `TEN` ignores sign convention.** `TEN(-5, 30, 0)` returns -4.5; IDLAstro's `ten` returns -5.5
  (sign applies to the whole value). *Verified (port) for the arithmetic; the IDL behavior is from memory,
  check it.* Public API, unused inside the library.
- **L2. `FB_IAU2000B` has 79-entry tables and loops over 78.** SOFA's IAU 2000B has 77 luni-solar terms.
  *Verified (port):* the first 77 terms reproduce `erfa.nut00b` to a constant (0.135 and -0.388 mas, which
  is SOFA's planetary offset). The 78th term is spurious and adds 0.03 to 0.13 mas depending on epoch.
  Harmless in size, but it means the tables were not checked against the source.
  The constants `-0.0433585"` and `-0.0084531"` stand in for frame bias (the header comment says so). That
  works, since the end-to-end error stays under 0.35", but `d_psi` is no longer the nutation and is
  then reused for sidereal time.
- **L3. `FB_NUTATE` (1980 theory) is dead code.** *Removed in `e1f0a49` (#17).* Only the `.plcproj` references it (grep over all
  sibling repos). Remove or test it.
- **L4. Unclamped `ASIN` arguments** in `FB_ALTAZ2HADEC`, `FB_PRECESS`, `FB_CO_NUTATE`, `FB_SUNPOS`. A
  rounding overshoot above 1.0 gives NaN. *Not reproduced:* 20000 random alt/az/lat cases and 400 pole
  cases through the precession matrix never exceeded 1.0. Hardening only, cheap (`LIMIT(-1, x, 1)`).
- **L5. Custom `ATAN2`** *(#19: kept and tested in `FB_ATAN2_Tests`; TwinCAT's PLC has no `ATAN2` of its own; `POLY` removed, it had no callers after `FB_NUTATE` went)* hand-rolls a quadrant fix-up around `ATAN(y/x)`. A string search of the
  Tc2_Math archive finds no `ATAN2` (it does find `LMOD` and `MODABS`), so there is no name clash. It returns +PI for `y = -0.0, x < 0`; harmless after the
  `MODABS` calls. `POLY` uses `EXPT(X, n)` instead of Horner form.
- **L6. `DateTime2JD` is Gregorian only** *(#20: unused variable and dead code removed, contract documented in the block, `FB_DateTime2JD_Tests` added; no validation by design, a validity flag belongs in `FB_AstroClock`, BROTLib M1)* (Julian-calendar branch commented out), has an unused variable
  `d`, and does no input validation. *Verified (port):* 0 s difference to `erfa` for five test dates.
  It does not say whether the `TIMESTRUCT` must be UTC.
- **L7. Cost per call is unmeasured.** `FB_IAU2000B` runs 78 sin/cos pairs per call, and HOR2EQ and
  HADEC2RADEC run it twice. Nutation changes slowly, so it could be cached per second. *Inference:* I
  have not timed this on the CE7/ARM or x64 targets; the notebook only reports the 10 ms task cycle.

## Security

Nothing here is exploitable remotely. The library does no I/O. The items are hygiene.

- **S1 (Low). Script injection in `release.yml`.** The "Validate version format" step interpolates
  `${{ inputs.version }}` directly into a shell command, so a `$(...)` payload runs before the regex
  check. Only users who can already dispatch the workflow (write access, with `contents: write`) can
  exploit it. Fix: pass it through `env:` and read `$VERSION`.
- **S2 (Low-Medium). The release job pushes straight to `develop` and `main` and tags, with no build or
  test gate.** Combined with H4 this is how a bad binary gets tagged. `actions/checkout@v4` is pinned by
  tag, not commit SHA.
- **S3 (Low). Internal address in a public repo.** The notebook contains the PLC AmsNetId
  (an IP-based address, not repeated here). *Not verified:* whether it is routable or internal. The repo is
  public (checked with `gh`). Remove it or reduce it to a placeholder; it stays in git history either way.
- **S4 (Low). About 67 MB of binaries are tracked**: three `.compileinfo` files (11 MB, 11 MB, 4.6 MB),
  `_Boot/` for three targets, three versions of several Beckhoff libraries, and the notebook twice
  (1.9 MB each, once as `.ipynb_checkpoints/`). Text files show no credentials (grep for `password`,
  `secret`, `token`, `api key`). I did **not** open the binary archives (`.tpzip`, `.tizip`, `.app`), which
  can hold routes and settings; check them before the repo is public if it is not yet.

## Design assessment

1. **Function blocks used for pure math.** Each transform is an FB with outputs and hidden instance
   state, which is what produces M1. Plain `FUNCTION`s returning a struct, or FBs that reset their
   outputs on every call, would remove that class of bug. Nested FB instances (EQ2HOR holds five
   FBs, each with its own `FB_IAU2000B` copy of about 900 constants) also cost memory on every instance.
2. **The pipeline should be composed, not copied** (M7). One `F_Obliquity`, one `LAST` helper, one
   apparent-place block, and `EQ2HOR`/`HOR2EQ` built on top of it.
3. **Inconsistent API.** `JD2LST` returns degrees, `CT2LST` hours. `ha_out`/`ra_out` vs `ha`/`ra`.
   `refract_to_observed` has different meaning by default in the two top-level blocks (H3). `ws`
   exists on HADEC2ALTAZ and EQ2HOR but not on ALTAZ2HADEC. File `FB_Eq2Hor.TcPOU` holds `FB_EQ2HOR`.
   The README talks about `F_*` naming that the functions do not use. ST is case-insensitive and the
   code mixes `JD`/`jd`, `ABERRATION`/`aberration`.
4. **Missing inputs.** No pressure/temperature/humidity pass-through in the top-level blocks, no `dut1`,
   no wavelength. Consumers cannot use measured weather.
5. **A library that ships a `MAIN` program and a 10 ms PLC task** (used as a test harness) is
   confusing next to the "pure calculation blocks" description. Move it to a separate test project.
6. **Accuracy is good where it was measured.** Vs `erfa` (2000 random cases, 2024 to 2029, geometric, no
   refraction, `dut1 = 0`): apparent HA/Dec and Alt/Az great-circle error median 0.16", p95 0.26",
   max 0.34". The RADEC2HADEC to HADEC2RADEC round trip has a max error of 0.21". Sidereal time matches
   `erfa.gmst82` to 0.0001". Part of the 0.16" is probably diurnal aberration, which erfa includes and
   the library does not (inference). The maths is not the weak part; the defaults, error handling,
   test coverage and release process are.

## CI: can it compare against astropy?

Investigated 2026-09-20. Build CI already exists and works. Test CI does not, and its tooling is the weak part.

**What exists (verified from the repos and `gh run list`):**
- An org-level self-hosted runner (labels `self-hosted, twincat, windows`), set up as described in
  `BROTLib/specs/design/twincat-ci-runner-setup.md` and
  `BROTLib/specs/plans/2026-09-15-twincat-ci-investigation.md`. I could not list the runner itself (needs
  `admin:org`).
- `tcbuild-test.yml` (`workflow_dispatch` only) exists on AstroBROT `main`, not on `develop`. Its last run
  succeeded on 2026-09-16 (2m47s). BROTLib's run succeeded on 2026-09-15. Full telescope solutions are an
  open problem for this runner, per the runner doc.
- The tool is `JustusRijke/TcBuild` (MIT, Windows, TwinCAT 3.1.4024 or newer, .NET 4.8). `build` compiles,
  `install` compiles and exports a `.library` into the library repository. Exit codes: 0 ok, 1 success with
  warnings, 2 errors, 3 to 5 COM or missing-file problems. Per its README it does **not** run tests or
  activate a configuration.
- The runner doc keeps workflows `workflow_dispatch` only after an earlier PR-triggered setup exposed the
  runner on a public repo. That matches the concern in my first draft of this section.

**What that settles:** a compile check for H4 is possible today. `TcBuild install` on the AstroBROT solution
would produce the `.library` from the sources; upload it as a workflow artifact instead of committing it.
Decide whether exit code 1 (warnings only) should fail the job; the runner doc lists a spurious exit 1 among
its known flakiness symptoms.

**What it does not settle (numeric tests):**
- Running the blocks needs a TwinCAT runtime. Beckhoff's test licenses last 7 days, can be renewed any
  number of times, are created in XAE (not on the runtime), are bound to the target system and need no
  internet. The pages I read say nothing about VMs, unattended renewal, or what happens at expiry, so
  **unattended runs are unverified**. Whether a PLC runtime license is required here I do not know. The
  runner doc only says compile-only use does not appear to need one.
- **TcUnit-Runner is archived** (read-only since 2025-10-17, "contact us for the latest version"), and was
  built around Jenkins and xUnit XML. I would not build new CI on it. Your investigation doc also lists
  [zkbuild-action](https://github.com/Zeugwerk/zkbuild-action) as "not yet evaluated"; I have not
  evaluated it either.

**Recommendation:**
1. The build job is now on `develop` (see M8); add an `install` step and upload the
   `.library` as an artifact, then drop the committed binary.
2. Write the golden vectors (option 2 below) and run them from the pyads notebook on a real PLC for now,
   with hard thresholds.
3. Only then look at unattended runtime tests: ask Beckhoff about licensing for a CI machine and evaluate
   zkbuild-action. Do not depend on TcUnit-Runner.

Options as first ranked:
1. **Self-hosted runner with XAE**: build now, tests pending the licensing and tooling questions above.
2. **Golden vectors.** Generate reference values with `erfa` (fixed seed, dates, sites, including poles,
   zenith, RA wrap, refraction on and off) and commit them as JSON. A PLC-side run compares against them
   with hard tolerances (for example 1" great-circle). Independent of the runner.
3. **Python port in cloud CI.** Cheap and catches regressions in the maths, but tests the port, not the
   ST. It should not count as coverage of the library.

## Suggested order of work

1. H2 (cap the loop), H1 (temperature unit), H3 (default direction plus an IAG50cm check). Small changes.
2. H4 and S2: build in CI, gate the release on it (M8 is already resolved).
3. Golden vectors with great-circle metric (M6), including RADEC2HADEC/HADEC2RADEC and refraction.
4. M1 to M3 (input mutation, `PRECESS` contract, `d_ra` wrap) together with the M7 refactor.
5. `dut1` input (M5) if the pointing budget needs it.
