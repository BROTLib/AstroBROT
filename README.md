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
├── testing/BROT_test.ipynb        # Jupyter notebook with algorithm cross-checks
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

`testing/BROT_test.ipynb` is a Python (pyads) validation notebook that
cross-checks the ported algorithms **on the live PLC** against reference
implementations (astropy, PyAstronomy): it writes test inputs to the `MAIN`
test harness (which executes `JD2LST`, `EQ2HOR`, `HOR2EQ` and an `EQ2EQ`
round trip per `E_TestState`), reads back the results and compares them.
Recorded accuracy (tested at the IAG 50 cm telescope): JD2LST within half a
second of astropy; EQ2HOR altitude error below ~2″, azimuth mostly below 5″
(with systematic outliers up to 40″); 500 random sky cases for EQ2HOR/HOR2EQ
and 100 round-trip cases.

`AstroBROTTests/` holds TcUnit tests for the transform blocks and their helpers (`FB_EQ2HOR`, `FB_HOR2EQ`,
`FB_CO_REFRACT`, `FB_CO_ABERRATION`, `FB_CO_NUTATE` and the helper functions; 56 test cases). They run the compiled library on the TwinCAT user-mode runtime
and check the results against golden values from the Python port, plus behaviour the `MAIN` harness cannot show:
blocks must not modify their inputs or keep state between calls. Setup, how to run and the known gaps are in
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
