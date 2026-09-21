"""Generates the TcUnit suites for the blocks that had no tests: FB_PRECESS, FB_RADEC2HADEC, FB_HADEC2RADEC,
FB_SUNPOS and the pole / zenith / wrap-around cases of FB_EQ2HOR and FB_HOR2EQ (FB_EdgeCases_Tests).

Run: python gen_block_tests.py

Writes AstroBROTTests/AstroBROTTests/AstroBROTTests/POUs/FB_*_Tests.TcPOU with the golden values of golden_blocks.py
inlined (see there for what "port" and "erfa" mean and where the tolerances come from). The POU and method ids are
derived from the names, so regenerating changes only the numbers. The older suites (FB_EQ2HOR_Tests, ...) are
written by hand and are not touched. Re-run after changing an algorithm, then check the diff.
"""
import math, os, uuid
import golden_blocks as gb

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'AstroBROTTests', 'AstroBROTTests', 'AstroBROTTests', 'POUs')
NS = uuid.UUID('6f1c2f6e-6d0e-4a54-9b0d-5d3a9c1e7a11')
TOL_PORT = 1.0e-7        # deg, 0.36 mas; the port reproduces the ST to about 1e-10
TOL_PRECESS_PORT = 1.0e-8
TOL_REL = 1.0e-9         # deg, for "these two calls must give the same answer"
CRLF = '\r\n'

def lit(x):
    if isinstance(x, bool): return 'TRUE' if x else 'FALSE'
    s = repr(float(x))
    if 'e' in s or 'E' in s:
        m, e = s.lower().split('e')
        if '.' not in m: m += '.0'
        return '%sE%d' % (m, int(e))
    return s

def guid(*parts):
    return '{' + str(uuid.uuid5(NS, '/'.join(parts))) + '}'

class Method:
    def __init__(self, name, body, variables=(), private=True, params=()):
        self.name, self.body, self.variables, self.params, self.private = name, body, list(variables), list(params), private

class Suite:
    def __init__(self, name, doc):
        self.name, self.doc, self.tests = name, doc, []
    def test(self, name, variables, body):
        self.tests.append(Method(name, ["TEST('%s');" % name] + body + ['TEST_FINISHED();'], variables))
    def xml(self):
        n = self.name
        helpers = [
            Method('CheckNear', ['AssertEquals_LREAL(Expected := fExpected, Actual := fActual, Delta := fDelta, Message := sName);'],
                   params=[('fExpected', 'LREAL'), ('fActual', 'LREAL'), ('fDelta', 'LREAL'), ('sName', 'STRING(255)')]),
            Method('CheckAngle', [
                '// angles in degrees, compared modulo 360 so that 359.9999999 and -1.0E-7 are equal',
                'fDiff := fActual - fExpected;',
                'WHILE fDiff > 180.0 DO fDiff := fDiff - 360.0; END_WHILE',
                'WHILE fDiff < -180.0 DO fDiff := fDiff + 360.0; END_WHILE',
                'AssertEquals_LREAL(Expected := 0.0, Actual := fDiff, Delta := fDelta, Message := sName);'],
                   params=[('fExpected', 'LREAL'), ('fActual', 'LREAL'), ('fDelta', 'LREAL'), ('sName', 'STRING(255)')],
                   variables=[('fDiff', 'LREAL')]),
            Method('CheckSeparation', [
                '// great-circle separation of two positions (longitude, latitude in degrees) against a tolerance in degrees;',
                '// a difference of longitudes is not a distance on the sky, this is (haversine formula)',
                'fD2r := 0.017453292519943295;',
                'fHalfDLat := (fLat2 - fLat1) * fD2r * 0.5;',
                'fHalfDLon := (fLon2 - fLon1) * fD2r * 0.5;',
                'fHav := SIN(fHalfDLat) * SIN(fHalfDLat) + COS(fLat1 * fD2r) * COS(fLat2 * fD2r) * SIN(fHalfDLon) * SIN(fHalfDLon);',
                'fSep := 2.0 * ASIN(SQRT(LIMIT(0.0, fHav, 1.0))) / fD2r;',
                'AssertEquals_LREAL(Expected := 0.0, Actual := fSep, Delta := fDelta, Message := sName);'],
                   params=[('fLon1', 'LREAL'), ('fLat1', 'LREAL'), ('fLon2', 'LREAL'), ('fLat2', 'LREAL'), ('fDelta', 'LREAL'), ('sName', 'STRING(255)')],
                   variables=[('fD2r', 'LREAL'), ('fHalfDLat', 'LREAL'), ('fHalfDLon', 'LREAL'), ('fHav', 'LREAL'), ('fSep', 'LREAL')]),
        ]
        o = []
        o.append('﻿<?xml version="1.0" encoding="utf-8"?>')
        o.append('<TcPlcObject Version="1.1.0.1" ProductVersion="3.1.4024.15">')
        o.append('  <POU Name="%s" Id="%s" SpecialFunc="None">' % (n, guid(n)))
        o.append('    <Declaration><![CDATA[' + self.doc.rstrip('\n'))
        o.append('FUNCTION_BLOCK %s EXTENDS TcUnit.FB_TestSuite' % n)
        o.append('VAR')
        o.append('END_VAR')
        o.append(']]></Declaration>')
        o.append('    <Implementation>')
        o.append('      <ST><![CDATA[' + ('\n'.join(t.name + '();' for t in self.tests)))
        o.append(']]></ST>')
        o.append('    </Implementation>')
        for m in helpers + self.tests:
            o.append('    <Method Name="%s" Id="%s">' % (m.name, guid(n, m.name)))
            o.append('      <Declaration><![CDATA[METHOD PRIVATE %s' % m.name)
            if m.params:
                o.append('VAR_INPUT')
                o += ['\t%s\t: %s;' % p for p in m.params]
                o.append('END_VAR')
            if m.variables:
                o.append('VAR')
                o += ['\t%s\t: %s;' % v for v in m.variables]
                o.append('END_VAR')
            o.append(']]></Declaration>')
            o.append('      <Implementation>')
            o.append('        <ST><![CDATA[' + '\n'.join(m.body))
            o.append(']]></ST>')
            o.append('      </Implementation>')
            o.append('    </Method>')
        o.append('  </POU>')
        o.append('</TcPlcObject>')
        return CRLF.join(o) + CRLF

    def write(self):
        path = os.path.join(OUT, self.name + '.TcPOU')
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(self.xml())
        print('wrote', os.path.normpath(path), '(%d tests)' % len(self.tests))

