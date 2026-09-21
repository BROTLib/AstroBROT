"""Compares the AstroBROT blocks running on a live PLC with astropy. Replaces testing/BROT_test.ipynb.

Run: python check_plc_vs_astropy.py [--net-id 192.168.4.1.1.1] [--seed 1]
Needs: pip install pyads astropy numpy, and a PLC whose MAIN has the harness symbols (estate, lat, lon, ra, dec, alt,
az, jd1, lst1; estate 1 EQ2HOR, 2 HOR2EQ, 3 EQ2EQ, 4 JD2LST, the PLC sets it back to 0 when it is done). That is
AstroBROT/POUs/MAIN.TcPOU, or any project with the same symbols on ADS port 851.

What is compared, always as a great-circle separation on the sky (never as separate azimuth and altitude / RA and Dec
differences: near the zenith an azimuth difference is amplified by 1/cos(alt), which is how the old notebook came to
report "outliers up to 40 arcsec"):
  * JD2LST against astropy's mean sidereal time,
  * FB_EQ2HOR against astropy ICRS -> AltAz (no refraction),
  * FB_HOR2EQ against astropy AltAz -> ICRS,
  * the EQ2HOR -> HOR2EQ round trip on the PLC against its own input.
The harness passes dut1 = 0, so astropy is told UT1 = UTC as well; astropy then needs no IERS download and the script runs
offline. Polar motion is not modelled by the PLC either (astropy is left with zero polar motion).

Exit code 0 if every maximum is below its threshold, 1 if not, 2 if the PLC did not answer.
"""
import argparse, sys, time
import numpy as np
import pyads
from astropy import units as u
from astropy.coordinates import AltAz, EarthLocation, SkyCoord
from astropy.time import Time
from astropy.utils import iers

iers.conf.auto_download = False
iers.conf.iers_degraded_accuracy = 'ignore'      # future dates: no IERS table, use zero polar motion

IDLE, EQ2HOR, HOR2EQ, EQ2EQ, JD2LST = 0, 1, 2, 3, 4
IAG = (51.55931126132681, 9.945392608768366, 200.0)      # lat [deg], lon [deg], height [m] of the IAG 50 cm telescope


class Plc:
    def __init__(self, net_id, port):
        self.c = pyads.Connection(net_id, port)
        self.c.open()
        self.c.read_state()                              # raises if the target does not answer

    def w(self, name, value):
        self.c.write_by_name('MAIN.' + name, float(value), pyads.PLCTYPE_LREAL)

    def r(self, name):
        return self.c.read_by_name('MAIN.' + name, pyads.PLCTYPE_LREAL)

    def run(self, state, timeout=2.0):
        """start a transform and wait until the PLC has processed it (it sets estate back to IDLE)"""
        self.c.write_by_name('MAIN.estate', state, pyads.PLCTYPE_INT)
        deadline = time.time() + timeout
        while self.c.read_by_name('MAIN.estate', pyads.PLCTYPE_INT) != IDLE:
            if time.time() > deadline:
                raise TimeoutError('the PLC did not finish state %d within %.1f s' % (state, timeout))
            time.sleep(0.002)

    def close(self):
        self.c.close()


def separation(lat1, lon1, lat2, lon2):
    """great-circle separation in arcsec of two positions given as (latitude, longitude) in degrees"""
    a1, z1, a2, z2 = np.radians([lat1, lon1, lat2, lon2])
    h = np.sin((a2 - a1) / 2) ** 2 + np.cos(a1) * np.cos(a2) * np.sin((z2 - z1) / 2) ** 2
    return np.degrees(2 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))) * 3600


def random_times(rng, n, start, days):
    return Time(start, scale='utc') + rng.uniform(0, days, n) * u.day


def make_time(t):
    t = Time(t.jd, format='jd', scale='utc')
    t.delta_ut1_utc = 0.0                                # the PLC harness passes dut1 = 0
    return t


