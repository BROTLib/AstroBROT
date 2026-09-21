"""Check JD2LST, FB_PRECESS and ASIN edge cases against erfa. Run: python3 check_time_precess.py"""
import astrobrot_port as port, erfa, math, numpy as np, random
random.seed(1)
AS=206264.80624709636
# --- JD2LST vs erfa gmst82 (UT1=UTC assumed)
for jd in [2461000.5,2461123.25]:
    g=erfa.gmst82(jd,0.0)*180/math.pi
    print('JD2LST-gmst82 (arcsec, lon=0):',((port.jd2lst(jd,0.0)-g+180)%360-180)*3600)
# --- precess vs erfa bp06 rp
worst=0
for _ in range(300):
    jd=random.uniform(2451545-20*365.25,2451545+40*365.25)
    ra=random.uniform(0,360);dec=random.uniform(-89,89)
    Jn=(jd-2451545.0)/365.25+2000.0
    r,d,x2=port.precess(ra,dec,2000.0,Jn)
    rb,rp,rbp=erfa.bp06(jd,0.0)
    x=np.array([math.cos(dec*port.d2r)*math.cos(ra*port.d2r),math.cos(dec*port.d2r)*math.sin(ra*port.d2r),math.sin(dec*port.d2r)])
    ref=rp@x
    worst=max(worst,math.acos(min(1,x2@ref))*AS)
print('precess vs erfa rp (mean J2000->date), max sep arcsec (t from 2000: 20yr back..40yr fwd):',worst)
# --- precess round trip and misuse
print('round trip:',port.precess(*port.precess(10,20,2000.0,2030.0)[:2],2030.0,2000.0)[:2])
# --- precess between two arbitrary epochs (via J2000) vs erfa rp2 @ rp1.T
worst=0
for _ in range(300):
    e1=random.uniform(1980,2040);e2=random.uniform(1980,2040)
    ra=random.uniform(0,360);dec=random.uniform(-89,89)
    r,d,x2=port.precess(ra,dec,e1,e2)
    x=np.array([math.cos(dec*port.d2r)*math.cos(ra*port.d2r),math.cos(dec*port.d2r)*math.sin(ra*port.d2r),math.sin(dec*port.d2r)])
    rp1=erfa.bp06(2451545.0+(e1-2000.0)*365.25,0.0)[1]; rp2=erfa.bp06(2451545.0+(e2-2000.0)*365.25,0.0)[1]
    worst=max(worst,math.acos(min(1,x2@(rp2@rp1.T@x)))*AS)
print('precess e1->e2 vs erfa, max sep arcsec (random epochs 1980..2040):',worst)
assert worst<0.01, worst
assert port.precess(10,20,2010.0,2020.0)[:2]!=port.precess(10,20,2000.0,2010.0)[:2]   # was identical before the fix
print('2010->2020 vs 2000->2010 (must differ):',port.precess(10,20,2010.0,2020.0)[:2],port.precess(10,20,2000.0,2010.0)[:2])
print('identity equinox1=equinox2:',port.precess(10,20,2015.0,2015.0)[:2])
print('via J2000 == direct two-step:',port.precess(10,20,2010.0,2020.0)[:2],port.precess(*port.precess(10,20,2010.0,2000.0)[:2],2000.0,2020.0)[:2])
# --- ASIN overflow at poles
bad=0;tot=0
for jd in np.linspace(2451545,2470000,400):
    Jn=(jd-2451545.0)/365.25+2000.0
    _,_,x2=port.precess(0.0,90.0,2000.0,Jn); tot+=1
    if x2[2]>1.0: bad+=1
print('precess dec=90: z>1 (ASIN NaN) in',bad,'of',tot)
zs=0;n=0
for _ in range(20000):
    alt=random.uniform(-90,90);az=random.uniform(0,360);lat=random.uniform(-90,90)
    l,a=math.radians(lat),math.radians(alt)
    sd=math.sin(l)*math.sin(a)+math.cos(l)*math.cos(a)*math.cos(math.radians(az)); n+=1
    if abs(sd)>1: zs+=1
print('altaz2hadec |sin dec|>1 in',zs,'of',n,'; zenith at lat=90/45/-30:',
  [math.sin(math.radians(l))**2+math.cos(math.radians(l))**2 for l in (90,45,-30,51.56)])