# ------------------------------------------------------------------------------------------------ helpers for bodies
def near(exp, act, tol, name): return "CheckNear(%s, %s, %s, '%s');" % (lit(exp) if not isinstance(exp, str) else exp, act, lit(tol), name)
def angle(exp, act, tol, name): return "CheckAngle(%s, %s, %s, '%s');" % (lit(exp) if not isinstance(exp, str) else exp, act, lit(tol), name)
def _v(x): return x if isinstance(x, str) else lit(x)
def sepchk(lon, lat, alon, alat, tol, name): return "CheckSeparation(%s, %s, %s, %s, %s, '%s');" % (_v(lon), _v(lat), _v(alon), _v(alat), lit(tol), name)
def istrue(cond, name): return "AssertTrue(Condition := %s, Message := '%s');" % (cond, name)

def call(fb, **kw):
    args = ', '.join('%s := %s' % (k, lit(v)) for k, v in kw.items())
    return '%s(%s);' % (fb, args)

FB = lambda name: ('fb', 'AstroBROT.' + name)

# ------------------------------------------------------------------------------------------------------- FB_PRECESS
def precess_suite():
    P = gb.precess_block()
    s = Suite('FB_PRECESS_Tests', '''// Tests for AstroBROT.FB_PRECESS (P03 precession between two Julian epochs, via J2000).
//
// GENERATED by AstroBROT/testing/gen_block_tests.py from testing/golden_blocks.py, do not edit the numbers by hand.
// Every golden case is checked twice: against the Python port of the ST (tolerance 1E-8 deg, catches any change of
// behaviour) and against erfa.bp06 (precession matrix, great-circle separation 1E-5 deg = 0.036 arcsec, catches an
// error the port shares with the ST). The relation tests do not need golden values at all.
//
// FB_PRECESS only rotates between J2000 and one other epoch, so a general epoch pair goes through J2000 (issue #9).''')
    def golden(test, cases):
        body = []
        for k in cases:
            c = P[k]
            body.append(call('fb', ra=c['ra'], dec=c['dec'], equinox1=c['eq1'], equinox2=c['eq2']))
            body.append(angle(c['port'][0], 'fb.ra_precessed', TOL_PRECESS_PORT, k + ' ra'))
            body.append(near(c['port'][1], 'fb.dec_precessed', TOL_PRECESS_PORT, k + ' dec'))
            body.append(sepchk(c['erfa'][0], c['erfa'][1], 'fb.ra_precessed', 'fb.dec_precessed', c['erfa_tol'], k + ' vs erfa'))
        s.test(test, [FB('FB_PRECESS')], body)
    golden('Golden_J2000_To_Date', ['J2000_to_2026', 'J2000_to_2010_south'])
    golden('Golden_Between_Two_Epochs', ['Both_epochs_not_J2000', 'Back_to_J2000', 'From_1950'])
    golden('Golden_RA_Wrap', ['RA_wrap_up', 'RA_wrap_down'])
    golden('Golden_Poles', ['North_pole', 'South_pole'])
    c = P['Same_epoch']
    s.test('Same_Epoch_Is_Identity', [FB('FB_PRECESS')], [
        call('fb', ra=c['ra'], dec=c['dec'], equinox1=2015.0, equinox2=2015.0),
        angle(c['ra'], 'fb.ra_precessed', 1.0e-12, 'ra'),
        near(c['dec'], 'fb.dec_precessed', 1.0e-12, 'dec'),
        call('fb', ra=c['ra'], dec=c['dec'], equinox1=2000.0, equinox2=2000.0),
        angle(c['ra'], 'fb.ra_precessed', 1.0e-12, 'J2000 ra'),
        near(c['dec'], 'fb.dec_precessed', 1.0e-12, 'J2000 dec')])
    s.test('Round_Trip_Through_J2000', [FB('FB_PRECESS'), ('fbBack', 'AstroBROT.FB_PRECESS')], [
        call('fb', ra=83.63, dec=22.01, equinox1=2000.0, equinox2=2050.0),
        'fbBack(ra := fb.ra_precessed, dec := fb.dec_precessed, equinox1 := 2050.0, equinox2 := 2000.0);',
        angle(83.63, 'fbBack.ra_precessed', 1.0E-9, 'J2000 -> 2050 -> J2000 ra'),
        near(22.01, 'fbBack.dec_precessed', 1.0E-9, 'J2000 -> 2050 -> J2000 dec'),
        call('fb', ra=10.0, dec=20.0, equinox1=2010.0, equinox2=2030.0),
        'fbBack(ra := fb.ra_precessed, dec := fb.dec_precessed, equinox1 := 2030.0, equinox2 := 2010.0);',
        angle(10.0, 'fbBack.ra_precessed', 1.0E-9, '2010 -> 2030 -> 2010 ra'),
        near(20.0, 'fbBack.dec_precessed', 1.0E-9, '2010 -> 2030 -> 2010 dec')])
    s.test('Two_Steps_Equal_Precessing_Via_J2000', [FB('FB_PRECESS'), ('fbA', 'AstroBROT.FB_PRECESS'), ('fbB', 'AstroBROT.FB_PRECESS')], [
        '// before the fix of issue #9 a step between two epochs that are both not J2000 gave the wrong result',
        call('fb', ra=10.0, dec=20.0, equinox1=2010.0, equinox2=2020.0),
        call('fbA', ra=10.0, dec=20.0, equinox1=2010.0, equinox2=2000.0),
        'fbB(ra := fbA.ra_precessed, dec := fbA.dec_precessed, equinox1 := 2000.0, equinox2 := 2020.0);',
        angle('fbB.ra_precessed', 'fb.ra_precessed', TOL_REL, 'ra'),
        near('fbB.dec_precessed', 'fb.dec_precessed', TOL_REL, 'dec'),
        '// and 2010 -> 2020 is not the same rotation as 2000 -> 2010',
        call('fbA', ra=10.0, dec=20.0, equinox1=2000.0, equinox2=2010.0),
        istrue('ABS(fb.ra_precessed - fbA.ra_precessed) > 1.0E-6', 'shifted epochs give a different result')])
    s.test('Right_Ascension_Is_Normalised', [FB('FB_PRECESS'), ('fbRef', 'AstroBROT.FB_PRECESS'), ('fbShift', 'AstroBROT.FB_PRECESS')], [
        call('fbRef', ra=350.0, dec=-40.0, equinox1=2000.0, equinox2=2030.0),
        call('fb', ra=-10.0, dec=-40.0, equinox1=2000.0, equinox2=2030.0),
        angle('fbRef.ra_precessed', 'fb.ra_precessed', TOL_REL, 'ra -10 is 350'),
        istrue('fb.ra_precessed >= 0.0 AND fb.ra_precessed < 360.0', 'ra -10 gives 0 <= ra < 360'),
        call('fbShift', ra=710.0, dec=-40.0, equinox1=2000.0, equinox2=2030.0),
        angle('fbRef.ra_precessed', 'fbShift.ra_precessed', TOL_REL, 'ra 710 is 350'),
        istrue('fbShift.ra_precessed >= 0.0 AND fbShift.ra_precessed < 360.0', 'ra 710 gives 0 <= ra < 360')])
    s.test('Inputs_Are_Not_Modified', [FB('FB_PRECESS')], [
        call('fb', ra=83.63, dec=22.01, equinox1=2000.0, equinox2=2026.5),
        near(83.63, 'fb.ra', 1.0E-15, 'ra unchanged'), near(22.01, 'fb.dec', 1.0E-15, 'dec unchanged'),
        near(2000.0, 'fb.equinox1', 1.0E-15, 'equinox1 unchanged'), near(2026.5, 'fb.equinox2', 1.0E-15, 'equinox2 unchanged')])
    c = P['J2000_to_2026']
    s.test('Cyclic_Calls_With_Inputs_Set_Once_Are_Stable', [FB('FB_PRECESS'), ('i', 'INT')], [
        'fb.ra := %s;' % lit(c['ra']), 'fb.dec := %s;' % lit(c['dec']), 'fb.equinox1 := 2000.0;', 'fb.equinox2 := 2026.5;',
        'FOR i := 1 TO 5 DO',
        '\tfb();',
        '\t' + angle(c['port'][0], 'fb.ra_precessed', TOL_PRECESS_PORT, 'cyclic call ra'),
        '\t' + near(c['port'][1], 'fb.dec_precessed', TOL_PRECESS_PORT, 'cyclic call dec'),
        'END_FOR'])
    return s

