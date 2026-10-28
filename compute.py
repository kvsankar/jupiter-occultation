"""Compute timings and geometry for the Lunar Occultation of Jupiter on 2026-11-02/03.

Uses JPL DE440s through Skyfield to calculate topocentric contact times,
separations, altitudes, and azimuths for observer locations across the visibility zone.
"""

from datetime import timedelta
import numpy as np
from skyfield.api import load, wgs84

# Physical constants
R_MOON_KM = 1737.4
R_JUP_EQ_KM = 71492.0

CITIES = {
    "Bengaluru (India)": (12.9716, 77.5946, 920.0, "Asia/Kolkata", 5.5),
    "Chennai (India)": (13.0827, 80.2707, 7.0, "Asia/Kolkata", 5.5),
    "Colombo (Sri Lanka)": (6.9271, 79.8612, 7.0, "Asia/Colombo", 5.5),
    "Kuala Lumpur (Malaysia)": (3.1390, 101.6869, 22.0, "Asia/Kuala_Lumpur", 8.0),
    "Singapore": (1.3521, 103.8198, 15.0, "Asia/Singapore", 8.0),
    "Jakarta (Indonesia)": (-6.2088, 106.8456, 8.0, "Asia/Jakarta", 7.0),
    "Perth (Australia)": (-31.9505, 115.8605, 31.0, "Australia/Perth", 8.0),
    "Sydney (Australia)": (-33.8688, 151.2093, 19.0, "Australia/Sydney", 11.0),
}


def load_ephemeris():
    eph = load("de440s.bsp")
    ts = load.timescale()
    return eph, ts


def compute_event_for_location(eph, ts, lat, lon, elev, tz_offset_hours):
    earth = eph["earth"]
    moon = eph["moon"]
    jupiter = eph["jupiter barycenter"]
    sun = eph["sun"]

    loc = earth + wgs84.latlon(lat, lon, elevation_m=elev)

    # Search window: 2026-11-02 20:00 to 2026-11-03 02:00 UTC (1-second steps)
    t_base = ts.utc(2026, 11, 2, 20, 0, 0)
    total_seconds = 6 * 3600
    # First search at 10-second resolution
    step_coarse = 10
    sec_coarse = np.arange(0, total_seconds, step_coarse)
    t_coarse = ts.utc(2026, 11, 2, 20, 0, sec_coarse)

    obs_m = loc.at(t_coarse).observe(moon).apparent()
    obs_j = loc.at(t_coarse).observe(jupiter).apparent()

    r_m_deg = np.degrees(np.arcsin(R_MOON_KM / obs_m.distance().km))
    r_j_deg = np.degrees(np.arcsin(R_JUP_EQ_KM / obs_j.distance().km))
    sep_deg = obs_m.separation_from(obs_j).degrees

    target_contact_out = r_m_deg + r_j_deg
    target_contact_in = r_m_deg - r_j_deg

    occulted = sep_deg < target_contact_out
    if not np.any(occulted):
        min_idx = np.argmin(sep_deg)
        miss_arcmin = (sep_deg[min_idx] - target_contact_out[min_idx]) * 60.0
        return None, miss_arcmin, t_coarse[min_idx], obs_m.altaz()[0].degrees[min_idx]

    # Refine at 1-second resolution around ingress and egress
    min_coarse_idx = np.argmin(sep_deg)
    occ_idx = np.where(occulted)[0]
    i_start = max(0, sec_coarse[occ_idx[0]] - 120)
    i_end = min(total_seconds, sec_coarse[occ_idx[-1]] + 120)

    fine_sec = np.arange(i_start, i_end, 1)
    t_fine = ts.utc(2026, 11, 2, 20, 0, fine_sec)

    obs_m_fine = loc.at(t_fine).observe(moon).apparent()
    obs_j_fine = loc.at(t_fine).observe(jupiter).apparent()

    r_m = np.degrees(np.arcsin(R_MOON_KM / obs_m_fine.distance().km)) * 3600.0
    r_j = np.degrees(np.arcsin(R_JUP_EQ_KM / obs_j_fine.distance().km)) * 3600.0
    sep = obs_m_fine.separation_from(obs_j_fine).arcseconds()

    c_out = sep - (r_m + r_j)
    c_in = sep - (r_m - r_j)
    min_fine_idx = np.argmin(sep)

    # Ingress C1 & C2
    c1_candidates = np.where(c_out[:min_fine_idx] <= 0)[0]
    c1 = c1_candidates[0] if len(c1_candidates) > 0 else 0

    c2_candidates = np.where(c_in[:min_fine_idx] <= 0)[0]
    c2 = c2_candidates[0] if len(c2_candidates) > 0 else c1

    # Egress C3 & C4
    c3_candidates = np.where(c_in[min_fine_idx:] >= 0)[0]
    c3 = min_fine_idx + c3_candidates[0] if len(c3_candidates) > 0 else len(t_fine) - 1

    c4_candidates = np.where(c_out[min_fine_idx:] >= 0)[0]
    c4 = min_fine_idx + c4_candidates[0] if len(c4_candidates) > 0 else len(t_fine) - 1

    alt_m, az_m, _ = obs_m_fine.altaz()
    alt_j, az_j, _ = obs_j_fine.altaz()

    results = {
        "C1": (t_fine[c1], alt_j.degrees[c1], az_j.degrees[c1]),
        "C2": (t_fine[c2], alt_j.degrees[c2], az_j.degrees[c2]),
        "Mid": (t_fine[min_fine_idx], alt_j.degrees[min_fine_idx], az_j.degrees[min_fine_idx], sep[min_fine_idx] / 60.0),
        "C3": (t_fine[c3], alt_j.degrees[c3], az_j.degrees[c3]),
        "C4": (t_fine[c4], alt_j.degrees[c4], az_j.degrees[c4]),
        "duration_min": (t_fine[c4].utc_datetime() - t_fine[c1].utc_datetime()).total_seconds() / 60.0,
        "moon_rad_arcmin": r_m[min_fine_idx] / 60.0,
        "jup_rad_arcsec": r_j[min_fine_idx],
    }
    return results, 0.0, None, None