def report(name, sep, limit, unit='arcsec', worst=None):
    ok = sep.max() < limit
    print('%-26s n=%-4d median %8.4f  p95 %8.4f  max %8.4f %s  (limit %g)  %s' %
          (name, len(sep), np.median(sep), np.percentile(sep, 95), sep.max(), unit, limit, 'ok' if ok else 'FAILED'))
    if worst is not None and not ok:
        for i in np.argsort(-sep)[:5]:
            print('    ' + worst(i))
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--net-id', default='192.168.4.1.1.1', help='AmsNetId of the PLC (default: the TwinCAT user-mode runtime)')
    ap.add_argument('--port', type=int, default=pyads.PORT_TC3PLC1)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--start', default='2026-01-01', help='start of the random UTC time range')
    ap.add_argument('--days', type=float, default=365.0, help='length of the random time range in days')
    ap.add_argument('--n-eq', type=int, default=500, help='cases for EQ2HOR and for HOR2EQ')
    ap.add_argument('--n-round', type=int, default=100, help='cases for the EQ2HOR -> HOR2EQ round trip')
    ap.add_argument('--n-lst', type=int, default=200, help='cases for JD2LST')
    ap.add_argument('--tol-lst', type=float, default=0.01, help='JD2LST vs astropy, seconds of time (default 0.01)')
    ap.add_argument('--tol-sky', type=float, default=1.0, help='EQ2HOR / HOR2EQ vs astropy, arcsec (default 1.0; measured 0.4)')
    ap.add_argument('--tol-round', type=float, default=0.5, help='round trip, arcsec (default 0.5; measured 0.2, worst near the poles)')
    a = ap.parse_args()

    lat, lon, height = IAG
    loc = EarthLocation(lat=lat * u.deg, lon=lon * u.deg, height=height * u.m)
    rng = np.random.default_rng(a.seed)
    try:
        plc = Plc(a.net_id, a.port)
    except Exception as e:
        print('cannot reach the PLC %s:%d: %s' % (a.net_id, a.port, e))
        return 2
    plc.w('lat', lat); plc.w('lon', lon)
    print('PLC %s, %d/%d/%d cases, seed %d, times %s + %g days, dut1 = 0 on both sides' %
          (a.net_id, a.n_eq, a.n_round, a.n_lst, a.seed, a.start, a.days))
    ok = True
    try:
        # ---- JD2LST
        times = random_times(rng, a.n_lst, a.start, a.days)
        dlst = np.zeros(a.n_lst)
        for i, t in enumerate(times):
            t = make_time(t)
            plc.w('jd1', t.jd); plc.run(JD2LST)
            ref = Time(t.jd, format='jd', scale='utc', location=EarthLocation(lat=lat * u.deg, lon=lon * u.deg))
            ref.delta_ut1_utc = 0.0
            ref_deg = ref.sidereal_time('mean').degree
            dlst[i] = abs((plc.r('lst1') - ref_deg + 180) % 360 - 180) * 240.0        # seconds of time
        ok &= report('JD2LST vs astropy', dlst, a.tol_lst, 'seconds')

        # ---- EQ2HOR
        times = random_times(rng, a.n_eq, a.start, a.days)
        ra = rng.uniform(0, 360, a.n_eq); dec = np.degrees(np.arcsin(rng.uniform(-1, 1, a.n_eq)))
        sep = np.zeros(a.n_eq); res = np.zeros((a.n_eq, 4)); raw_az = np.zeros(a.n_eq)
        for i in range(a.n_eq):
            t = make_time(times[i])
            plc.w('jd1', t.jd); plc.w('ra', ra[i]); plc.w('dec', dec[i]); plc.run(EQ2HOR)
            alt_p, az_p = plc.r('alt'), plc.r('az')
            h = SkyCoord(ra=ra[i] * u.deg, dec=dec[i] * u.deg, frame='icrs').transform_to(AltAz(location=loc, obstime=t))
            sep[i] = separation(alt_p, az_p, h.alt.deg, h.az.deg)
            res[i] = (h.alt.deg, h.az.deg, alt_p, az_p)
            raw_az[i] = abs((az_p - h.az.deg + 180) % 360 - 180) * 3600
        ok &= report('EQ2HOR vs astropy', sep, a.tol_sky, worst=lambda i: 'sep %.3f arcsec at alt %.3f az %.3f (raw azimuth difference %.3f arcsec)' % (sep[i], res[i, 0], res[i, 1], raw_az[i]))
        print('%-26s max raw azimuth difference %.3f arcsec (at alt %.3f); this is not a sky separation' %
              ('', raw_az.max(), res[raw_az.argmax(), 0]))

        # ---- HOR2EQ
        times = random_times(rng, a.n_eq, a.start, a.days)
        alt = np.degrees(np.arcsin(rng.uniform(-1, 1, a.n_eq))); az = rng.uniform(0, 360, a.n_eq)
        sep = np.zeros(a.n_eq)
        for i in range(a.n_eq):
            t = make_time(times[i])
            plc.w('jd1', t.jd); plc.w('alt', alt[i]); plc.w('az', az[i]); plc.run(HOR2EQ)
            ra_p, dec_p = plc.r('ra'), plc.r('dec')
            s = SkyCoord(alt=alt[i] * u.deg, az=az[i] * u.deg, frame=AltAz(location=loc, obstime=t)).transform_to('icrs')
            sep[i] = separation(dec_p, ra_p, s.dec.deg, s.ra.deg)
        ok &= report('HOR2EQ vs astropy', sep, a.tol_sky, worst=lambda i: 'sep %.3f arcsec at alt %.3f az %.3f' % (sep[i], alt[i], az[i]))

        # ---- EQ2EQ round trip on the PLC
        times = random_times(rng, a.n_round, a.start, a.days)
        ra = rng.uniform(0, 360, a.n_round); dec = np.degrees(np.arcsin(rng.uniform(-1, 1, a.n_round)))
        sep = np.zeros(a.n_round)
        for i in range(a.n_round):
            t = make_time(times[i])
            plc.w('jd1', t.jd); plc.w('ra', ra[i]); plc.w('dec', dec[i]); plc.run(EQ2EQ)
            sep[i] = separation(dec[i], ra[i], plc.r('dec'), plc.r('ra'))
        ok &= report('EQ2HOR->HOR2EQ round trip', sep, a.tol_round, worst=lambda i: 'sep %.4f arcsec at ra %.3f dec %.3f' % (sep[i], ra[i], dec[i]))
    finally:
        plc.close()
    print('PASSED' if ok else 'FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
