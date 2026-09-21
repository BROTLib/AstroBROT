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
    hs = np.concatenate([np.linspace(0, 11, 3000), np.linspace(11, 150, 3000)[1:]])
    th = np.where(hs <= 11.0, T0 - L * hs, T0 - L * 11.0)
    t11 = T0 - L * 11.0
    ph = np.where(hs <= 11.0, P * (th / T0) ** ex,
                  P * (t11 / T0) ** ex * np.exp(-g * (hs - 11.0) * 1000.0 / (Rd * t11)))
    ns = 1.0 + COEF * ph / th
    z0 = math.radians(90.0 - alt_obs_deg)
    sinz = ns[0] * R_EARTH * math.sin(z0) / (ns * (R_EARTH + hs))
    f = (sinz / np.sqrt(1.0 - sinz ** 2)) / ns
    return -np.sum(0.5 * (f[1:] + f[:-1]) * np.diff(ns)) * AS


def old_code(a, P, T):
    """CO_REFRACT_FORWARD before #11: Bennett-style branch from 15 deg, the rational branch below. Arcsec."""
    a = min(max(a, 0.0), 90.0); P = min(max(P, 600.0), 1200.0); T = min(max(T, -40.0), 40.0)
    if a >= 15.0:
        return (0.28 * P) / (T + 273.0) * 0.0167 / math.tan(math.radians(a + 7.31 / (a + 4.4))) * 3600.0
    return low_branch(a, P, T)


def current(a, P, T):
    """CO_REFRACT_FORWARD as implemented (the Python port). Arcsec."""
    return port.refract_forward(a, P, T) * 3600.0


def low_branch(a, P, T):     # a < 15 deg branch of CO_REFRACT_FORWARD
    return P / (T + 273.0) * (0.1594 + 0.0196 * a + 0.00002 * a * a) / (1.0 + 0.505 * a + 0.0845 * a * a) * 3600.0


def high_00452(a, P, T):     # candidate: 0.00452 * P / ((273 + T) * tan a); from memory of ExSup 2013 eq. 7.90, unchecked
    return 0.00452 * P / ((273.0 + T) * math.tan(math.radians(a))) * 3600.0


WL_TERM = 77.53484e-6 + (4.39108e-7 + 3.666e-9 / 0.55 ** 2) / 0.55 ** 2   # dry air, 0.55 um (eraRefco optical case)


def refco_dry(a, P, T):
    """A tan z + B tan^3 z with A, B as eraRefco (rh = 0, wl = 0.55 um), reduced to the dry formula. Arcsec."""
    tk = T + 273.15
    gamma = WL_TERM * P / tk
    beta = 4.4474e-6 * tk
    z = math.radians(90.0 - a)
    return (gamma * (1.0 - beta) * math.tan(z) - gamma * (beta - gamma / 2.0) * math.tan(z) ** 3) * AS


def erfa_refco(a, P, T):
    A, B = erfa.refco(P, T, 0.0, 0.55)
    z = math.radians(90.0 - a)
    return (A * math.tan(z) + B * math.tan(z) ** 3) * AS


def candidate_c(a, P, T):
    """Option c of the plan: refco_dry from 15 deg up, the existing low branch below."""
    return refco_dry(a, P, T) if a >= 15.0 else low_branch(a, P, T)


def candidate_blend(a, P, T, lo=14.0, hi=16.0):
    """What CO_REFRACT_FORWARD implements: low branch below lo, refco_dry from hi, linear blend between."""
    if a <= lo:
        return low_branch(a, P, T)
    if a >= hi:
        return refco_dry(a, P, T)
    w = (a - lo) / (hi - lo)
    return (1.0 - w) * low_branch(a, P, T) + w * refco_dry(a, P, T)


def acceptance(f, name):
    """Plan D1: |error| <= 1" from 15 deg up, <= 3" from 10 to 15 deg, jump at 15 deg <= 0.5", decreasing with altitude."""
    worst_hi = worst_lo = 0.0
    worst_jump = 0.0
    mono = True
    for P in (900.0, 950.0, 1000.0, 1013.0):
        for T in (-15.0, 0.0, 10.0, 20.0, 30.0):
            for a in np.arange(15.0, 90.01, 0.5):
                worst_hi = max(worst_hi, abs(f(a, P, T) - reference(a, P, T)))
            for a in np.arange(10.0, 14.99, 0.5):
                worst_lo = max(worst_lo, abs(f(a, P, T) - reference(a, P, T)))
            worst_jump = max(worst_jump, abs(f(15.0, P, T) - f(15.0 - 1e-9, P, T)))
            grid = [f(a, P, T) for a in np.arange(10.0, 90.01, 0.25)]
            mono = mono and all(x > y for x, y in zip(grid, grid[1:]))
    ok = worst_hi <= 1.0 and worst_lo <= 3.0 and worst_jump <= 0.5 and mono
    print(f'{name:28s} worst error 15-90 deg {worst_hi:5.2f}", 10-15 deg {worst_lo:5.2f}", jump at 15 deg {worst_jump:5.2f}", '
          f'monotonic {mono}  -> {"PASS" if ok else "FAIL"}')


if __name__ == '__main__':
    a1, a2 = erfa.refco(1010.0, 10.0, 0.0, 0.55)
    assert abs(refco_dry(30.0, 1010.0, 10.0) - erfa_refco(30.0, 1010.0, 10.0)) < 1e-9, 'refco_dry differs from erfa.refco'
    print('candidates against the acceptance limits (P 900-1013 hPa, T -15..30 degC):')
    acceptance(old_code, 'a. old code (before #11)')
    acceptance(lambda a, P, T: high_00452(a, P, T) if a >= 15.0 else low_branch(a, P, T), 'b. 0.00452 form, join 15 deg')
    acceptance(candidate_c, 'c. refco (dry) from 15 deg')
    acceptance(candidate_blend, 'c. refco, blend 14-16 deg (implemented)')
    for P, T in [(1010.0, 10.0), (900.0, -15.0), (1013.0, 30.0)]:
        print(f'\nP = {P:.0f} hPa, T = {T:.0f} degC        (errors are candidate - reference, arcsec)')
        print(' alt   reference   old code (err)  0.00452 form (err)   erfa.refco (err)   implemented (err)')
        for a in [5, 10, 14.9, 15.0, 15.1, 20, 30, 45, 60, 80]:
            r = reference(a, P, T)
            c = old_code(a, P, T)
            n = current(a, P, T)
            cand = high_00452(a, P, T) if a >= 15.0 else low_branch(a, P, T)
            e = erfa_refco(a, P, T)
            print(f'{a:5.1f} {r:10.2f} {c:9.2f} ({c - r:+6.2f}) {cand:12.2f} ({cand - r:+6.2f}) {e:12.2f} ({e - r:+6.2f}) {n:12.2f} ({n - r:+6.2f})')
        print('step at 15 deg: old code %.2f", 0.00452 form %.2f", implemented %.2f"' % (
            old_code(15.0, P, T) - old_code(14.9999999, P, T),
            high_00452(15.0, P, T) - low_branch(14.9999999, P, T),
            max(abs(current(x + 1e-6, P, T) - current(x, P, T)) for x in np.arange(5.0, 89.0, 0.01))))
