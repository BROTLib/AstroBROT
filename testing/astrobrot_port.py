"""Python port of the AstroBROT ST code, for cross-checking against erfa (SOFA).

This is a hand port, not the compiled ST. Tables are parsed from the .TcPOU sources.
Keep it in sync with the ST when the ST changes. Used by the check_*.py scripts here.
"""
import re, math
import numpy as np
import os
SRC=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','AstroBROT','AstroBROT','POUs','FUNCTION_BLOCKS')+os.sep
d2r=math.pi/180.0
def modabs(x,m): return x % m
def lmod(x,m): return math.fmod(x,m)

def _arrays(fname, n):
    txt=open(SRC+fname).read()
    out={}
    for m in re.finditer(r'^\s*(\w+)\s*:\s*ARRAY\[1\.\.%d\] OF LREAL := \[(.*?)\];'%n, txt, re.M):
        out[m.group(1)]=np.array([float(v) for v in m.group(2).split(',')])
    return out
NUT=_arrays('FB_IAU2000B.TcPOU',77)

def iau2000b(jd, nterms=77, bias=True):
    t=(jd-2451545.0)/36525.0
    asec2r=math.pi/(180*3600); a360=3600*360
    m_l=lmod(485868.249036+t*1717915923.2178,a360)*asec2r
    m_l_=lmod(1287104.79305+t*129596581.0481,a360)*asec2r
    m_f=lmod(335779.526232+t*1739527262.8478,a360)*asec2r
    m_d=lmod(1072260.70369+t*1602961601.2090,a360)*asec2r
    m_om=lmod(450160.398036-t*6962890.5431,a360)*asec2r
    dp=de=0.0
    N=NUT
    for i in range(nterms):
        th=lmod(N['l'][i]*m_l+N['l_'][i]*m_l_+N['f'][i]*m_f+N['d'][i]*m_d+N['om'][i]*m_om,2*math.pi)
        s,c=math.sin(th),math.cos(th)
        dp+=(N['A'][i]+N['A1'][i]*t)*s+N['A2'][i]*c
        de+=(N['B'][i]+N['B1'][i]*t)*c+N['B2'][i]*s
    dpsi=dp*1e-7-(0.0433585 if bias else 0); deps=de*1e-7-(0.0084531 if bias else 0)
    return dpsi,deps

def eps_true(jd,d_eps):
    T=(jd-2451545.0)/36525.0
    eps0=23.4392911*3600-46.8150*T-0.00059*T**2+0.001813*T**3
    return (eps0+d_eps)/3600*d2r

def co_nutate(jd,ra,dec):
    d_psi,d_eps=iau2000b(jd); eps=eps_true(jd,d_eps)
    ce,se=math.cos(eps),math.sin(eps); d2as=math.pi/(180*3600)
    x=math.cos(ra*d2r)*math.cos(dec*d2r); y=math.sin(ra*d2r)*math.cos(dec*d2r); z=math.sin(dec*d2r)
    x2=x-(y*ce+z*se)*d_psi*d2as; y2=y+(x*ce*d_psi-z*d_eps)*d2as; z2=z+(x*se*d_psi+y*d_eps)*d2as
    rad=math.sqrt(x2*x2+y2*y2+z2*z2); xy=math.sqrt(x2*x2+y2*y2)
    ra2=0.0; dec2=0.0
    if xy==0 and z!=0: dec2=math.asin(z2/rad); ra2=0.0
    if xy!=0: ra2=math.atan2(y2,x2); dec2=math.asin(z2/rad)
    ra2=modabs(ra2/d2r,360.0); dec2=dec2/d2r
    return modabs(ra2-ra+180.0,360.0)-180.0, dec2-dec, eps, d_psi, d_eps

def sunpos(jd):
    t=(jd-2415020.0)/36525.0
    l=(279.696678+lmod(36000.768925*t,360.0))*3600.0
    me=358.475844+lmod(35999.049750*t,360.0)
    l+=(6910.1-17.2*t)*math.sin(me*d2r)+72.3*math.sin(2*me*d2r)
    mv=212.603219+lmod(58517.803875*t,360.0)
    C=lambda a: math.cos(a*d2r)
    l+=4.8*C(299.1017+mv-me)+5.5*C(148.3133+2*mv-2*me)+2.5*C(315.9433+2*mv-3*me)+1.6*C(345.2533+3*mv-4*me)+1.0*C(318.15+3*mv-5*me)
    mm=319.529425+lmod(19139.858500*t,360.0)
    l+=2.0*C(343.8883-2*mm+2*me)+1.8*C(200.4017-2*mm+me)
    mj=225.328328+lmod(3034.6920239*t,360.0)
    l+=7.2*C(179.5317-mj+me)+2.6*C(263.2167-mj)+2.7*C(87.1450-2*mj+2*me)+1.6*C(109.4933-2*mj+me)
    d=350.7376814+lmod(445267.11422*t,360.0)
    l+=6.5*math.sin(d*d2r)
    l+=6.4*math.sin((231.19+20.20*t)*d2r)
    l=lmod(l+2592000.0,1296000.0)
    return l/3600.0

