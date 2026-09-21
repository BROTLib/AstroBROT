"""Golden values for the AstroBROTTests suites FB_PRECESS_Tests, FB_RADEC2HADEC_Tests, FB_HADEC2RADEC_Tests,
FB_SUNPOS_Tests and FB_EdgeCases_Tests (TcUnit). Run: python golden_blocks.py [--json]

Two references per case, so a test can fail for the right reason:
  * "port": astrobrot_port.py, the line-by-line Python port of the ST. It reproduces the ST to about 1e-10 deg, so the
    tests pin these values at 1e-7 deg (1e-8 for FB_PRECESS). This catches every change of behaviour.
  * "erfa": the same quantity computed by erfa (SOFA), independent of the port. The tests compare the block against it
    as a great-circle separation with a hard tolerance. This catches a port that is wrong in the same way as the ST,
    and it is the number that says how accurate the block is.

Every value is printed with 17 significant digits so the LREAL literal in the test is exact.
"""
import math, json, sys, warnings
import numpy as np, erfa
import astrobrot_port as p
import golden_astro as g

warnings.filterwarnings('ignore')       # erfa: "dubious year" for dates after the leap second table
R = math.radians
D = math.degrees

# Tolerances against erfa, in degrees, as a great-circle separation. Measured maxima are in the comments.
TOL_PRECESS = 1.0e-5     # 0.036 arcsec; measured 0.009
TOL_HADEC = 2.0e-4       # 0.72 arcsec; measured 0.38 (diurnal aberration, which the ST leaves out, and TT-UTC)
TOL_SUN = 1.5e-3         # 5.4 arcsec; measured 3.2, the IDLAstro documentation gives 7.3 arcsec maximum for 1900-2100
# FB_HADEC2RADEC at exactly dec = +-90: the aberration and nutation corrections are applied in (ra, dec) and d_ra grows
# like 1/cos(dec), so the dec correction is evaluated at a meaningless RA. Measured 4.7 arcsec (north) and 39.4 arcsec
# (south); 0.1 deg away from the pole the error is back at 0.5 arcsec. Pinned so that it cannot get worse unnoticed.
TOL_EXACT_POLE = 1.5e-2  # 54 arcsec
EXACT_POLE_CASES = ('North_pole', 'South_pole')

def sep(a1, b1, a2, b2):
    """Great-circle separation in degrees of two (lon, lat) positions in degrees."""
    h = math.sin(R(b2-b1)/2)**2 + math.cos(R(b1))*math.cos(R(b2))*math.sin(R(a2-a1)/2)**2
    return 2*D(math.asin(math.sqrt(min(1.0, max(0.0, h)))))

def split(jd):
    u1 = math.floor(jd-0.5)+0.5
    return u1, jd-u1

def erfa_eq2hor(jd, ra, dec, lon, lat, dut1=0.0):
    """ICRS -> observed az, alt, HA, Dec (no refraction, no polar motion)."""
    u1, u2 = split(jd)
    aob, zob, hob, dob, rob, eo = erfa.atco13(R(ra), R(dec), 0, 0, 0, 0, u1, u2, dut1, R(lon), R(lat), 0.0, 0, 0, 0, 0, 0, 0.55)
    return D(aob) % 360.0, 90.0-D(zob), D(hob) % 360.0, D(dob)

def erfa_hor2eq(jd, alt, az, lon, lat):
    u1, u2 = split(jd)
    rc, dc = erfa.atoc13('A', R(az), R(90.0-alt), u1, u2, 0.0, R(lon), R(lat), 0.0, 0, 0, 0, 0, 0, 0.55)
    return D(rc) % 360.0, D(dc)

def erfa_hadec2radec(jd, ha, dec, lon, lat, dut1=0.0):
    u1, u2 = split(jd)
    rc, dc = erfa.atoc13('H', R(ha), R(dec), u1, u2, dut1, R(lon), R(lat), 0.0, 0, 0, 0, 0, 0, 0.55)
    return D(rc) % 360.0, D(dc)

def erfa_precess(ra, dec, e1, e2):
    x = np.array([math.cos(R(dec))*math.cos(R(ra)), math.cos(R(dec))*math.sin(R(ra)), math.sin(R(dec))])
    rp1 = erfa.bp06(2451545.0+(e1-2000.0)*365.25, 0.0)[1]
    rp2 = erfa.bp06(2451545.0+(e2-2000.0)*365.25, 0.0)[1]
    y = rp2 @ rp1.T @ x
    return D(math.atan2(y[1], y[0])) % 360.0, D(math.asin(max(-1.0, min(1.0, y[2]))))