# ---------------------------------------------------------------------------------------- FB_RADEC2HADEC / FB_HADEC2RADEC
def radec2hadec_suite():
    C = gb.radec2hadec_block()
    s = Suite('FB_RADEC2HADEC_Tests', '''// Tests for AstroBROT.FB_RADEC2HADEC (ICRS RA/Dec -> apparent hour angle / Dec; the block IAG50cm uses).
//
// GENERATED by AstroBROT/testing/gen_block_tests.py from testing/golden_blocks.py, do not edit the numbers by hand.
// Every golden case is checked against the Python port of the ST (1E-7 deg) and against erfa.atco13 as a great-circle
// separation on the (HA, Dec) sphere (2E-4 deg = 0.72 arcsec; the port is 0.2 to 0.4 arcsec away, mostly the diurnal
// aberration that the ST leaves out). The dut1 shift itself is also covered in FB_DUT1_Tests.
//
// Every call assigns all inputs: FB_RADEC2HADEC still writes its precessed and corrected position back into ra and dec
// (issue #8), so these tests must not rely on ra / dec surviving a call.''')
    def golden(test, cases):
        body = []
        for k in cases:
            c = C[k]
            body.append(call('fb', jd=c['jd'], ra=c['ra'], dec=c['dec'], lon=c['lon'], dut1=c['dut1']))
            body.append(angle(c['port'][0], 'fb.ha_out', TOL_PORT, k + ' ha'))
            body.append(near(c['port'][1], 'fb.dec_out', TOL_PORT, k + ' dec'))
            body.append(sepchk(c['erfa'][0], c['erfa'][1], 'fb.ha_out', 'fb.dec_out', c['erfa_tol'], k + ' vs erfa'))
        s.test(test, [FB('FB_RADEC2HADEC')], body)
    golden('Golden_Tenerife_2026', ['Tenerife_2026'])
    golden('Golden_Tenerife_low', ['Tenerife_low'])
    golden('Golden_South_2010', ['South_2010'])
    golden('Golden_Dut1', ['Tenerife_dut1_plus', 'Tenerife_dut1_minus'])
    golden('Golden_RA_Wrap', ['RA_wrap_low', 'RA_wrap_high'])
    golden('Golden_Poles', ['North_pole', 'South_pole'])
    golden('Golden_Near_The_Poles', ['Near_north_pole', 'Near_south_pole'])
    c = C['Tenerife_2026']
    s.test('Right_Ascension_Is_Periodic', [FB('FB_RADEC2HADEC')], [
        '// ra and ra +- 360 are the same position',
        call('fb', jd=c['jd'], ra=c['ra'] - 360.0, dec=c['dec'], lon=c['lon']),
        angle(c['port'][0], 'fb.ha_out', TOL_REL, 'ra - 360 ha'), near(c['port'][1], 'fb.dec_out', TOL_REL, 'ra - 360 dec'),
        call('fb', jd=c['jd'], ra=c['ra'] + 360.0, dec=c['dec'], lon=c['lon']),
        angle(c['port'][0], 'fb.ha_out', TOL_REL, 'ra + 360 ha'), near(c['port'][1], 'fb.dec_out', TOL_REL, 'ra + 360 dec')])
    s.test('Longitude_Is_Periodic', [FB('FB_RADEC2HADEC')], [
        '// lon and lon +- 360 are the same place',
        call('fb', jd=c['jd'], ra=c['ra'], dec=c['dec'], lon=c['lon'] + 360.0),
        angle(c['port'][0], 'fb.ha_out', TOL_REL, 'lon + 360 ha'),
        call('fb', jd=c['jd'], ra=c['ra'], dec=c['dec'], lon=c['lon'] - 360.0),
        angle(c['port'][0], 'fb.ha_out', TOL_REL, 'lon - 360 ha')])
    s.test('Outputs_Stay_In_Range', [FB('FB_RADEC2HADEC'), ('i', 'INT'), ('fRa', 'LREAL')], [
        '// a sweep over the whole RA circle and the declinations up to and including the poles',
        'FOR i := 0 TO 8 DO',
        '\tfRa := 45.0 * i;',
        '\tfb(jd := 2461300.75, ra := fRa, dec := 90.0, lon := -16.5);',
        '\t' + istrue('fb.ha_out >= 0.0 AND fb.ha_out < 360.0 AND fb.dec_out <= 90.0 AND fb.dec_out >= -90.0', 'ra sweep at dec +90 stays in range'),
        '\tfb(jd := 2461300.75, ra := fRa, dec := -90.0, lon := -16.5);',
        '\t' + istrue('fb.ha_out >= 0.0 AND fb.ha_out < 360.0 AND fb.dec_out <= 90.0 AND fb.dec_out >= -90.0', 'ra sweep at dec -90 stays in range'),
        '\tfb(jd := 2461300.75, ra := fRa, dec := 0.0, lon := -16.5);',
        '\t' + istrue('fb.ha_out >= 0.0 AND fb.ha_out < 360.0 AND fb.dec_out <= 90.0 AND fb.dec_out >= -90.0', 'ra sweep at dec 0 stays in range'),
        'END_FOR'])
    s.test('Time_Inputs_Are_Not_Modified', [FB('FB_RADEC2HADEC')], [
        call('fb', jd=c['jd'], ra=c['ra'], dec=c['dec'], lon=c['lon'], dut1=0.5),
        near(c['jd'], 'fb.jd', 0.0, 'jd unchanged'), near(c['lon'], 'fb.lon', 0.0, 'lon unchanged'), near(0.5, 'fb.dut1', 0.0, 'dut1 unchanged')])
    return s