def co_aberration(jd,ra,dec,eps):
    T=(jd-2451545.0)/36525.0; k=20.49552
    sunlon=sunpos(jd)
    e=0.016708634-0.000042037*T-0.0000001267*T**2
    peri=102.93735+1.71946*T+0.00046*T**2
    cd,sd=math.cos(dec*d2r),math.sin(dec*d2r)
    ce,te=math.cos(eps),math.tan(eps)
    cp,sp=math.cos(peri*d2r),math.sin(peri*d2r)
    cs,ss=math.cos(sunlon*d2r),math.sin(sunlon*d2r)
    ca,sa=math.cos(ra*d2r),math.sin(ra*d2r)
    t1=(ca*cs*ce+sa*ss)/cd; t2=(ca*cp*ce+sa*sp)/cd
    t3=cs*ce*(te*cd-sa*sd)+ca*sd*ss; t4=cp*ce*(te*cd-sa*sd)+ca*sd*sp
    return (-k*t1+e*k*t2)/3600,(-k*t3+e*k*t4)/3600

def precess(ra,dec,eq1,eq2):
    """Precess between any two epochs, in two steps via J2000 like the ST. A step whose epoch is 2000.0 is skipped."""
    sr=d2r/3600
    rr,dr=ra*d2r,dec*d2r
    x=np.array([math.cos(dr)*math.cos(rr),math.cos(dr)*math.sin(rr),math.sin(dr)])
    if eq1!=eq2:
        for step,epoch in enumerate((eq1,eq2)):
            if epoch==2000.0: continue
            t=0.01*(epoch-2000.0)
            EPS0=sr*84381.406
            PSIA=sr*((((-0.0000000951*t+0.000132851)*t-0.00114045)*t-1.0790069)*t+5038.481507)*t
            OMEGAA=sr*((((0.0000003337*t-0.000000467)*t-0.00772503)*t+0.0512623)*t-0.025754)*t+EPS0
            CHIA=sr*((((-0.0000000560*t+0.000170663)*t-0.00121197)*t-2.3814292)*t+10.556403)*t
            SA,CA=math.sin(EPS0),math.cos(EPS0); SB,CB=math.sin(-PSIA),math.cos(-PSIA)
            SC,CC=math.sin(-OMEGAA),math.cos(-OMEGAA); SD,CD=math.sin(CHIA),math.cos(CHIA)
            r=np.zeros((3,3))
            r[0,0]=CD*CB-SB*SD*CC; r[0,1]=CD*SB*CA+SD*CC*CB*CA-SA*SD*SC; r[0,2]=CD*SB*SA+SD*CC*CB*SA+CA*SD*SC
            r[1,0]=-SD*CB-SB*CD*CC; r[1,1]=-SD*SB*CA+CD*CC*CB*CA-SA*CD*SC; r[1,2]=-SD*SB*SA+CD*CC*CB*SA+CA*CD*SC
            r[2,0]=SB*SC; r[2,1]=-SC*CB*CA-SA*CC; r[2,2]=-SC*CB*SA+CC*CA
            x=r.T@x if step==0 else r@x     # step 0: eq1 -> J2000, step 1: J2000 -> eq2
    return modabs(math.atan2(x[1],x[0])/d2r,360.0), math.asin(x[2])/d2r, x

def jd2lst(jd,lon,dut1=0.0):
    ut1=jd+dut1/86400.0
    T=(ut1-2451545.0)/36525.0
    th=280.46061837+360.98564736629*(ut1-2451545.0)+0.000387933*T*T-T**3/38710000.0
    return modabs(th+lon,360.0)

def hadec2altaz(ha,dec,lat,ws=False):
    sh,ch=math.sin(ha*d2r),math.cos(ha*d2r); sd,cd=math.sin(dec*d2r),math.cos(dec*d2r); sl,cl=math.sin(lat*d2r),math.cos(lat*d2r)
    x=-ch*cd*sl+sd*cl; y=-sh*cd; z=ch*cd*cl+sd*sl; r=math.hypot(x,y)
    az=modabs(math.atan2(y,x)/d2r,360.0); alt=math.atan2(z,r)/d2r
    if ws: az=modabs(az+180,360)
    return alt,az

