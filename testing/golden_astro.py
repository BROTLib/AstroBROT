"""Golden values for AstroBROTTests (TcUnit). Run: python golden_astro.py

The expected values in the tests come from astrobrot_port.py, the Python port that check_apparent_vs_erfa.py,
check_refraction_roundtrip.py and check_time_precess.py validate against erfa (SOFA). The port is extended here
with the nutate / aberration switches of FB_EQ2HOR and FB_HOR2EQ. Re-run after changing an algorithm and paste
the printed values into the tests (AstroBROTTests/AstroBROTTests/POUs/FB_*_Tests.TcPOU).

Every value is printed with 17 significant digits so the LREAL literal in the test is exact.
"""
import math, json, sys
import astrobrot_port as p

d2r = p.d2r
def ang(a, b): return abs((a - b + 180) % 360 - 180)

def eq2hor(jd, ra, dec, lon, lat, nut=True, abr=True, refract=False, altitude=0.0, to_obs=True, dut1=0.0):
    ra_pre, dec_pre, _ = p.precess(ra, dec, 2000.0, (jd-2451545.0)/365.25+2000.0)
    dra, ddec, eps, dpsi, _ = p.co_nutate(jd, ra_pre, dec_pre)
    dra_a, ddec_a = p.co_aberration(jd, ra_pre, dec_pre, eps)
    r = ra_pre + (dra_a if abr else 0) + (dra if nut else 0)
    dc = dec_pre + (ddec_a if abr else 0) + (ddec if nut else 0)
    last = p.jd2lst(jd, lon, dut1) + dpsi*math.cos(eps)/3600      # d_psi is always part of the sidereal time
    ha = (last - r) % 360.0
    alt, az = p.hadec2altaz(ha, dc, lat)
    if refract: alt, _ = p.co_refract(alt, altitude, to_obs=to_obs)
    return alt, az, ha

def hor2eq(jd, alt, az, lon, lat, nut=True, abr=True, ws=False, refract=False, altitude=0.0, alt_is_observed=True, dut1=0.0):
    if ws: az = az - 180.0
    if refract: alt, _ = p.co_refract(alt, altitude, to_obs=not alt_is_observed)
    ha, dec = p.altaz2hadec(alt, az, lat)
    dpsi, deps = p.iau2000b(jd); eps = p.eps_true(jd, deps)
    last = p.jd2lst(jd, lon, dut1) + dpsi*math.cos(eps)/3600
    ra = last - ha
    dra, ddec, _, _, _ = p.co_nutate(jd, ra, dec)
    dra_a, ddec_a = p.co_aberration(jd, ra, dec, eps)
    ra = ra - ((dra_a if abr else 0) + (dra if nut else 0))
    dc = dec - ((ddec_a if abr else 0) + (ddec if nut else 0))
    r, d, _ = p.precess(ra, dc, (jd-2451545.0)/365.25+2000.0, 2000.0)
    return r % 360.0, d

DUT1S = (0.9, -0.9)      # UT1-UTC in seconds, the extremes of the IERS range

# name: (jd, lat, lon, altitude m, ra, dec)
CASES = {
    'Tenerife_2026':   (2461300.75, 28.3,  -16.5, 2400.0,  83.63, 22.01),   # high in the sky
    'Tenerife_low':    (2461300.75, 28.3,  -16.5, 2400.0, 130.0, -10.0),    # about 20 deg altitude, refraction matters
    'South_2010':      (2455197.5, -30.2,  -70.7, 2700.0, 312.5, -47.3),    # southern site, other epoch
}