def erfa_sun(jd):
    """Apparent RA/Dec of the Sun of date, built like FB_SUNPOS: geometric direction from erfa.epv00, precessed to the
    mean equinox of date, nutation in longitude added, 20.5 arcsec of aberration subtracted, true obliquity."""
    u1, u2 = split(jd)
    pvh, pvb = erfa.epv00(u1, u2)
    xs = -np.array(pvh[0])                                  # heliocentric Earth -> geocentric Sun (ICRS)
    xd = erfa.pmat06(u1, u2) @ xs                           # bias + precession, mean equator of date
    eps_mean = erfa.obl06(u1, u2)
    dpsi, deps = erfa.nut06a(u1, u2)
    ce, se = math.cos(eps_mean), math.sin(eps_mean)
    lon_ecl = math.atan2(ce*xd[1]+se*xd[2], xd[0])          # ecliptic longitude of date
    lon_app = lon_ecl + dpsi - R(20.5/3600.0)
    eps = eps_mean + deps
    ra = math.atan2(math.sin(lon_app)*math.cos(eps), math.cos(lon_app))
    dec = math.asin(math.sin(lon_app)*math.sin(eps))
    return D(ra) % 360.0, D(dec)

# ---------------------------------------------------------------------------------------------- FB_PRECESS
# name: (ra, dec, equinox1, equinox2)
PRECESS = {
    'J2000_to_2026':         (83.63,  22.01, 2000.0, 2026.5),
    'J2000_to_2010_south':   (312.5, -47.3,  2000.0, 2010.0),
    'Both_epochs_not_J2000': (10.0,   20.0,  2010.0, 2020.0),
    'Back_to_J2000':         (10.0,   20.0,  2020.0, 2000.0),
    'From_1950':             (200.0, -30.0,  1950.0, 2000.0),
    'RA_wrap_up':            (359.9999, 10.0, 2000.0, 2050.0),
    'RA_wrap_down':          (0.0001,  10.0, 2000.0, 1950.0),
    'North_pole':            (0.0,    90.0,  2000.0, 2030.0),
    'South_pole':            (0.0,   -90.0,  2000.0, 2030.0),
    'Same_epoch':            (123.4, -56.7,  2015.0, 2015.0),
}

def precess_block():
    out = {}
    for k, (ra, dec, e1, e2) in PRECESS.items():
        r, d, _ = p.precess(ra, dec, e1, e2)
        er, ed = erfa_precess(ra, dec, e1, e2)
        out[k] = {'ra': ra, 'dec': dec, 'eq1': e1, 'eq2': e2, 'port': [r, d], 'erfa': [er, ed],
                  'erfa_tol': TOL_PRECESS, 'sep_port_erfa': sep(r, d, er, ed)}
    return out

# ------------------------------------------------------------------------------------ FB_RADEC2HADEC / HADEC2RADEC
# name: (jd, lat, lon, ra, dec, dut1)
RADEC2HADEC = {
    'Tenerife_2026':       (2461300.75,  28.3, -16.5,  83.63,  22.01, 0.0),
    'Tenerife_low':        (2461300.75,  28.3, -16.5, 130.0,  -10.0,  0.0),
    'South_2010':          (2455197.5,  -30.2, -70.7, 312.5,  -47.3,  0.0),
    'Tenerife_dut1_plus':  (2461300.75,  28.3, -16.5,  83.63,  22.01, 0.9),
    'Tenerife_dut1_minus': (2461300.75,  28.3, -16.5,  83.63,  22.01, -0.9),
    'RA_wrap_low':         (2461300.75,  28.3, -16.5,   0.0001, 22.01, 0.0),
    'RA_wrap_high':        (2461300.75,  28.3, -16.5, 359.9999, 22.01, 0.0),
    'North_pole':          (2461300.75,  28.3, -16.5,   0.0,   90.0,  0.0),
    'South_pole':          (2455197.5,  -30.2, -70.7,   0.0,  -90.0,  0.0),
    'Near_north_pole':     (2461300.75,  28.3, -16.5, 200.0,   89.9,  0.0),
    'Near_south_pole':     (2455197.5,  -30.2, -70.7, 200.0,  -89.9,  0.0),
}
# name: (jd, lat, lon, ha, dec, dut1)
HADEC2RADEC = {
    'Tenerife_2026':       (2461300.75,  28.3, -16.5, 345.0,  22.01, 0.0),
    'Tenerife_low':        (2461300.75,  28.3, -16.5,  30.0, -10.0,  0.0),
    'South_2010':          (2455197.5,  -30.2, -70.7, 100.0, -47.3,  0.0),
    'Tenerife_dut1_plus':  (2461300.75,  28.3, -16.5, 345.0,  22.01, 0.9),
    'Tenerife_dut1_minus': (2461300.75,  28.3, -16.5, 345.0,  22.01, -0.9),
    'HA_wrap_low':         (2461300.75,  28.3, -16.5,   0.0001, 22.01, 0.0),
    'HA_wrap_high':        (2461300.75,  28.3, -16.5, 359.9999, 22.01, 0.0),
    'North_pole':          (2461300.75,  28.3, -16.5, 200.0,   90.0,  0.0),
    'South_pole':          (2455197.5,  -30.2, -70.7, 200.0,  -90.0,  0.0),
    'Near_north_pole':     (2461300.75,  28.3, -16.5, 200.0,   89.9,  0.0),
    'Near_south_pole':     (2455197.5,  -30.2, -70.7, 200.0,  -89.9,  0.0),
}

