"""Refraction units, refraction loop, HOR2EQ direction, RA wrap and round trips. Run: python3 check_refraction_roundtrip.py"""
import astrobrot_port as port, erfa, math, numpy as np, random
random.seed(3); R=math.radians
# 1. Kelvin/Celsius mismatch in default temperature
print('default T path: CO_REFRACT passes T=283 to forward fn (expects degC) -> clamped to', min(max(283.0,-40),40),'degC')
print(' alt  R(T=10C,correct)  R(default path)  diff arcsec')
for a in (5,10,15,30,45,60):
    r_ok=port.refract_forward(a,1010.0,10.0)*3600
    r_bug=port.co_refract(a,0.0,to_obs=False)[0]; r_bug=(a-r_bug)*3600
    print(f'{a:4d} {r_ok:10.2f} {r_bug:14.2f} {r_ok-r_bug:10.2f}')
# 2. compare forward model to erfa refco (10C, 1010 hPa, rh 0, 0.55um)
refa,refb=erfa.refco(1010.0,10.0,0.0,0.55)
for a in (10,30,60):
    z=R(90-a); ref_erfa=(refa*math.tan(z)+refb*math.tan(z)**3)*206264.806
    print(f'alt {a}: erfa refraction {ref_erfa:.1f}" vs ExSup formula {port.refract_forward(a,1010.0,10.0)*3600:.1f}"')
# 3. continuity at 15 deg
print('continuity at a=15: below %.4f" above %.4f"'%(port.refract_forward(14.9999999)*3600,port.refract_forward(15.0)*3600))
# 4. iteration: epsilon=0 and NaN
_,n=port.co_refract(30.0,to_obs=True,eps=0.25); print('normal iterations:',n)
_,n=port.co_refract(30.0,to_obs=True,eps=0.0,maxit=100000); print('epsilon=0 -> iterations before my cap:',n,'(loop would never exit)')
_,n=port.co_refract(30.0,to_obs=True,eps=1e-12,maxit=100000); print('epsilon=1e-12" -> iterations:',n)
nan=float('nan'); print('NaN alt: abs(last-cur)*3600<eps is', abs(nan-nan)*3600<0.25, '-> UNTIL never true')
# 5. HOR2EQ with default refract_to_observed=TRUE doubles refraction
lon,lat=9.9454,51.5593; jd=2461000.3; ra,dec=120.0,35.0
alt,az,_=port.eq2hor(jd,ra,dec,lon,lat,refract=True,to_obs=True)
for flag in (True,False):
    r2,d2=port.hor2eq(jd,alt,az,lon,lat,refract=True,to_obs=flag)
    e=math.degrees(math.acos(min(1,math.sin(R(d2))*math.sin(R(dec))+math.cos(R(d2))*math.cos(R(dec))*math.cos(R(r2-ra)))))*3600
    print(f'HOR2EQ round-trip after EQ2HOR(refract) with refract_to_observed={flag}: error {e:.1f}"  (alt={alt:.2f})')
# 6. wrap: d_ra magnitude from co_nutate near RA=0
dra,ddec,_,_,_=port.co_nutate(2461000.3,0.001,10.0); print('co_nutate d_ra at ra=0.001 deg:',dra)
dra,ddec,_,_,_=port.co_nutate(2461000.3,-5.0,10.0); print('co_nutate d_ra at ra=-5 deg (as HADEC2RADEC can pass):',dra)
# 7. HADEC2RADEC round trip incl. wrap
worst=0;bad=0
for _ in range(3000):
    jd=random.uniform(2460310.5,2462137.5); ra=random.uniform(0,360);dec=random.uniform(-89,89)
    ha,d=port.radec2hadec(jd,ra,dec,lon); r2,d2=port.hadec2radec(jd,ha,d,lon)
    e=math.degrees(math.acos(max(-1,min(1,math.sin(R(d2))*math.sin(R(dec))+math.cos(R(d2))*math.cos(R(dec))*math.cos(R(r2-ra))))))*3600
    worst=max(worst,e)
print('RADEC2HADEC->HADEC2RADEC round trip max err arcsec:',worst)