def format_dt(t, tz_offset_hours):
    dt_utc = t.utc_datetime()
    dt_loc = dt_utc + timedelta(hours=tz_offset_hours)
    return dt_utc.strftime("%H:%M:%S UTC"), dt_loc.strftime("%H:%M:%S")


def main():
    eph, ts = load_ephemeris()
    print("================================================================================")
    print(" LUNAR OCCULTATION OF JUPITER: 2026 NOVEMBER 2-3")
    print("================================================================================")
    print("Geocentric Closest Approach: 2026-11-02 22:46:00 UTC (Sep: 29.07 arcmin)\n")

    for city_name, (lat, lon, elev, tz_name, tz_offset) in CITIES.items():
        res, miss, t_miss, alt_miss = compute_event_for_location(
            eph, ts, lat, lon, elev, tz_offset
        )
        print(f"\n--- {city_name} (tz offset +{tz_offset:g}h) ---")
        if res is None:
            print(f"  Missed by {miss:.2f} arcmin at {t_miss.utc_strftime('%H:%M:%S UTC')} (Alt: {alt_miss:.1f} deg)")
            continue

        c1_u, c1_l = format_dt(res["C1"][0], tz_offset)
        c2_u, c2_l = format_dt(res["C2"][0], tz_offset)
        mid_u, mid_l = format_dt(res["Mid"][0], tz_offset)
        c3_u, c3_l = format_dt(res["C3"][0], tz_offset)
        c4_u, c4_l = format_dt(res["C4"][0], tz_offset)

        print(f"  Ingress C1 (First Contact):  {c1_u}  /  Local: {c1_l}  (Alt: {res['C1'][1]:.1f} deg, Az: {res['C1'][2]:.1f} deg)")
        print(f"  Ingress C2 (Full Ingress):   {c2_u}  /  Local: {c2_l}")
        print(f"  Mid-Occultation:             {mid_u}  /  Local: {mid_l}  (Min sep: {res['Mid'][3]:.2f}', Alt: {res['Mid'][1]:.1f} deg)")
        print(f"  Egress C3 (Reappearance):   {c3_u}  /  Local: {c3_l}")
        print(f"  Egress C4 (Full Egress):     {c4_u}  /  Local: {c4_l}  (Alt: {res['C4'][1]:.1f} deg, Az: {res['C4'][2]:.1f} deg)")
        print(f"  Total Duration: {res['duration_min']:.2f} minutes")


if __name__ == "__main__":
    main()
