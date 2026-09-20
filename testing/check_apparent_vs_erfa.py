"""End-to-end ICRS to apparent HA/Dec and Alt/Az vs erfa.atco13 (dut1=0, no refraction). Run: python3 check_apparent_vs_erfa.py"""
import astrobrot_port as port, erfa, math, numpy as np, random
random.seed(2); AS=206264.80624709636; R=math.radians
lon,lat=9.9454,51.5593   # Goettingen-ish
def sep(a1,b1,a2,b2):
    return math.degrees(math.acos(max(-1,min(1,math.sin(R(b1))*math.sin(R(b2))+math.cos(R(b1))*math.cos(R(b2))*math.cos(R(a1-a2))))))*3600
rows=[]
for _ in range(2000):
    jd=random.uniform(2460310.5,2462137.5)   # 2024..2029
    ra=random.uniform(0,360); dec=math.degrees(math.asin(random.uniform(-1,1)))
    u1=math.floor(jd-0.5)+0.5; u2=jd-u1
    aob,zob,hob,dob,rob,eo=erfa.atco13(R(ra),R(dec),0,0,0,0,u1,u2,0.0,R(lon),R(lat),0.0,0,0,0,0,0,0.55)
    ha_ref=math.degrees(hob); dec_ref=math.degrees(dob); alt_ref=90-math.degrees(zob); az_ref=math.degrees(aob)
    ha,d=port.radec2hadec(jd,ra,dec,lon)
    alt,az,_=port.eq2hor(jd,ra,dec,lon,lat)
    # erfa observed HA is measured westwards; check
    e_hd=sep(ha,d,ha_ref,dec_ref); e_ha=((ha-ha_ref+180)%360-180)
    e_hor=sep(az,alt,az_ref,alt_ref)
    rows.append((jd,ra,dec,e_hd,e_hor,alt_ref,e_ha*3600*math.cos(R(d)),az-az_ref))
a=np.array(rows)
print('HA/Dec (apparent) great-circle err arcsec: median %.3f  p95 %.3f  max %.3f'%(np.median(a[:,3]),np.percentile(a[:,3],95),a[:,3].max()))
print('Alt/Az great-circle err arcsec:          median %.3f  p95 %.3f  max %.3f'%(np.median(a[:,4]),np.percentile(a[:,4],95),a[:,4].max()))
# error trend with time and with dec
for lo,hi in [(2460310,2460700),(2460700,2461300),(2461300,2462200)]:
    m=(a[:,0]>=lo)&(a[:,0]<hi); print('  jd %d-%d median %.3f max %.3f'%(lo,hi,np.median(a[m,3]),a[m,3].max()))
i=a[:,3].argmax(); print('worst case jd=%.2f ra=%.2f dec=%.2f err=%.2f"'%(a[i,0],a[i,1],a[i,2],a[i,3]))