if __name__ == '__main__':
    out = {}
    for name, (jd, lat, lon, h, ra, dec) in CASES.items():
        out[name] = {'jd': jd, 'lat': lat, 'lon': lon, 'altitude': h, 'ra': ra, 'dec': dec}
        for nut in (True, False):
            for abr in (True, False):
                a, z, ha = eq2hor(jd, ra, dec, lon, lat, nut, abr)
                out[name][f'eq2hor_nut{int(nut)}_abr{int(abr)}'] = {'alt': a, 'az': z, 'ha': ha}
        a, z, ha = eq2hor(jd, ra, dec, lon, lat, refract=True, altitude=h, to_obs=True)
        out[name]['eq2hor_refract_to_observed'] = {'alt': a, 'az': z}
        a, z, ha = eq2hor(jd, ra, dec, lon, lat, refract=True, altitude=h, to_obs=False)
        out[name]['eq2hor_refract_to_geometric'] = {'alt': a, 'az': z}
        for dut1 in DUT1S:
            a, z, ha = eq2hor(jd, ra, dec, lon, lat, dut1=dut1)
            out[name][f'eq2hor_dut1_{dut1:+.1f}'] = {'alt': a, 'az': z, 'ha': ha}
    # HOR2EQ inputs are fixed alt/az values, not the outputs above, so a common error cannot cancel out
    HOR = {'Tenerife_2026': (52.0, 200.0), 'Tenerife_low': (21.0, 130.0), 'South_2010': (63.5, 310.0)}
    for name, (alt, az) in HOR.items():
        jd, lat, lon, h, _, _ = CASES[name]
        o = out[name]; o['hor_alt'] = alt; o['hor_az'] = az
        for nut in (True, False):
            for abr in (True, False):
                r, d = hor2eq(jd, alt, az, lon, lat, nut, abr)
                o[f'hor2eq_nut{int(nut)}_abr{int(abr)}'] = {'ra': r, 'dec': d}
        for dut1 in DUT1S:
            r, d = hor2eq(jd, alt, az, lon, lat, dut1=dut1)
            o[f'hor2eq_dut1_{dut1:+.1f}'] = {'ra': r, 'dec': d}
        r, d = hor2eq(jd, alt, az, lon, lat, ws=True)
        o['hor2eq_ws'] = {'ra': r, 'dec': d}
        r, d = hor2eq(jd, alt, az, lon, lat, ws=True, refract=True, altitude=h, alt_is_observed=True)
        o['hor2eq_ws_refract'] = {'ra': r, 'dec': d}
        r, d = hor2eq(jd, alt, az, lon, lat, refract=True, altitude=h, alt_is_observed=True)
        o['hor2eq_refract_observed'] = {'ra': r, 'dec': d}
        r, d = hor2eq(jd, alt, az, lon, lat, refract=True, altitude=h, alt_is_observed=False)
        o['hor2eq_refract_geometric'] = {'ra': r, 'dec': d}
    # JD2LST (lon 0 / 9.945 deg): jd, lon, dut1
    out['jd2lst'] = {f'{jd}_{lon}_{dut1:+.1f}': p.jd2lst(jd, lon, dut1)
                     for jd in (2461300.75, 2455197.5) for lon in (0.0, 9.945392608768366) for dut1 in (0.0, 0.9, -0.9)}
    # FB_CO_REFRACT: (old_alt, altitude, pressure, temperature or None)
    refr = {}
    for label, (alt, h, P, T) in {
        'alt45_sea':        (45.0,   0.0,    0.0, None),
        'alt10_sea':        (10.0,   0.0,    0.0, None),
        'alt3_high':        (3.0,  2400.0,   0.0, None),
        'alt20_P_T0':       (20.0,   0.0, 1000.0, 0.0),    # 0.0 deg C is a valid temperature
        'alt20_P_Tminus15': (20.0,   0.0,  900.0, -15.0),
    }.items():
        refr[label] = {'in': alt, 'altitude': h, 'pressure': P, 'temperature': T,
                       'to_geometric': p.co_refract(alt, h, P, T, to_obs=False)[0],
                       'to_observed':  p.co_refract(alt, h, P, T, to_obs=True, eps=0.001)[0]}
    out['refract'] = refr
    # FB_CO_ABERRATION (ra/dec precessed to the date); eps = 0 in the FB means "calculate it"
    for name in ('Tenerife_2026', 'South_2010'):
        jd, lat, lon, h, ra, dec = CASES[name]
        ra_pre, dec_pre, _ = p.precess(ra, dec, 2000.0, (jd-2451545.0)/365.25+2000.0)
        _, _, eps, _, _ = p.co_nutate(jd, ra_pre, dec_pre)
        dra, ddec = p.co_aberration(jd, ra_pre, dec_pre, eps)
        out['aberration_' + name] = {'jd': jd, 'ra': ra_pre, 'dec': dec_pre, 'eps': eps, 'd_ra': dra, 'd_dec': ddec}
    json.dump(out, sys.stdout if '--json' in sys.argv else open('golden_astro.json', 'w'), indent=1)
    if '--json' not in sys.argv:
        for k, v in out.items():
            if isinstance(v, dict) and 'eq2hor_nut1_abr1' in v:
                a = v.get('eq2hor_nut1_abr1'); print(k, 'alt/az', a['alt'], a['az'])
        print('refract:', {k: (round(v['to_geometric'], 6), round(v['to_observed'], 6)) for k, v in out['refract'].items()})
        for k in ('aberration_Tenerife_2026', 'aberration_South_2010'):
            print(k, 'd_ra/d_dec [arcsec]:', out[k]['d_ra']*3600, out[k]['d_dec']*3600)
        print('wrote golden_astro.json')