def radec2hadec_block():
    out = {}
    for k, (jd, lat, lon, ra, dec, dut1) in RADEC2HADEC.items():
        ha, d = p.radec2hadec(jd, ra, dec, lon, dut1)
        _, _, eha, edec = erfa_eq2hor(jd, ra, dec, lon, lat, dut1)
        out[k] = {'jd': jd, 'lat': lat, 'lon': lon, 'ra': ra, 'dec': dec, 'dut1': dut1, 'port': [float(ha), d],
                  'erfa': [eha, edec], 'erfa_tol': TOL_HADEC, 'sep_port_erfa': sep(ha, d, eha, edec)}
    return out

def hadec2radec_block():
    out = {}
    for k, (jd, lat, lon, ha, dec, dut1) in HADEC2RADEC.items():
        r, d = p.hadec2radec(jd, ha, dec, lon, dut1)
        r = float(r) % 360.0
        er, ed = erfa_hadec2radec(jd, ha, dec, lon, lat, dut1)
        out[k] = {'jd': jd, 'lat': lat, 'lon': lon, 'ha': ha, 'dec': dec, 'dut1': dut1, 'port': [r, d],
                  'erfa': [er, ed], 'erfa_tol': TOL_EXACT_POLE if k in EXACT_POLE_CASES else TOL_HADEC,
                  'sep_port_erfa': sep(r, d, er, ed)}
    return out

# ------------------------------------------------------------------------------------------------- FB_SUNPOS
SUNPOS = {
    'Epoch_1900':          2415020.0,
    'J2000':               2451545.0,
    'Start_2010':          2455197.5,
    'Tenerife_2026':       2461300.75,
    'March_equinox_2026':  2461120.5,       # 2026-03-21 00:00 UT, 9 h after the equinox: RA 0.35, Dec +0.15
    'June_solstice_2026':  2461212.5,       # 2026-06-21 00:00 UT, 8 h before the solstice: Dec +23.44
    'Year_2050':           2469807.5,
}

def sunpos_block():
    out = {}
    for k, jd in SUNPOS.items():
        ra, dec, longmed, oblt = p.sunpos_full(jd)
        er, ed = erfa_sun(jd)
        out[k] = {'jd': jd, 'port': [ra, dec, longmed, oblt], 'erfa': [er, ed], 'erfa_tol': TOL_SUN,
                  'sep_port_erfa': sep(ra, dec, er, ed)}
    return out

