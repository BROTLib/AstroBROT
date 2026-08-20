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
├── testing/BROT_test.ipynb        # Jupyter notebook with algorithm cross-checks
└── README.md
```

---

## Function blocks (coordinate and celestial mechanics)

| Function block | Description |
|---|---|
| `FB_EQ2HOR` | Equatorial (RA/Dec, J2000) → Horizontal (Alt/Az) conversion |
| `FB_HOR2EQ` | Horizontal (Alt/Az) → Equatorial (RA/Dec) conversion |
| `FB_RADEC2HADEC` | ICRS RA/Dec → apparent Hour Angle / Declination |
| `FB_HADEC2RADEC` | Apparent Hour Angle / Declination → ICRS RA/Dec |
| `FB_PRECESS` | Precession between epochs (Capitaine et al. 2003) |
| `FB_NUTATE` | IAU 1980 nutation theory (63 terms) |
| `FB_IAU2000B` | IAU 2000B nutation model (~1 mas accuracy) |
| `FB_SUNPOS` | Apparent solar position from Julian Date |
| `FB_HADEC2ALTAZ` | Hour Angle / Dec → Alt/Az via spherical trigonometry |
| `FB_ALTAZ2HADEC` | Alt/Az → Hour Angle / Dec |
| `FB_CO_NUTATE` | RA/Dec correction due to nutation |
| `FB_CO_ABERRATION` | RA/Dec correction due to annual aberration |
| `FB_CO_REFRACT` | Atmospheric refraction correction |

## Functions

| Function | Description |
|---|---|
| `JD2LST` | Julian Date → Local Sidereal Time |
| `CT2LST` | Civil Time → Local Mean Sidereal Time |
| `DateTime2JD` | TwinCAT `TIMESTRUCT` → Julian Date |
| `ATAN2` | Four-quadrant arctangent |
| `POLY` | Polynomial evaluation (4 coefficients) |
| `TEN` | DMS (degrees-minutes-seconds) → decimal degrees |
| `CO_REFRACT_FORWARD` | Forward atmospheric refraction model |

---

## Usage

The function blocks are pure calculation blocks: instantiate, set the input
coordinates/epochs/Julian dates, call once per PLC cycle (or on demand) and
read the outputs. No I/O or hardware dependencies are required, which makes the
library portable across all TwinCAT targets.

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
