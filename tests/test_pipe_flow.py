"""Unit tests for the pipe flow calculator. Run with:  pytest"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipe_flow_calculator import (  # noqa: E402
    ROUGHNESS, colebrook, friction_factor, pipe_flow, swamee_jain, water_properties,
)


def test_water_properties_20C():
    rho, mu = water_properties(20)
    assert abs(rho - 998.2) < 0.5          # kg/m^3
    assert abs(mu - 1.002e-3) < 0.02e-3    # Pa*s


def test_laminar_friction_factor_is_64_over_Re():
    f, regime = friction_factor(1000, 0.001)
    assert regime == "laminar"
    assert math.isclose(f, 0.064, rel_tol=1e-12)


def test_colebrook_satisfies_its_own_equation():
    re, rr = 1e5, 1e-3
    f = colebrook(re, rr)
    rhs = -2.0 * math.log10(rr / 3.7 + 2.51 / (re * math.sqrt(f)))
    assert math.isclose(1 / math.sqrt(f), rhs, rel_tol=1e-8)


def test_swamee_jain_within_3_percent_of_colebrook():
    for re in [5e3, 1e4, 1e5, 1e6, 1e7]:
        for rr in [1e-5, 1e-4, 1e-3, 1e-2]:
            fc, fs = colebrook(re, rr), swamee_jain(re, rr)
            assert abs(fs - fc) / fc < 0.03


def test_hand_calculation_case():
    # Water 20 C, 50 mm commercial steel, 100 m, 5 L/s -> about 138 kPa by hand
    rho, mu = water_properties(20)
    r = pipe_flow(0.005, 0.05, 100, rho, mu, ROUGHNESS["commercial steel"])
    assert r["regime"] == "turbulent"
    assert abs(r["velocity_m_s"] - 2.546) < 0.01
    assert abs(r["dp_total_kPa"] - 138.0) / 138.0 < 0.01


def test_elevation_only_adds_rho_g_dz():
    rho, mu = water_properties(20)
    flat = pipe_flow(0.005, 0.05, 100, rho, mu, 0.045e-3)
    uphill = pipe_flow(0.005, 0.05, 100, rho, mu, 0.045e-3, dz=10)
    assert math.isclose(uphill["dp_total_kPa"] - flat["dp_total_kPa"],
                        rho * 9.81 * 10 / 1000, rel_tol=1e-9)


def test_larger_pipe_needs_less_pump_power():
    rho, mu = water_properties(20)
    p75 = pipe_flow(0.01, 0.075, 500, rho, mu, 0.045e-3, 4.5, 10)["pump_power_kW"]
    p100 = pipe_flow(0.01, 0.100, 500, rho, mu, 0.045e-3, 4.5, 10)["pump_power_kW"]
    assert p100 < p75
    assert 0.55 < 1 - p100 / p75 < 0.65   # about a 59% reduction
