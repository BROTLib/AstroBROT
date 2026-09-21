# AstroBROT

AstroBROT is the **astronomical calculations library** of the BROT project —
the real-time celestial-mechanics and coordinate-transformation layer for the
BROTLib-based robotic telescope control system. It is written in IEC 61131-3
Structured Text for the **Beckhoff TwinCAT 3** platform (version 0.3.0).

The algorithms are ported from established astronomical references:
[IDLAstro](https://github.com/wlandsman/IDLAstro) (NASA/GSFC), **NOVAS F3.1**
(USNO), **SOFA** (IAU) and Meeus, *Astronomical Algorithms*. AstroBROT is
consumed by BROTLib and, through it, by every telescope application in the BROT
ecosystem (HalfBROT, MONETcommon, MONETN, MONETS, MONETRoof, IAG50cm).

---

## Repository layout

```
AstroBROT/
├── AstroBROT.sln                  # TwinCAT solution
├── AstroBROT/
│   ├── AstroBROT.tsproj           # TwinCAT system project
│   ├── AstroBROT/
│   │   ├── AstroBROT.plcproj      # PLC library project
│   │   ├── PlcTask.TcTTO          # PLC task
│   │   ├── DUTs/E_TestState.TcDUT # Test-state enumeration
│   │   └── POUs/
│   │       ├── MAIN.TcPOU
│   │       ├── FUNCTION_BLOCKS/   # FB_* astronomical algorithms
│   │       └── FUNCTIONS/         # F_* / utility functions
│   └── _Boot/                     # Boot projects for TwinCAT RT (x86/x64), CE7 (ARMV7)
├── AstroBROTTests/                # TcUnit tests (separate solution, see its README)
│   ├── AstroBROTTests.sln
│   ├── tools/                     # Install-TcUnit.ps1, Run-Tests.ps1
│   └── vendor/tcunit.library      # TcUnit 1.2.0.0
├── testing/                       # Python port, erfa cross-checks, golden values, check_plc_vs_astropy.py
├── testing/                       # Python port, erfa checks, golden_astro.py (source of the test values)
└── README.md
```

---

## Function blocks (coordinate and celestial mechanics)

| Function block | Description |
|---|---|
| `FB_EQ2HOR` | Equatorial (RA/Dec, J2000) → Horizontal (Alt/Az) conversion |
| `FB_HOR2EQ` | Horizontal (Alt/Az) → Equatorial (RA/Dec) conversion. Input `alt_is_observed` (default TRUE) says whether `alt` is measured, so refraction is removed. It replaces `refract_to_observed`, whose default `TRUE` had the opposite meaning (breaking change, callers passing `refract_to_observed` must switch to `alt_is_observed := NOT refract_to_observed`) |
| `FB_RADEC2HADEC` | ICRS RA/Dec → apparent Hour Angle / Declination |
| `FB_HADEC2RADEC` | Apparent Hour Angle / Declination → ICRS RA/Dec |
| `FB_PRECESS` | Precession between epochs (Capitaine et al. 2003) |
| `FB_IAU2000B` | IAU 2000B nutation model (~1 mas accuracy) |
| `FB_SUNPOS` | Apparent solar position from Julian Date |
| `FB_HADEC2ALTAZ` | Hour Angle / Dec → Alt/Az via spherical trigonometry |
| `FB_ALTAZ2HADEC` | Alt/Az → Hour Angle / Dec |
| `FB_CO_NUTATE` | RA/Dec correction due to nutation |
| `FB_CO_ABERRATION` | RA/Dec correction due to annual aberration |
| `FB_CO_REFRACT` | Atmospheric refraction correction. Output `clamped` is TRUE when altitude, pressure or temperature was outside the model's range and had to be limited |

## Functions

| Function | Description |
|---|---|
| `JD2LST` | Julian Date (UTC) → Local Sidereal Time; optional `dut1` (UT1−UTC in seconds, default 0) |
| `CT2LST` | Civil Time → Local Mean Sidereal Time |
| `DateTime2JD` | TwinCAT `TIMESTRUCT` → Julian Date |
| `ATAN2` | Four-quadrant arctangent |
| `TEN` | DMS (degrees-minutes-seconds) → decimal degrees |
| `CO_REFRACT_FORWARD` | Forward atmospheric refraction model (dry air, 0.55 um): rational formula below 14 deg, ERFA `eraRefco` constants from 16 deg, blended in between; within 0.7" of a ray trace from 15 deg up, unverified below 10 deg. Output `clamped`. See `NOTICE-erfa.md` |

---

## Usage

The function blocks are pure calculation blocks: instantiate, set the input
coordinates/epochs/Julian dates, call once per PLC cycle (or on demand) and
read the outputs. No I/O or hardware dependencies are required, which makes the
library portable across all TwinCAT targets.

All `jd` inputs are Julian Dates on the UTC time scale. The sidereal time
(`JD2LST` and the blocks that call it) needs UT1, so the blocks take an optional
`dut1` input (UT1−UTC in seconds, from IERS bulletins, |dut1| < 0.9). It defaults
to 0, which treats UTC as UT1 and can be off by up to ~13.5″ of RA. Precession,
nutation and aberration use `jd` as TT, where the ~69 s offset is negligible.

## Testing

`testing/check_plc_vs_astropy.py` cross-checks the blocks **on a live PLC** against astropy over ADS (pyads): it
writes inputs to the `MAIN` test harness (`JD2LST`, `EQ2HOR`, `HOR2EQ` and an `EQ2HOR` -> `HOR2EQ` round trip per
`E_TestState`), reads back the results and compares them as great-circle separations on the sky, with thresholds and an
exit code. It replaces the former notebook `BROT_test.ipynb` (still in the git history); the AmsNetId is an argument
(`--net-id`), and with `dut1` = 0 on both sides it runs offline. Measured on the TwinCAT user-mode runtime, 500 random
cases each in 2026: JD2LST within 0.004 s of astropy's mean sidereal time; EQ2HOR and HOR2EQ median 0.35″ and maximum
0.65″ (astropy's diurnal aberration and polar motion are what remains); round trip maximum 0.08″. The old notebook's
"azimuth outliers up to 40″" was a difference of azimuth angles, not a separation on the sky (near the zenith or nadir it
is amplified by 1/cos(alt): in the run above a 0.65″ separation shows up as 11.5″ of azimuth at an altitude of -89.3°);
it did not reproduce: a re-run of the notebook itself (500 cases, IERS data, sky above the horizon) gave at most 3.8″ of
raw azimuth difference and 1.1″ of separation. The original figure was recorded before the fixes of #6, #9, #10 and #12,
so its cause is unknown; do not quote it. Needs `pip install pyads astropy numpy`. The library's own `MAIN` did not enter
run mode on the user-mode runtime in this check (reason not found), so the runs above used a project with the same
`MAIN` symbols that calls the installed library.

`AstroBROTTests/` holds TcUnit tests for every block and helper function (`FB_EQ2HOR`, `FB_HOR2EQ`, `FB_RADEC2HADEC`,
`FB_HADEC2RADEC`, `FB_PRECESS`, `FB_SUNPOS`, `FB_CO_REFRACT`, `FB_CO_ABERRATION`, `FB_CO_NUTATE`, `FB_ALTAZ2HADEC` and
the helper functions; 138 test cases). They run the compiled library on the TwinCAT user-mode runtime
and check the results against golden values from the Python port and, with hard tolerances, against erfa (SOFA), including
the celestial poles, observers at the poles, the zenith, RA / azimuth wrap-around and out-of-range angles, plus behaviour
the `MAIN` harness cannot show: blocks must not modify their inputs or keep state between calls. Setup, how to run and the known gaps are in
[AstroBROTTests/README.md](AstroBROTTests/README.md). Not wired into CI: the runtime needs a trial license that
cannot be renewed unattended.

## Dependencies

Beckhoff system libraries: `Tc2_Standard`, `Tc2_Math`, `Tc2_System`,
`Tc2_Utilities`, `Tc3_Module` (a `TcUnit` v1.2.0 artifact sits in
`_Libraries/` but is not referenced by the project).

## Building and deployment

The library is built with TwinCAT 3.1 in TwinCAT XAE (PLC task 10 ms,
priority 20, runs the `MAIN` test harness; compiled library v0.3.0, company
`BROT`, referenced by consumers as `AstroBROT, * (BROT)`). Boot projects for
`TwinCAT RT (x86)`, `TwinCAT RT (x64)` and `TwinCAT CE7 (ARMV7)` are included
under `_Boot/`.
