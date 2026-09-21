"""Refraction model vs an independent ray trace and erfa.refco (AstroBROT#11). Run: python3 check_refraction_model.py

Reference: numerical ray trace through a standard atmosphere (6.5 K/km up to 11 km, isothermal above, hydrostatic
pressure, spherical shells, Snell's law n*r*sin(z) = const, R = integral of tan(z)/n dn). It is NOT an authority:
the refractivity coefficient below is calibrated so that 45 deg gives the textbook 58" at 10 degC / 1010 hPa, so it is
good to about 0.5 %, and it ignores humidity and wavelength. Use it to compare candidate formulas, not as ground truth.
"""
import math
import numpy as np
import erfa
import astrobrot_port as port

AS = 206264.80624709636
COEF = 78.8e-6          # (n-1) = COEF * P[hPa] / T[K], visible light, dry air
R_EARTH = 6371.0        # km


def reference(alt_obs_deg, P=1010.0, T=10.0):
    """Refraction in arcsec for an OBSERVED altitude, P in hPa, T in degC."""
    T0 = T + 273.15; L = 6.5; g = 9.80665; Rd = 287.05; ex = g / (Rd * L / 1000.0)

    def pt(h):
        if h <= 11.0:
            th = T0 - L * h
            return P * (th / T0) ** ex, th
        t11 = T0 - L * 11.0
        return P * (t11 / T0) ** ex * math.exp(-g * (h - 11.0) * 1000.0 / (Rd * t11)), t11

    def n_of(h):
        p, t = pt(h)
        return 1.0 + COEF * p / t

    z0 = math.radians(90.0 - alt_obs_deg)
    n0 = n_of(0.0)
    hs = np.concatenate([np.linspace(0, 11, 6000), np.linspace(11, 150, 6000)[1:]])
    ns = np.array([n_of(h) for h in hs])
    sinz = n0 * R_EARTH * math.sin(z0) / (ns * (R_EARTH + hs))
    f = (sinz / np.sqrt(1.0 - sinz ** 2)) / ns
    return -np.sum(0.5 * (f[1:] + f[:-1]) * np.diff(ns)) * AS


def current(a, P, T):
    return port.refract_forward(a, P, T) * 3600.0


def low_branch(a, P, T):     # a < 15 deg branch of CO_REFRACT_FORWARD
    return P / (T + 273.0) * (0.1594 + 0.0196 * a + 0.00002 * a * a) / (1.0 + 0.505 * a + 0.0845 * a * a) * 3600.0


def high_00452(a, P, T):     # candidate: 0.00452 * P / ((273 + T) * tan a); from memory of ExSup 2013 eq. 7.90, unchecked
    return 0.00452 * P / ((273.0 + T) * math.tan(math.radians(a))) * 3600.0


def erfa_refco(a, P, T):
    A, B = erfa.refco(P, T, 0.0, 0.55)
    z = math.radians(90.0 - a)
    return (A * math.tan(z) + B * math.tan(z) ** 3) * AS


if __name__ == '__main__':
    for P, T in [(1010.0, 10.0), (900.0, -15.0), (1013.0, 30.0)]:
        print(f'\nP = {P:.0f} hPa, T = {T:.0f} degC        (errors are candidate - reference, arcsec)')
        print(' alt   reference   code (err)      0.00452 form (err)   erfa.refco (err)')
        for a in [5, 10, 14.9, 15.0, 15.1, 20, 30, 45, 60, 80]:
            r = reference(a, P, T)
            c = current(a, P, T)
            cand = high_00452(a, P, T) if a >= 15.0 else low_branch(a, P, T)
            e = erfa_refco(a, P, T)
            print(f'{a:5.1f} {r:10.2f} {c:9.2f} ({c - r:+6.2f}) {cand:12.2f} ({cand - r:+6.2f}) {e:12.2f} ({e - r:+6.2f})')
        print('step at 15 deg: code %.2f", 0.00452 form %.2f"' % (
            current(15.0, P, T) - current(14.9999999, P, T),
            high_00452(15.0, P, T) - low_branch(14.9999999, P, T)))
