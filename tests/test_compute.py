"""Tests for Jupiter occultation computation."""

import pytest
from compute import load_ephemeris, compute_event_for_location


def test_bengaluru_occultation():
    eph, ts = load_ephemeris()
    # Bengaluru: 12.9716 N, 77.5946 E, 920 m
    res, miss, _, _ = compute_event_for_location(
        eph, ts, 12.9716, 77.5946, 920.0, 5.5
    )

    assert res is not None, "Bengaluru should experience an occultation"

    c1 = res["C1"][0]
    c2 = res["C2"][0]
    mid = res["Mid"][0]
    c3 = res["C3"][0]
    c4 = res["C4"][0]

    # Verify chronological sequence
    assert c1.tt < c2.tt < mid.tt < c3.tt < c4.tt

    # Verify ingress time is around 2026-11-02 20:58 to 21:02 UTC
    dt_c1 = c1.utc_datetime()
    assert dt_c1.year == 2026 and dt_c1.month == 11 and dt_c1.day == 2
    assert dt_c1.hour == 20 and dt_c1.minute == 58

    # Verify egress time is around 21:31 to 21:35 UTC
    dt_c4 = c4.utc_datetime()
    assert dt_c4.year == 2026 and dt_c4.month == 11 and dt_c4.day == 2
    assert dt_c4.hour == 21 and dt_c4.minute == 34

    # Verify duration is around 35 minutes
    assert 34.0 < res["duration_min"] < 37.0

    # Verify target is above the horizon (> 15 deg)
    assert res["C1"][1] > 18.0
    assert res["C4"][1] > 26.0
