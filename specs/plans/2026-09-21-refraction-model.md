# Plan: fix the refraction model (AstroBROT#11)

**Status: implemented in the working tree; library compiles (0 errors, 0 warnings) and `AstroBROTTests` passes on
the user-mode runtime (9 suites, 56 cases, 56 passed, 2026-09-21).** Decisions taken: D1 = option c, D2 = linear blend 14 to 16 deg, D3 = (ii); D4 open. See
section 7. Issue: [#11](https://github.com/BROTLib/AstroBROT/issues/11)
(code review finding M4). Related: #13 (tests), MONETcommon#18 and IAG50cm#3 (consumers). The comparison
script is `testing/check_refraction_model.py`; it produced every number below.

## 1. Goal and scope

Make `CO_REFRACT_FORWARD` (and with it `FB_CO_REFRACT`, `FB_EQ2HOR`, `FB_HOR2EQ`) accurate and continuous
over the altitudes a telescope uses, and say honestly what it can and cannot do.

In scope: the refraction formula, the 15 deg step, the silent clamping of `a`, `P` and `T`, the accuracy
claim in the comment, tests and goldens.

Not in scope: humidity and wavelength inputs, UT1-UTC (#12), a full ray-traced atmosphere on the PLC,
changing the `FB_CO_REFRACT` interface beyond what section 3 (D3) decides.

## 2. What is known

Reference for all comparisons: a ray trace through a standard atmosphere (script docstring has the
assumptions). **It is not an authority.** Its refractivity is calibrated so that 45 deg gives the textbook
58" at 10 degC and 1010 hPa, so it is good to about 0.5 %, and it is weakest below 10 deg. It is used to
rank candidate formulas, not to declare one true.

Errors, candidate minus reference, arcsec, 1010 hPa and 10 degC (the other two conditions in the script
behave the same above 15 deg):

| Altitude | Reference | Current code | `0.00452` form | `erfa.refco` |
|---|---|---|---|---|
| 5 deg | 587.9 | -0.2 | -0.2 | -21.3 |
| 10 deg | 317.2 | -0.6 | -0.6 | +0.2 |
| 14.9 deg (low branch) | 214.2 | +0.5 | +0.5 | +0.6 |
| 15.0 deg (high branch) | 212.8 | **+5.7** | +4.0 | +0.6 |
| 20 deg | 157.7 | +4.7 | +1.8 | +0.5 |
| 30 deg | 99.9 | +3.2 | +0.6 | +0.3 |
| 45 deg | 57.8 | +1.9 | +0.2 | +0.2 |
| 60 deg | 33.4 | +1.1 | +0.1 | +0.1 |
| 80 deg | 10.2 | +0.3 | +0.0 | +0.0 |

Findings:

1. The branch below 15 deg is fine (within about 0.6" from 10 deg, larger at 5 deg in cold or hot air: up to
   5.6"). The **branch at 15 deg and above is about 3 % too high**: 1.1" to 5.7". It is a Bennett-style
   `cot(a + 7.31/(a+4.4))` scaled by `0.28 * 0.0167`, not the `tan` form the comment cites. The "accurate to
   0.5 arcsec" claim is false.
2. The jump at 15 deg is 5.2" today. The `0.00452 * P / ((273 + T) * tan a)` form (what I remember of
   Explanatory Supplement 2013 eq. 7.90, **not checked against the book**) fixes the size of the error above
   30 deg but leaves a 3.5" jump, because it is itself 1.8 % high at 20 deg.
3. `erfa.refco` (`A tan z + B tan^3 z`) is within 0.6" everywhere from 10 deg up and joins the low branch
   with a jump of about 0.1". It fails below 10 deg (-21" at 5 deg), so the low branch stays.
4. Clamping: `a` to [0, 90], `P` to [600, 1200], `T` to [-40, 40], no flag. Below the horizon the caller gets
   the horizon refraction (about 35') without being told.

Consumers: IAG50cm's pointing model has fitted refraction terms (`C_Refr_tau`, `C_Refr_dec` in
`GVL_Pointing`), and MONET calls `eq2hor` without pressure or temperature (MONETcommon#18). Any change
here moves what the pointing model has to absorb (section 6).

## 3. Decisions needed

**D1. Formula at 15 deg and above.**

| Option | Above 30 deg | At the join | Cost |
|---|---|---|---|
| a. keep | up to 3.2" high | 5.2" jump | none |
| b. `0.00452` form, move the join up | 0.1"-0.6" | needs a join near 20-25 deg; jump size to be computed | one `TAN`, no `EXPT` |
| c. `A tan z + B tan^3 z`, with `A` and `B` from P and T as in `erfa.refco` (dry, 0.55 um) | 0.1"-0.3" | about 0.1" | port of ~30 lines of SOFA code (BSD-style licence, attribution needed) |

Recommendation: **c**, if the licence and the size of the port are acceptable, otherwise **b**. Pick by
running the acceptance check in step 2 below, not by argument.

Acceptance (for the chosen formula, over P 900-1013 hPa, T -15 to 30 degC): error against the reference at
most 1" from 15 deg up, and at most 3" from 10 to 15 deg; jump at the join at most 0.5"; monotonically
decreasing with altitude. Below 10 deg the behaviour stays as it is and is documented as unverified.

**D2. Where the branches join.** Only relevant for option b or a blend. Decided by the same check.

**D3. Clamping.** Options: (i) keep the clamps and document them, (ii) also add an output such as
`clamped : BOOL` to `FB_CO_REFRACT` so the caller can tell (additive, not breaking), (iii) stop clamping and
pass the input through outside the valid range. Recommendation: (ii), keeping the horizon value for below-horizon altitudes and flagging it.

**D4. Release and versioning.** Refraction values change by up to a few arcseconds above 15 deg, so this is a
behaviour change for every consumer. Which version number and release note, and whether it goes out together
with the other pending breaking change (`alt_is_observed`, IAG50cm#3), is a maintainer decision. Decide
before step 4.

## 4. Steps

1. **Check the source equations.** Someone with the Explanatory Supplement (2013), p. 280, checks eq. 7.90
   and 7.91 against `CO_REFRACT_FORWARD` and the `0.00452` form. Result goes into this plan (one line).
   Blocking for option b only.
2. **Rank the candidates.** Extend `testing/check_refraction_model.py` with the candidate formulas of D1
   (and D2's join) and the acceptance check above. Output: a table like section 2 for each candidate and a
   pass or fail line. Deliverable: the chosen formula plus its error table, appended to this plan.
   Independent cross-check of the reference itself against a published refraction table, if one can be
   found, before trusting it for the final decision.
3. **Implement.** In `CO_REFRACT_FORWARD.TcPOU`: the new formula, the corrected comment (measured accuracy,
   not 0.5"), the documented clamps. In `FB_CO_REFRACT.TcPOU`: the `clamped` output if D3 says so. Keep
   `testing/astrobrot_port.py` in sync.
4. **Tests and goldens.**
   - Regenerate the goldens: `testing/golden_astro.py`, then update `FB_CO_REFRACT_Tests`, the refraction
     cases in `FB_EQ2HOR_Tests` and `FB_HOR2EQ_Tests` (every golden computed with refraction on above
     15 deg moves by more than the 1e-7 deg tolerance), and `check_refraction_roundtrip.py`.
   - New tests: the value at 15 deg from both sides (jump within the acceptance limit), monotonicity over a
     grid, values from the acceptance table at a few altitudes, the clamp behaviour and flag.
   - The iteration in `FB_CO_REFRACT` must still converge in a few steps; `check_refraction_roundtrip.py`
     already asserts it.
5. **Run.** `AstroBROTTests` on the user-mode runtime (rebuild and reinstall the library first).
6. **Consumers.** Note the change in IAG50cm#3 and MONETcommon#18; do not bump their library reference
   until step 7.
7. **Telescope.** Open a "Verify" issue (labels `on site`, `hardware test`, as for the other fixes):
   compare pointing residuals against altitude before and after, with the pointing model's refraction
   terms as they are, and again after refitting. Only then release.
8. **Docs.** README, the code review status line, the fleet open-items list.

## 5. Order and effort

Steps 1 and 2 first, they decide the formula (about half a day each, step 1 depends on someone with the
book). Steps 3 and 4 are one session once the formula is chosen. Steps 5 to 7 depend on runtime and
telescope access, not on effort.

## 6. Risks and unknowns

- **The reference is my model.** If it is biased in a way that matters, the ranking in step 2 could pick
  the wrong formula. The cross-check in step 2 and `erfa.refco` agreeing with it within 0.6" from 10 deg up
  are the mitigations.
- **Pointing model absorption.** The IAG50cm refraction coefficients were fitted with a library that used
  the wrong default temperature (Kelvin fed as Celsius, finding H1, fixed on `develop` but not released).
  The fitted terms may compensate a refraction error, and this change moves it again. After release, the
  telescope check in step 7 decides whether the pointing model has to be refitted.
- **Below 10 deg** the model is unverified in every option (the reference is weakest there, and the low
  branch is off by up to 5.6" at 5 deg in cold air). Out of scope, documented.
- **Equation numbers.** 7.90 and 7.91 were never checked against the book (step 1).
- **Nothing has been run on a PLC.** Port results only, until step 5.

## 7. Outcome of the implementation

- **D1, D2.** `testing/check_refraction_model.py` ranks the candidates against the plan's acceptance limits (P 900
  to 1013 hPa, T -15 to 30 degC). Old code: worst error 5.9", jump 5.7", not monotonic, FAIL. `0.00452` form:
  worst error 4.0", jump 3.8", FAIL. `erfa.refco` joined at 15 deg: worst error 0.67", jump 0.53", FAIL by 0.03".
  `erfa.refco` from 16 deg with a linear blend from 14 deg: worst error 0.64" from 15 deg up, 1.9" from 10 to
  15 deg, no jump, monotonic, PASS. Implemented in `CO_REFRACT_FORWARD`.
- **Step 1 (book check) was not needed.** The chosen formula is eraRefco's, whose documentation states 62 mas
  worst case against ray tracing between 15 and 75 deg zenith distance; the `0.00452` form was dropped. The
  low-altitude rational formula is still the one the code always had, its equation number is still unchecked.
- **D3.** `CO_REFRACT_FORWARD` and `FB_CO_REFRACT` have a `clamped` output (additive). Clamp limits unchanged.
- **Licence.** The eraRefco constants are used under ERFA's licence; `NOTICE-erfa.md` carries it.
- **Goldens.** Regenerated with `testing/golden_astro.py` and mapped onto the tests (97 values in four suites,
  which also picks up the 77-term `FB_IAU2000B`, #16). Shifts: 1.8" at 45 deg, about 4" at 20 deg, none at or
  below 10 deg. `FB_CO_NUTATE_Tests` is not covered by `golden_astro.py`; its values moved by at most 3e-8 deg
  (tolerance 1e-7).
- **New tests** in `FB_CO_REFRACT_Tests`: `Forward_Values` (18 values), `Continuous_And_Decreasing`, `Clamped_Flag`.
- **Run:** the library was installed over the installed 0.3.0 copy (backup of the old file kept outside the repo),
  the tests project built with 0 errors, `Run-Tests.ps1` reported 56 cases, 56 passed. This was also the first run of
  the suites added for #15 to #20.
- **Not done:** D4 (release, version), the telescope check (step 7), and informing IAG50cm#3 and MONETcommon#18
  (step 6).