def hadec2radec_suite():
    C = gb.hadec2radec_block()
    s = Suite('FB_HADEC2RADEC_Tests', '''// Tests for AstroBROT.FB_HADEC2RADEC (apparent hour angle / Dec -> ICRS RA/Dec; the block IAG50cm uses).
//
// GENERATED by AstroBROT/testing/gen_block_tests.py from testing/golden_blocks.py, do not edit the numbers by hand.
// Every golden case is checked against the Python port of the ST (1E-7 deg) and against erfa.atoc13 as a great-circle
// separation on the sky (2E-4 deg = 0.72 arcsec).
//
// KNOWN LIMITATION, pinned here on purpose: at exactly dec = +-90 the ST applies the aberration and nutation
// corrections in (ra, dec), d_ra grows like 1/cos(dec) and the dec correction is evaluated at an RA that means
// nothing there. The result then depends on the hour angle and is 4.7 arcsec (north) / 39 arcsec (south) away from
// erfa. Golden_Exact_Poles allows 0.015 deg so that it cannot get worse unnoticed; 0.1 deg from the pole the error is
// back at 0.5 arcsec (Golden_Near_The_Poles, strict tolerance).''')
    def golden(test, cases):
        body = []
        for k in cases:
            c = C[k]
            body.append(call('fb', jd=c['jd'], ha=c['ha'], dec=c['dec'], lon=c['lon'], dut1=c['dut1']))
            if k in gb.EXACT_POLE_CASES:
                body.append('// at exactly dec = +-90 neither ra nor dec is reproducible (d_ra ~ 1/cos(dec) = 1E16, and d_dec is evaluated at that ra), only the bound against erfa is pinned')
            else:
                body.append(angle(c['port'][0], 'fb.ra_out', TOL_PORT, k + ' ra'))
                body.append(near(c['port'][1], 'fb.dec_out', TOL_PORT, k + ' dec'))
            body.append(sepchk(c['erfa'][0], c['erfa'][1], 'fb.ra_out', 'fb.dec_out', c['erfa_tol'], k + ' vs erfa'))
        s.test(test, [FB('FB_HADEC2RADEC')], body)
    golden('Golden_Tenerife_2026', ['Tenerife_2026'])
    golden('Golden_Tenerife_low', ['Tenerife_low'])
    golden('Golden_South_2010', ['South_2010'])
    golden('Golden_Dut1', ['Tenerife_dut1_plus', 'Tenerife_dut1_minus'])
    golden('Golden_HA_Wrap', ['HA_wrap_low', 'HA_wrap_high'])
    golden('Golden_Near_The_Poles', ['Near_north_pole', 'Near_south_pole'])
    golden('Golden_Exact_Poles', ['North_pole', 'South_pole'])
    c = C['Tenerife_2026']
    s.test('Hour_Angle_Is_Periodic', [FB('FB_HADEC2RADEC')], [
        '// ha and ha +- 360 are the same position; the block does not wrap ra before the corrections, so this also covers the wrap of d_ra (issue #10)',
        call('fb', jd=c['jd'], ha=c['ha'] - 360.0, dec=c['dec'], lon=c['lon']),
        angle(c['port'][0], 'fb.ra_out', TOL_REL, 'ha - 360 ra'), near(c['port'][1], 'fb.dec_out', TOL_REL, 'ha - 360 dec'),
        call('fb', jd=c['jd'], ha=c['ha'] + 360.0, dec=c['dec'], lon=c['lon']),
        angle(c['port'][0], 'fb.ra_out', TOL_REL, 'ha + 360 ra'), near(c['port'][1], 'fb.dec_out', TOL_REL, 'ha + 360 dec'),
        istrue('fb.ra_out >= 0.0 AND fb.ra_out < 360.0', 'ra_out is within 0 <= ra < 360')])
    s.test('Longitude_Is_Periodic', [FB('FB_HADEC2RADEC')], [
        call('fb', jd=c['jd'], ha=c['ha'], dec=c['dec'], lon=c['lon'] + 360.0),
        angle(c['port'][0], 'fb.ra_out', TOL_REL, 'lon + 360 ra'),
        call('fb', jd=c['jd'], ha=c['ha'], dec=c['dec'], lon=c['lon'] - 360.0),
        angle(c['port'][0], 'fb.ra_out', TOL_REL, 'lon - 360 ra')])
    s.test('Outputs_Stay_In_Range', [FB('FB_HADEC2RADEC'), ('i', 'INT'), ('fHa', 'LREAL')], [
        'FOR i := -1 TO 8 DO',
        '\tfHa := 45.0 * i;',
        '\tfb(jd := 2461300.75, ha := fHa, dec := 89.9, lon := -16.5);',
        '\t' + istrue('fb.ra_out >= 0.0 AND fb.ra_out < 360.0 AND fb.dec_out <= 90.0 AND fb.dec_out >= -90.0', 'ha sweep at dec +89.9 stays in range'),
        '\tfb(jd := 2461300.75, ha := fHa, dec := -89.9, lon := -16.5);',
        '\t' + istrue('fb.ra_out >= 0.0 AND fb.ra_out < 360.0 AND fb.dec_out <= 90.0 AND fb.dec_out >= -90.0', 'ha sweep at dec -89.9 stays in range'),
        '\tfb(jd := 2461300.75, ha := fHa, dec := 0.0, lon := -16.5);',
        '\t' + istrue('fb.ra_out >= 0.0 AND fb.ra_out < 360.0 AND fb.dec_out <= 90.0 AND fb.dec_out >= -90.0', 'ha sweep at dec 0 stays in range'),
        'END_FOR'])
    s.test('Round_Trip_Through_RADEC2HADEC', [('fbFwd', 'AstroBROT.FB_RADEC2HADEC'), ('fbBack', 'AstroBROT.FB_HADEC2RADEC')], [
        '// the two blocks are only approximate inverses (nutation and aberration are applied at slightly different',
        '// positions), so 1E-6 deg away from the poles and 2E-4 deg (0.72 arcsec) 0.1 deg from a pole',
        call('fbFwd', jd=2461300.75, ra=83.63, dec=22.01, lon=-16.5),
        'fbBack(jd := 2461300.75, ha := fbFwd.ha_out, dec := fbFwd.dec_out, lon := -16.5);',
        sepchk(83.63, 22.01, 'fbBack.ra_out', 'fbBack.dec_out', 1.0e-6, 'Tenerife_2026'),
        call('fbFwd', jd=2455197.5, ra=312.5, dec=-47.3, lon=-70.7),
        'fbBack(jd := 2455197.5, ha := fbFwd.ha_out, dec := fbFwd.dec_out, lon := -70.7);',
        sepchk(312.5, -47.3, 'fbBack.ra_out', 'fbBack.dec_out', 1.0e-6, 'South_2010'),
        call('fbFwd', jd=2461300.75, ra=359.9999, dec=22.01, lon=-16.5),
        'fbBack(jd := 2461300.75, ha := fbFwd.ha_out, dec := fbFwd.dec_out, lon := -16.5);',
        sepchk(359.9999, 22.01, 'fbBack.ra_out', 'fbBack.dec_out', 1.0e-6, 'RA just below 360'),
        call('fbFwd', jd=2461300.75, ra=0.0001, dec=22.01, lon=-16.5),
        'fbBack(jd := 2461300.75, ha := fbFwd.ha_out, dec := fbFwd.dec_out, lon := -16.5);',
        sepchk(0.0001, 22.01, 'fbBack.ra_out', 'fbBack.dec_out', 1.0e-6, 'RA just above 0'),
        call('fbFwd', jd=2461300.75, ra=200.0, dec=89.9, lon=-16.5),
        'fbBack(jd := 2461300.75, ha := fbFwd.ha_out, dec := fbFwd.dec_out, lon := -16.5);',
        sepchk(200.0, 89.9, 'fbBack.ra_out', 'fbBack.dec_out', 2.0e-4, 'near the north pole')])
    s.test('Inputs_Are_Not_Modified', [FB('FB_HADEC2RADEC')], [
        call('fb', jd=c['jd'], ha=c['ha'], dec=c['dec'], lon=c['lon'], dut1=0.5),
        near(c['jd'], 'fb.jd', 0.0, 'jd unchanged'), near(c['ha'], 'fb.ha', 0.0, 'ha unchanged'),
        near(c['dec'], 'fb.dec', 0.0, 'dec unchanged'), near(c['lon'], 'fb.lon', 0.0, 'lon unchanged'), near(0.5, 'fb.dut1', 0.0, 'dut1 unchanged')])
    s.test('Cyclic_Calls_With_Inputs_Set_Once_Are_Stable', [FB('FB_HADEC2RADEC'), ('i', 'INT')], [
        'fb.jd := %s;' % lit(c['jd']), 'fb.ha := %s;' % lit(c['ha']), 'fb.dec := %s;' % lit(c['dec']), 'fb.lon := %s;' % lit(c['lon']),
        'FOR i := 1 TO 5 DO',
        '\tfb();',
        '\t' + angle(c['port'][0], 'fb.ra_out', TOL_PORT, 'cyclic call ra'),
        '\t' + near(c['port'][1], 'fb.dec_out', TOL_PORT, 'cyclic call dec'),
        'END_FOR'])
    return s