# ------------------------------------------------------------------ FB_EQ2HOR / FB_HOR2EQ edge cases (FB_EdgeCases_Tests)
# name: (jd, lat, lon, ra, dec)
EQ2HOR = {
    'North_celestial_pole':   (2461300.75,  28.3, -16.5,   0.0,   90.0),
    'South_celestial_pole':   (2455197.5,  -30.2, -70.7,   0.0,  -90.0),
    'RA_wrap_low':            (2461300.75,  28.3, -16.5,   0.0001, 22.01),
    'RA_wrap_high':           (2461300.75,  28.3, -16.5, 359.9999, 22.01),
    'Below_horizon':          (2461300.75,  28.3, -16.5, 200.0,  -60.0),
    'Observer_at_north_pole': (2461300.75,  90.0,   0.0,  83.63,  22.01),
    'Observer_at_south_pole': (2461300.75, -90.0,   0.0,  83.63, -22.01),
    'Observer_on_equator':    (2461300.75,   0.0, -16.5,  83.63,  22.01),
}
# name: (jd, lat, lon, alt, az)
HOR2EQ = {
    'Zenith_az0':             (2461300.75,  28.3, -16.5,  90.0,   0.0),
    'Zenith_az180':           (2461300.75,  28.3, -16.5,  90.0, 180.0),
    'Nadir':                  (2461300.75,  28.3, -16.5, -90.0,   0.0),
    'Horizon_north':          (2461300.75,  28.3, -16.5,   0.0,   0.0),
    'Az_wrap_low':            (2461300.75,  28.3, -16.5,  45.0,   0.0001),
    'Az_wrap_high':           (2461300.75,  28.3, -16.5,  45.0, 359.9999),
    'Observer_at_north_pole': (2461300.75,  90.0,   0.0,  40.0, 100.0),
    'Observer_at_south_pole': (2461300.75, -90.0,   0.0, -20.0, 100.0),
    'Observer_on_equator':    (2461300.75,   0.0, -16.5,  60.0, 250.0),
}

# A star 0.05 deg from the zenith of Tenerife, and the same star moved by 0.72 arcsec in RA. On the sky the two are
# 0.72 * cos(dec) arcsec apart, but their azimuths differ by tens of arcsec: an azimuth difference in degrees is not a
# separation on the sky (it is amplified by 1/cos(alt)). This is the mechanism behind the "40 arcsec outliers".
NEAR_ZENITH = {'jd': 2461300.75, 'lat': 28.3, 'lon': -16.5, 'alt': 89.95, 'az': 30.0, 'dra': 2.0e-4}

def near_zenith():
    n = NEAR_ZENITH
    ra, dec = g.hor2eq(n['jd'], n['alt'], n['az'], n['lon'], n['lat'])
    a1, z1, _ = g.eq2hor(n['jd'], ra, dec, n['lon'], n['lat'])
    a2, z2, _ = g.eq2hor(n['jd'], ra+n['dra'], dec, n['lon'], n['lat'])
    return {'ra': ra, 'dec': dec, 'alt1': a1, 'az1': z1, 'alt2': a2, 'az2': z2,
            'sky_sep': sep(ra, dec, ra+n['dra'], dec), 'out_sep': sep(z1, a1, z2, a2), 'az_diff': (z2-z1+180) % 360-180, **n}

def edge_block():
    out = {'eq2hor': {}, 'hor2eq': {}, 'near_zenith': near_zenith()}
    for k, (jd, lat, lon, ra, dec) in EQ2HOR.items():
        alt, az, ha = g.eq2hor(jd, ra, dec, lon, lat)
        eaz, ealt, _, _ = erfa_eq2hor(jd, ra, dec, lon, lat)
        out['eq2hor'][k] = {'jd': jd, 'lat': lat, 'lon': lon, 'ra': ra, 'dec': dec, 'port': [alt, az],
                            'erfa': [ealt, eaz], 'erfa_tol': TOL_HADEC, 'sep_port_erfa': sep(az, alt, eaz, ealt)}
    for k, (jd, lat, lon, alt, az) in HOR2EQ.items():
        ra, dec = g.hor2eq(jd, alt, az, lon, lat)
        er, ed = erfa_hor2eq(jd, alt, az, lon, lat)
        out['hor2eq'][k] = {'jd': jd, 'lat': lat, 'lon': lon, 'alt': alt, 'az': az, 'port': [ra, dec],
                            'erfa': [er, ed], 'erfa_tol': TOL_HADEC, 'sep_port_erfa': sep(ra, dec, er, ed)}
    return out

def all_blocks():
    return {'precess': precess_block(), 'radec2hadec': radec2hadec_block(), 'hadec2radec': hadec2radec_block(),
            'sunpos': sunpos_block(), 'edge': edge_block()}

def summary(blocks):
    for name, blk in blocks.items():
        recs = list(blk.items()) if name != 'edge' else [(f'{a}/{k}', v) for a in ('eq2hor', 'hor2eq') for k, v in blk[a].items()]
        for k, v in sorted(recs, key=lambda kv: -kv[1]['sep_port_erfa'])[:3]:
            print('%-12s %-32s port vs erfa %.3e deg (%.3f arcsec)' % (name, k, v['sep_port_erfa'], v['sep_port_erfa']*3600))

if __name__ == '__main__':
    blocks = all_blocks()
    if '--json' in sys.argv:
        json.dump(blocks, sys.stdout, indent=1)
    else:
        summary(blocks)