def altaz2hadec(alt,az,lat):
    a,z,l=alt*d2r,az*d2r,lat*d2r
    ha=math.atan2(-math.sin(z)*math.cos(a),-math.cos(z)*math.sin(l)*math.cos(a)+math.sin(a)*math.cos(l))/d2r
    if ha<0: ha+=360
    ha=modabs(ha,360.0)
    sd=math.sin(l)*math.sin(a)+math.cos(l)*math.cos(a)*math.cos(z)
    return ha, math.asin(sd)/d2r      # unclamped, like the ST

def refract_clamped(a,P,T):
    return not (0.0<=a<=90.0 and 600.0<=P<=1200.0 and -40.0<=T<=40.0)

def refract_forward(a,P=1010.0,T=0.0):
    """CO_REFRACT_FORWARD: Explanatory Supplement rational formula below 14 deg, eraRefco (dry, 0.55 um) from 16 deg, linear blend between."""
    a=min(max(a,0.0),90.0); P=min(max(P,600.0),1200.0); T=min(max(T,-40.0),40.0)
    lo=hi=0.0
    if a<16.0: lo=P/(T+273.0)*(0.1594+0.0196*a+0.00002*a*a)/(1.0+0.505*a+0.0845*a*a)
    if a>14.0:
        tk=T+273.15; gamma=7.902649953145277E-5*P/tk; beta=4.4474E-6*tk; t=math.tan((90.0-a)*d2r)
        hi=(gamma*(1.0-beta)*t-gamma*(beta-gamma/2.0)*t**3)/d2r
    if a<=14.0: return lo
    if a>=16.0: return hi
    w=(a-14.0)/2.0
    return (1.0-w)*lo+w*hi

def co_refract(old_alt,altitude=0.0,pressure=0.0,temperature=None,eps=0.25,to_obs=False,maxit=10):
    # temperature in degC (None = estimate from altitude), like FB_CO_REFRACT with temperature_set
    if not (-1e6<old_alt<1e6): return old_alt,0     # NaN/Inf rejected, passed through unchanged
    if temperature is None: temperature=211.5-273.0 if altitude>11000 else 283.0-273.0-0.0065*altitude
    if pressure==0: pressure=1010.0*(1-6.5/288000*altitude)**5.255
    if not to_obs: return old_alt-refract_forward(old_alt,pressure,temperature),0
    eps=eps if eps>0.001 else 0.001                 # min_epsilon (also catches NaN)
    cur=old_alt+refract_forward(old_alt,pressure,temperature); n=0
    while True:
        last=cur; cur=old_alt+refract_forward(cur,pressure,temperature); n+=1
        if abs(last-cur)*3600<eps or n>=maxit: break
    return cur,n

def radec2hadec(jd,ra,dec,lon):
    ra_pre,dec_pre,_=precess(ra,dec,2000.0,(jd-2451545.0)/365.25+2000.0)
    dra,ddec,eps,dpsi,_=co_nutate(jd,ra_pre,dec_pre)
    dra_a,ddec_a=co_aberration(jd,ra_pre,dec_pre,eps)
    r=ra_pre+dra_a+dra; d=dec_pre+ddec_a+ddec
    last=jd2lst(jd,lon)+dpsi*math.cos(eps)/3600
    return modabs(last-r,360.0), d

def hadec2radec(jd,ha,dec,lon):
    dpsi,deps=iau2000b(jd); eps=eps_true(jd,deps)
    last=jd2lst(jd,lon)+dpsi*math.cos(eps)/3600
    ra=last-ha                            # not wrapped in the ST
    dra,ddec,_,_,_=co_nutate(jd,ra,dec)
    dra_a,ddec_a=co_aberration(jd,ra,dec,eps)
    ra=ra-(dra_a+dra); dc=dec-(ddec_a+ddec)
    r,d,_=precess(ra,dc,(jd-2451545.0)/365.25+2000.0,2000.0)
    return r,d

def eq2hor(jd,ra,dec,lon,lat,refract=False,altitude=0.0,to_obs=True):
    ha,d=radec2hadec(jd,ra,dec,lon)
    alt,az=hadec2altaz(ha,d,lat)
    if refract: alt,_=co_refract(alt,altitude,to_obs=to_obs)
    return alt,az,ha

def hor2eq(jd,alt,az,lon,lat,refract=False,altitude=0.0,alt_is_observed=True):
    if refract: alt,_=co_refract(alt,altitude,to_obs=not alt_is_observed)
    ha,dec=altaz2hadec(alt,az,lat)
    ra,d=hadec2radec(jd,ha,dec,lon)
    return ra,d
