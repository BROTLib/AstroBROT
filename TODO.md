# TODO

## Installed AstroBROT library out of date relative to source (blocks IAG50cm build)

Rebuilding IAG50cm (on a clean checkout of its `develop` branch, before any
other changes) fails with:

```
FB_TelescopeControl.TcPOU (Decl)(65) : error: C0077: Unbekannter Typ: 'FB_HADEC2RADEC'
FB_TelescopeControl.TcPOU (Decl)(66) : error: C0077: Unbekannter Typ: 'FB_RADEC2HADEC'
```
plus several cascading `C0035` errors for `fbHaDec2RaDec`/`fbRaDec2HaDec` instances
that depend on those types resolving.

**Root cause:** IAG50cm references AstroBROT as an installed library, not live
source:

```xml
<LibraryReference Include="AstroBROT,0.3.0,BROT">
  <Namespace>AstroBROT</Namespace>
</LibraryReference>
```

Both `FB_HADEC2RADEC` and `FB_RADEC2HADEC` exist in this repo's current source
(`AstroBROT/AstroBROT/POUs/FUNCTION_BLOCKS/`, included in `AstroBROT.plcproj`,
`ProjectVersion` `0.3.0`), so the installed library registered locally under
`AstroBROT,0.3.0,BROT` is a stale build that predates these two function
blocks, despite matching version number `0.3.0`.

**Fix:** rebuild `AstroBROT.library` from current `main`/`develop` source and
reinstall/re-register it in the TwinCAT library repository, so `0.3.0`
actually corresponds to the current source rather than an older build tagged
with the same version.

**Confirmed:** this is pre-existing and unrelated to BROTLib's FB_Axis/
FB_BaseAxis unification work (BROTLib PR #1, HalfBROT PR #1, IAG50cm PR #1) -
the identical error reproduces on a clean `develop` checkout of IAG50cm before
any of those changes.
