# AstroBROTTests

TcUnit tests for AstroBROT. A separate PLC project, so no test code ends up in the shipped library. It references
the *installed* AstroBROT (`AstroBROT, * (BROT)`), exactly like a telescope project does.

## What is covered

| Suite | Tests | What it checks |
|---|---|---|
| `FB_EQ2HOR_Tests` | `FB_EQ2HOR` | golden alt/az at three sites, the `nutate` / `aberration` switches, refraction in both directions, inputs left untouched, cyclic calls with inputs set once |
| `FB_HOR2EQ_Tests` | `FB_HOR2EQ` | the same for the reverse transform, plus `ws` (azimuth west from south) and the round trip through `FB_EQ2HOR` |
| `FB_CO_REFRACT_Tests` | `FB_CO_REFRACT` | golden values in both directions, 0.0 degC as a valid temperature, no state kept between calls, out-of-range input, non-positive `epsilon` |
| `FB_CO_ABERRATION_Tests` | `FB_CO_ABERRATION` | golden `d_ra` / `d_dec` at two epochs, `eps` input not modified |

29 test cases in total.

The block tests exist mainly for behaviour that `MAIN` of the library cannot show, because `MAIN` assigns every input on
every call: the blocks must not modify their inputs and must not keep correction deltas between calls (issue #8). The
cyclic tests set the inputs once and call the block repeatedly, like a PLC program would.

Expected values come from [`testing/golden_astro.py`](../testing/golden_astro.py), which builds on
`testing/astrobrot_port.py` (validated against erfa/SOFA by the `check_*.py` scripts) and adds the `nutate` /
`aberration` switches. The tolerance is 1e-7 deg (0.36 mas); the port reproduces the ST to about 1e-10 deg. The
round-trip test uses 1e-6 deg because the two blocks are only approximate inverses (they apply nutation and
aberration at slightly different positions, up to 0.34 mas). Re-run `golden_astro.py` after changing an algorithm and
update the numbers in the tests.

`FB_CO_NUTATE` (RA wrap-around, issue #10) has no suite of its own yet. `FB_HOR2EQ` with `ws` or at low altitude feeds
a negative RA into it, so those cases also need the wrap fix.

## Running the tests

TcBuild only compiles. Running needs a TwinCAT runtime that executes the PLC, plus a (trial) license for it.

**Windows 11 note.** The TwinCAT 3.1 Build 4024 *real-time* runtime does not run on Windows 11
([Beckhoff system requirements](https://infosys.beckhoff.com/content/1033/tc3_overview/6162419083.html)); Run mode
fails with `Init4\RTime: Start Interrupt: Ticker started >> AdsError: 6 (port 200)`. XAE and TcBuild are fine. Use the
beta **user-mode runtime** that ships with TwinCAT instead (`C:\TwinCAT\3.1\Runtimes\UmRT_Default`, see the
`Readme.txt` there for its terms of use).

One-time setup on a machine:

1. Install TcUnit into the local library repository (skip if `Managed Libraries\www.tcunit.org` already exists). This
   starts a hidden XAE instance:
   ```powershell
   .\AstroBROTTests\tools\Install-TcUnit.ps1
   ```
2. Install the current AstroBROT (the tests use the *installed* copy, not the source tree; repeat after every change
   to the library):
   ```powershell
   & "C:\Program Files\Industrial Brains B.V\TcBuild\TcBuild.exe" install AstroBROT.sln -x AstroBROT -p AstroBROT -l AstroBROT.library
   ```
   This replaces the installed library of the same version, so other projects on the machine pick it up.

Every run:

1. Start the user-mode runtime **from its own folder** (`Start.bat` uses the current directory for its config):
   ```powershell
   cd C:\TwinCAT\3.1\Runtimes\UmRT_Default; .\Start.bat
   ```
2. Build, deploy and run. Exit code 0 = all passed, 1 = a test failed, 2 = no result (timeout, or no test case ran):
   ```powershell
   & "C:\Program Files\Industrial Brains B.V\TcBuild\TcBuild.exe" build AstroBROTTests.sln
   .\AstroBROTTests\tools\Run-Tests.ps1
   ```
   It overwrites whatever boot project is on the target runtime (default `192.168.4.1.1.1`, override with
   `-TargetNetId`). Only one run can use the runtime at a time.

Which test failed: the counters are printed, the individual assertions go to the TwinCAT ADS log (XAE error list).
Over ADS every suite instance also exposes `MAIN.<suite>.Tests[i].TestName`, `.TestIsFailed` and `.AssertionMessage`.

To debug interactively instead: open `AstroBROTTests.sln` in XAE, choose the user-mode runtime as target, activate the
configuration, log in and start the PLC. TcUnit prints every result to the error list.

## Things to know

- **Target of `AstroBROT.tsproj`.** The library's own project targets a remote route (`5.146.183.126.1.1`) that does
  not exist on other machines. A headless XAE (TcBuild, the automation scripts here) then stalls with
  `RPC_E_SERVERCALL_RETRYLATER` or loads the project as "unmodeled". Point it at a local target (for example
  `192.168.4.1.1.1`) before running `TcBuild install AstroBROT.sln`. `AstroBROTTests.tsproj` already does.
- **Trial license.** The PLC trial license lasts 7 days and is renewed by hand (captcha). This is why the tests are not
  wired into CI.
- **TcUnit sizing.** TcUnit's defaults allocate about 78 MB of PLC data, which the user-mode runtime cannot start. The
  project overrides them to 32 / 32 / 256 in the `TcUnit` reference (`AstroBROTTests.plcproj`). TcUnit needs
  tests-per-suite <= suites, or it does not compile. If you add a suite with more than 32 tests or 256 assertions,
  raise the numbers together.
- **Every test method is called every PLC cycle.** Each test registers itself with `TEST('name')` on its first line and
  ends with `TEST_FINISHED()`; a method without the `TEST()` call is never counted. Locals of a method are
  re-initialised on every call, so a test that needs state across calls has to keep it within one method call.
- **Function blocks from another project.** Inputs that are not passed keep their declared defaults, so `fb(ra := ...)`
  is enough. Functions need every argument.
- **Identifier pitfall.** ST is case-insensitive: a parameter named `sIn` collides with the `SIN` operator and produces a
  wall of parse errors.
- `.tmc`, `_Boot/`, `_CompileInfo/` and `_Libraries/` are generated and ignored by git.