# --------------------------------------------------------------------------------------------------------- FB_SUNPOS
def sunpos_suite():
    C = gb.sunpos_block()
    s = Suite('FB_SUNPOS_Tests', '''// Tests for AstroBROT.FB_SUNPOS (apparent position of the Sun, port of IDLAstro sunpos.pro).
//
// GENERATED by AstroBROT/testing/gen_block_tests.py from testing/golden_blocks.py, do not edit the numbers by hand.
// Golden values from the Python port of the ST (1E-7 deg). Independently of the port the position is compared with a
// position built from erfa (epv00 / pmat06 / nut06a): 1.5E-3 deg = 5.4 arcsec, the measured maximum is 3.2 arcsec and
// the IDLAstro documentation states 7.3 arcsec for 1900-2100. The last tests are plain sanity checks (equinox,
// solstice, obliquity, RA rate) that need neither the port nor erfa.''')
    def golden(test, cases):
        body = []
        for k in cases:
            c = C[k]
            body.append(call('fb', jd=c['jd']))
            body.append(angle(c['port'][0], 'fb.ra', TOL_PORT, k + ' ra'))
            body.append(near(c['port'][1], 'fb.dec', TOL_PORT, k + ' dec'))
            body.append(near(c['port'][2], 'fb.longmed', TOL_PORT, k + ' longmed'))
            body.append(near(c['port'][3], 'fb.oblt', TOL_PORT, k + ' oblt'))
            body.append(sepchk(c['erfa'][0], c['erfa'][1], 'fb.ra', 'fb.dec', c['erfa_tol'], k + ' vs erfa'))
        s.test(test, [FB('FB_SUNPOS')], body)
    golden('Golden_Epoch_1900_And_J2000', ['Epoch_1900', 'J2000'])
    golden('Golden_Start_2010', ['Start_2010'])
    golden('Golden_Tenerife_2026', ['Tenerife_2026'])
    golden('Golden_Year_2050', ['Year_2050'])
    golden('Golden_Equinox_And_Solstice_2026', ['March_equinox_2026', 'June_solstice_2026'])
    s.test('Sanity_Equinox_Solstice_Obliquity', [FB('FB_SUNPOS')], [
        '// 2026-03-21 00:00 UT is 9 h after the March equinox: the Sun is at RA about 0.35 deg, Dec about +0.15 deg',
        call('fb', jd=2461120.5),
        angle(0.35, 'fb.ra', 0.3, 'March equinox ra'),
        near(0.15, 'fb.dec', 0.1, 'March equinox dec'),
        '// 2026-06-21 00:00 UT is 8 h before the June solstice: Dec is at its maximum, RA about 89.6 deg',
        call('fb', jd=2461212.5),
        near(23.44, 'fb.dec', 0.02, 'June solstice dec'),
        angle(89.6, 'fb.ra', 0.3, 'June solstice ra'),
        '// true obliquity of the ecliptic in 2026',
        near(23.437, 'fb.oblt', 0.005, 'oblt 2026')])
    s.test('Sanity_Right_Ascension_Advances_About_One_Degree_Per_Day', [FB('FB_SUNPOS'), ('fbNext', 'AstroBROT.FB_SUNPOS'), ('i', 'INT'), ('fStep', 'LREAL')], [
        '// over a year the daily change of RA is between 0.85 and 1.15 deg (0.91 to 1.11 in reality); this also crosses the wrap at 360',
        'FOR i := 0 TO 36 DO',
        '\tfb(jd := 2461041.5 + 10.0 * i);',
        '\tfbNext(jd := 2461042.5 + 10.0 * i);',
        '\tfStep := fbNext.ra - fb.ra;',
        '\tIF fStep < 0.0 THEN fStep := fStep + 360.0; END_IF',
        '\t' + istrue('fStep > 0.85 AND fStep < 1.15', 'daily RA step within 0.85 .. 1.15 deg'),
        '\t' + istrue('fb.ra >= 0.0 AND fb.ra < 360.0 AND ABS(fb.dec) < 23.5', 'ra in range, |dec| below the obliquity'),
        'END_FOR'])
    s.test('Inputs_Are_Not_Modified', [FB('FB_SUNPOS')], [
        call('fb', jd=2461300.75), near(2461300.75, 'fb.jd', 0.0, 'jd unchanged')])
    c = C['Tenerife_2026']
    s.test('Cyclic_Calls_With_Inputs_Set_Once_Are_Stable', [FB('FB_SUNPOS'), ('i', 'INT')], [
        'fb.jd := %s;' % lit(c['jd']),
        'FOR i := 1 TO 5 DO',
        '\tfb();',
        '\t' + angle(c['port'][0], 'fb.ra', TOL_PORT, 'cyclic call ra'),
        '\t' + near(c['port'][1], 'fb.dec', TOL_PORT, 'cyclic call dec'),
        'END_FOR'])
    return s

