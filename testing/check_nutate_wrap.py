"""Check FB_CO_NUTATE d_ra is wrapped to +-180 (issue #10). Run: python3 check_nutate_wrap.py"""
import astrobrot_port as port, random
random.seed(1)
worst=0
for _ in range(2000):
    jd=random.uniform(2451545-20*365.25,2451545+40*365.25)
    ra=random.uniform(-360,720); dec=random.uniform(-60,60)   # unwrapped input, as FB_HADEC2RADEC can pass
    dra=port.co_nutate(jd,ra,dec)[0]
    assert -180<=dra<180, (jd,ra,dec,dra)
    worst=max(worst,abs(dra))
print('max |d_ra| over unwrapped ra in (-360,720), dec +-60 (deg):',worst)
assert worst<0.02, worst   # nutation shifts RA by at most ~20"/cos(60) = 0.011 deg
for ra in (-5.0,0.001,359.999,355.0,365.0):
    print('d_ra at ra=%s: %.6f deg'%(ra,port.co_nutate(2461000.3,ra,10.0)[0]))