# ------------------------------------------------------------------------------------------------- FB_EdgeCases_Tests
def edge_suite():
    E = gb.edge_block()
    s = Suite('FB_EdgeCases_Tests', '''// Edge cases of FB_EQ2HOR and FB_HOR2EQ: the celestial poles, an observer at a pole and on the equator, the zenith and
// the nadir, wrap-around of RA and azimuth, positions below the horizon and out-of-range angles.
//
// GENERATED by AstroBROT/testing/gen_block_tests.py from testing/golden_blocks.py, do not edit the numbers by hand.
// Every golden case is checked against the Python port of the ST (1E-7 deg) and against erfa (atco13 / atoc13) as a
// great-circle separation (2E-4 deg = 0.72 arcsec, no refraction, dut1 = 0). Altitude and azimuth are compared as a
// separation on the sky, not as two separate angle differences: near the zenith an azimuth difference is amplified by
// 1 / cos(alt) and says little about the pointing error (Azimuth_Difference_Is_Not_A_Sky_Separation).''')
    for k, c in E['eq2hor'].items():
        s.test('EQ2HOR_' + k, [FB('FB_EQ2HOR')], [
            call('fb', ra=c['ra'], dec=c['dec'], jd=c['jd'], lon=c['lon'], lat=c['lat'], refract=False),
            near(c['port'][0], 'fb.alt', TOL_PORT, k + ' alt'),
            angle(c['port'][1], 'fb.az', TOL_PORT, k + ' az'),
            sepchk(c['erfa'][1], c['erfa'][0], 'fb.az', 'fb.alt', c['erfa_tol'], k + ' vs erfa')])
    for k, c in E['hor2eq'].items():
        s.test('HOR2EQ_' + k, [FB('FB_HOR2EQ')], [
            call('fb', alt=c['alt'], az=c['az'], jd=c['jd'], lon=c['lon'], lat=c['lat'], refract=False),
            angle(c['port'][0], 'fb.ra', TOL_PORT, k + ' ra'),
            near(c['port'][1], 'fb.dec', TOL_PORT, k + ' dec'),
            sepchk(c['erfa'][0], c['erfa'][1], 'fb.ra', 'fb.dec', c['erfa_tol'], k + ' vs erfa')])
    z0, z1 = E['hor2eq']['Zenith_az0'], E['hor2eq']['Zenith_az180']
    s.test('HOR2EQ_Azimuth_Does_Not_Matter_At_The_Zenith', [('fbA', 'AstroBROT.FB_HOR2EQ'), ('fbB', 'AstroBROT.FB_HOR2EQ')], [
        call('fbA', alt=90.0, az=0.0, jd=z0['jd'], lon=z0['lon'], lat=z0['lat'], refract=False),
        call('fbB', alt=90.0, az=180.0, jd=z0['jd'], lon=z0['lon'], lat=z0['lat'], refract=False),
        angle('fbA.ra', 'fbB.ra', TOL_REL, 'ra'), near('fbA.dec', 'fbB.dec', TOL_REL, 'dec'),
        istrue('fbA.dec > 0.0 AND fbA.dec < 90.0', 'the zenith of a northern site has 0 < dec < 90 (no NaN from ASIN)')])
    s.test('HOR2EQ_Azimuth_Is_Periodic', [('fbRef', 'AstroBROT.FB_HOR2EQ'), ('fb', 'AstroBROT.FB_HOR2EQ')], [
        call('fbRef', alt=45.0, az=350.0, jd=2461300.75, lon=-16.5, lat=28.3, refract=False),
        call('fb', alt=45.0, az=-10.0, jd=2461300.75, lon=-16.5, lat=28.3, refract=False),
        angle('fbRef.ra', 'fb.ra', TOL_REL, 'az -10 ra'), near('fbRef.dec', 'fb.dec', TOL_REL, 'az -10 dec'),
        call('fb', alt=45.0, az=710.0, jd=2461300.75, lon=-16.5, lat=28.3, refract=False),
        angle('fbRef.ra', 'fb.ra', TOL_REL, 'az 710 ra'), near('fbRef.dec', 'fb.dec', TOL_REL, 'az 710 dec')])
    c = E['eq2hor']['RA_wrap_low']
    s.test('EQ2HOR_Right_Ascension_Is_Periodic', [('fbRef', 'AstroBROT.FB_EQ2HOR'), ('fb', 'AstroBROT.FB_EQ2HOR')], [
        call('fbRef', ra=83.63, dec=22.01, jd=2461300.75, lon=-16.5, lat=28.3, refract=False),
        call('fb', ra=-276.37, dec=22.01, jd=2461300.75, lon=-16.5, lat=28.3, refract=False),
        near('fbRef.alt', 'fb.alt', TOL_REL, 'ra -276.37 alt'), angle('fbRef.az', 'fb.az', TOL_REL, 'ra -276.37 az'),
        call('fb', ra=443.63, dec=22.01, jd=2461300.75, lon=-16.5, lat=28.3, refract=False),
        near('fbRef.alt', 'fb.alt', TOL_REL, 'ra 443.63 alt'), angle('fbRef.az', 'fb.az', TOL_REL, 'ra 443.63 az')])
    s.test('EQ2HOR_Longitude_Is_Periodic', [('fbRef', 'AstroBROT.FB_EQ2HOR'), ('fb', 'AstroBROT.FB_EQ2HOR')], [
        call('fbRef', ra=83.63, dec=22.01, jd=2461300.75, lon=-16.5, lat=28.3, refract=False),
        call('fb', ra=83.63, dec=22.01, jd=2461300.75, lon=343.5, lat=28.3, refract=False),
        near('fbRef.alt', 'fb.alt', TOL_REL, 'lon 343.5 alt'), angle('fbRef.az', 'fb.az', TOL_REL, 'lon 343.5 az')])
    s.test('EQ2HOR_Outputs_Stay_In_Range', [FB('FB_EQ2HOR'), ('i', 'INT'), ('fDec', 'LREAL')], [
        '// declinations from pole to pole for observers at both poles, on the equator and at a mid latitude',
        'FOR i := -2 TO 2 DO',
        '\tfDec := 45.0 * i;',
        '\tfb(ra := 200.0, dec := fDec, jd := 2461300.75, lon := 0.0, lat := 90.0, refract := FALSE);',
        '\t' + istrue('fb.alt >= -90.0 AND fb.alt <= 90.0 AND fb.az >= 0.0 AND fb.az <= 360.0', 'observer at the north pole'),
        '\tfb(ra := 200.0, dec := fDec, jd := 2461300.75, lon := 0.0, lat := -90.0, refract := FALSE);',
        '\t' + istrue('fb.alt >= -90.0 AND fb.alt <= 90.0 AND fb.az >= 0.0 AND fb.az <= 360.0', 'observer at the south pole'),
        '\tfb(ra := 200.0, dec := fDec, jd := 2461300.75, lon := 0.0, lat := 0.0, refract := FALSE);',
        '\t' + istrue('fb.alt >= -90.0 AND fb.alt <= 90.0 AND fb.az >= 0.0 AND fb.az <= 360.0', 'observer on the equator'),
        '\tfb(ra := 200.0, dec := fDec, jd := 2461300.75, lon := -16.5, lat := 28.3, refract := FALSE);',
        '\t' + istrue('fb.alt >= -90.0 AND fb.alt <= 90.0 AND fb.az >= 0.0 AND fb.az <= 360.0', 'observer at 28.3 deg'),
        'END_FOR'])
    s.test('HOR2EQ_Outputs_Stay_In_Range', [FB('FB_HOR2EQ'), ('i', 'INT'), ('fAlt', 'LREAL')], [
        '// altitudes from nadir to zenith, for observers at both poles, on the equator and at a mid latitude',
        'FOR i := -2 TO 2 DO',
        '\tfAlt := 45.0 * i;',
        '\tfb(alt := fAlt, az := 100.0, jd := 2461300.75, lon := 0.0, lat := 90.0, refract := FALSE);',
        '\t' + istrue('fb.dec >= -90.0 AND fb.dec <= 90.0 AND fb.ra >= 0.0 AND fb.ra < 360.0', 'observer at the north pole'),
        '\tfb(alt := fAlt, az := 100.0, jd := 2461300.75, lon := 0.0, lat := -90.0, refract := FALSE);',
        '\t' + istrue('fb.dec >= -90.0 AND fb.dec <= 90.0 AND fb.ra >= 0.0 AND fb.ra < 360.0', 'observer at the south pole'),
        '\tfb(alt := fAlt, az := 100.0, jd := 2461300.75, lon := 0.0, lat := 0.0, refract := FALSE);',
        '\t' + istrue('fb.dec >= -90.0 AND fb.dec <= 90.0 AND fb.ra >= 0.0 AND fb.ra < 360.0', 'observer on the equator'),
        '\tfb(alt := fAlt, az := 100.0, jd := 2461300.75, lon := -16.5, lat := 28.3, refract := FALSE);',
        '\t' + istrue('fb.dec >= -90.0 AND fb.dec <= 90.0 AND fb.ra >= 0.0 AND fb.ra < 360.0', 'observer at 28.3 deg'),
        'END_FOR'])
    n = E['near_zenith']
    s.test('Azimuth_Difference_Is_Not_A_Sky_Separation', [('fb1', 'AstroBROT.FB_EQ2HOR'), ('fb2', 'AstroBROT.FB_EQ2HOR'), ('fAzDiff', 'LREAL')], [
        '// The review recorded "azimuth outliers up to 40 arcsec" as a coordinate difference. Two positions %.2f arcsec apart on the sky' % (n['sky_sep'] * 3600),
        '// (0.05 deg from the zenith) differ by %.0f arcsec in azimuth: the azimuth difference is amplified by 1 / cos(alt) = %.0f.' % (abs(n['az_diff']) * 3600, 1 / math.cos(math.radians(n['alt1']))),
        '// A raw azimuth difference therefore cannot be used as an accuracy figure; a great-circle separation can.',
        call('fb1', ra=n['ra'], dec=n['dec'], jd=n['jd'], lon=n['lon'], lat=n['lat'], refract=False),
        call('fb2', ra=n['ra'] + n['dra'], dec=n['dec'], jd=n['jd'], lon=n['lon'], lat=n['lat'], refract=False),
        'fAzDiff := fb2.az - fb1.az;',
        near(n['az_diff'], 'fAzDiff', 1.0E-6, 'azimuth difference in degrees'),
        sepchk('fb1.az', 'fb1.alt', 'fb2.az', 'fb2.alt', n['out_sep'] + 1.0e-6, 'separation of the two outputs is the sky separation'),
        istrue('ABS(fAzDiff) > 100.0 * %s' % lit(n['out_sep']), 'the azimuth difference is more than 100 times the separation')])
    return s

if __name__ == '__main__':
    for build in (precess_suite, radec2hadec_suite, hadec2radec_suite, sunpos_suite, edge_suite):
        build().write()
