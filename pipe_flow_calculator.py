"""
Pipe Flow & Pump Sizing Calculator
Author: Lucas Cerriku

Calculates pressure drop, head loss and required pump power for
single-phase flow in a straight pipe, using the Darcy-Weisbach equation.

  - Fluid properties: CoolProp (water) when installed, otherwise standard
    correlations; user-defined properties for crude oil / other fluids.
  - Friction factor: laminar (64/Re) or turbulent Colebrook-White
    (solved iteratively), checked against the explicit Swamee-Jain equation.
  - Includes minor (fitting) losses and elevation change.

Run:  python pipe_flow_calculator.py
Outputs (in ./results): scenario_results.csv, pressure_drop_vs_flow.png,
                        pump_power_vs_diameter.png
"""

import csv
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = "DejaVu Sans"   # matplotlib default font

G = 9.81  # gravitational acceleration, m/s^2

# ---------------------------------------------------------------------------
# 1. Fluid properties
# ---------------------------------------------------------------------------
try:
    from CoolProp.CoolProp import PropsSI
    HAVE_COOLPROP = True
except ImportError:
    HAVE_COOLPROP = False


def water_properties(temp_c):
    """Return (density kg/m^3, dynamic viscosity Pa*s) of liquid water at 1 atm."""
    if HAVE_COOLPROP:
        T = temp_c + 273.15
        rho = PropsSI("D", "T", T, "P", 101325, "Water")
        mu = PropsSI("V", "T", T, "P", 101325, "Water")
        return rho, mu
    # Fallback: Kell (1975) density fit and Vogel viscosity equation
    t = temp_c
    rho = (999.83952 + 16.945176 * t - 7.9870401e-3 * t**2 - 46.170461e-6 * t**3
           + 105.56302e-9 * t**4 - 280.54253e-12 * t**5) / (1 + 16.879850e-3 * t)
    mu = 2.414e-5 * 10 ** (247.8 / (temp_c + 273.15 - 140))
    return rho, mu


# Typical values for a light crude oil (user-editable; real values come from lab data)
LIGHT_CRUDE = {"name": "Light crude oil", "rho": 850.0, "mu": 0.005}

# Absolute pipe roughness, m
ROUGHNESS = {
    "commercial steel": 0.045e-3,
    "cast iron": 0.26e-3,
    "PVC / drawn tubing": 0.0015e-3,
}


# ---------------------------------------------------------------------------
# 2. Friction factor
# ---------------------------------------------------------------------------
def swamee_jain(re, rel_rough):
    """Explicit approximation of Colebrook (valid 5e3 < Re < 1e8)."""
    return 0.25 / (math.log10(rel_rough / 3.7 + 5.74 / re**0.9)) ** 2


def colebrook(re, rel_rough, tol=1e-10, max_iter=100):
    """Solve Colebrook-White iteratively, starting from Swamee-Jain."""
    f = swamee_jain(re, rel_rough)
    for _ in range(max_iter):
        rhs = -2.0 * math.log10(rel_rough / 3.7 + 2.51 / (re * math.sqrt(f)))
        f_new = 1.0 / rhs**2
        if abs(f_new - f) < tol:
            return f_new
        f = f_new
    return f


def friction_factor(re, rel_rough):
    if re < 2300:
        return 64.0 / re, "laminar"
    if re < 4000:
        # transitional: flagged, Colebrook used as conservative estimate
        return colebrook(re, rel_rough), "transitional"
    return colebrook(re, rel_rough), "turbulent"


# ---------------------------------------------------------------------------
# 3. Core calculation
# ---------------------------------------------------------------------------
def pipe_flow(q, d, length, rho, mu, roughness, k_minor=0.0, dz=0.0, pump_eff=0.75):
    """
    q: flow rate m^3/s, d: inner diameter m, length: m, rho: kg/m^3, mu: Pa*s,
    roughness: m, k_minor: sum of fitting loss coefficients, dz: elevation gain m,
    pump_eff: pump efficiency (0-1).
    """
    area = math.pi * d**2 / 4
    v = q / area
    re = rho * v * d / mu
    f, regime = friction_factor(re, roughness / d)
    dyn = rho * v**2 / 2                       # dynamic pressure, Pa
    dp_major = f * (length / d) * dyn          # Darcy-Weisbach
    dp_minor = k_minor * dyn
    dp_elev = rho * G * dz
    dp_total = dp_major + dp_minor + dp_elev
    head = dp_total / (rho * G)
    pump_kw = q * dp_total / pump_eff / 1000
    return {
        "velocity_m_s": v, "reynolds": re, "regime": regime, "friction_factor": f,
        "dp_major_kPa": dp_major / 1000, "dp_minor_kPa": dp_minor / 1000,
        "dp_elev_kPa": dp_elev / 1000, "dp_total_kPa": dp_total / 1000,
        "head_m": head, "pump_power_kW": pump_kw,
    }


# ---------------------------------------------------------------------------
# 4. Validation
# ---------------------------------------------------------------------------
def validate():
    print("=== Validation ===")
    # (a) Laminar check: f must equal 64/Re exactly
    f, _ = friction_factor(1000, 0.001)
    print(f"Laminar Re=1000: f = {f:.4f} (expected 0.0640)")

    # (b) Colebrook vs Swamee-Jain across the turbulent range
    max_err = 0.0
    for re in [5e3, 1e4, 5e4, 1e5, 5e5, 1e6, 1e7]:
        for rr in [1e-5, 1e-4, 1e-3, 1e-2]:
            fc = colebrook(re, rr)
            fs = swamee_jain(re, rr)
            max_err = max(max_err, abs(fs - fc) / fc * 100)
    print(f"Max Swamee-Jain vs Colebrook difference: {max_err:.2f}% (literature: within ~1-3%)")

    # (c) Textbook-style hand calculation: water 20 C, 50 mm steel, 100 m, 5 L/s
    rho, mu = water_properties(20)
    r = pipe_flow(0.005, 0.05, 100, rho, mu, ROUGHNESS["commercial steel"])
    print(f"Hand-check case: V={r['velocity_m_s']:.3f} m/s, Re={r['reynolds']:.0f}, "
          f"f={r['friction_factor']:.4f}, dP={r['dp_total_kPa']:.1f} kPa")
    return max_err, r


# ---------------------------------------------------------------------------
# 5. Scenario study
# ---------------------------------------------------------------------------
def run_scenarios(outdir):
    rho_w, mu_w = water_properties(20)
    fluids = [
        {"name": "Water (20 C)", "rho": rho_w, "mu": mu_w},
        LIGHT_CRUDE,
    ]
    diameters_mm = [50, 75, 100, 150]
    flows_L_s = [2, 5, 10, 15, 20]
    length = 500.0        # m
    k_minor = 4.5         # e.g. 6 elbows (0.75 each) + 2 open gate valves (0.15 each)
    dz = 10.0             # m elevation gain
    rough = ROUGHNESS["commercial steel"]

    rows = []
    for fl in fluids:
        for d_mm in diameters_mm:
            for q_L in flows_L_s:
                r = pipe_flow(q_L / 1000, d_mm / 1000, length, fl["rho"], fl["mu"],
                              rough, k_minor, dz)
                rows.append({"fluid": fl["name"], "diameter_mm": d_mm, "flow_L_s": q_L, **r})

    with open(os.path.join(outdir, "scenario_results.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for row in rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()})

    make_charts(rows, outdir)
    return rows


# ---------------------------------------------------------------------------
# 6. Charts
# ---------------------------------------------------------------------------
def make_charts(rows, outdir):
    def series(fluid_prefix, key, **match):
        pts = [r for r in rows if r["fluid"].startswith(fluid_prefix)
               and all(r[k] == v for k, v in match.items())]
        return pts

    # Chart 1: pressure drop vs flow rate (75 mm and 100 mm pipes)
    plt.figure(figsize=(8, 5))
    for d, color in ((75, "tab:blue"), (100, "tab:orange")):
        for fluid, ls, label in (("Water", "-", "Water"), ("Light", "--", "Light crude")):
            pts = series(fluid, "dp_total_kPa", diameter_mm=d)
            plt.plot([p["flow_L_s"] for p in pts], [p["dp_total_kPa"] for p in pts],
                     ls, marker="o", color=color, label=f"{label}, D = {d} mm")
    plt.xlabel("Flow rate (L/s)")
    plt.ylabel("Total pressure drop (kPa)")
    plt.title("Pressure Drop vs Flow Rate\n(L = 500 m, steel pipe, +10 m elevation, K = 4.5)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "pressure_drop_vs_flow.png"), dpi=150)
    plt.close()

    # Chart 2: pump power vs pipe diameter at 10 L/s
    plt.figure(figsize=(8, 5))
    for fluid, ls, label in (("Water", "-", "Water (20 C)"), ("Light", "--", "Light crude oil")):
        pts = series(fluid, "pump_power_kW", flow_L_s=10)
        plt.plot([p["diameter_mm"] for p in pts], [p["pump_power_kW"] for p in pts],
                 ls, marker="s", label=label)
    plt.xlabel("Pipe inner diameter (mm)")
    plt.ylabel("Required pump power (kW)")
    plt.title("Pump Power vs Pipe Diameter (Q = 10 L/s, pump efficiency = 75%)")
    plt.xticks([50, 75, 100, 150])
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "pump_power_vs_diameter.png"), dpi=150)
    plt.close()


def interactive():
    print("\n=== Custom calculation (press Enter to accept defaults) ===")
    def ask(prompt, default):
        s = input(f"{prompt} [{default}]: ").strip()
        return float(s) if s else default
    fluid = input("Fluid: 1 = water, 2 = light crude, 3 = custom [1]: ").strip() or "1"
    if fluid == "1":
        rho, mu = water_properties(ask("Water temperature (C)", 20.0))
    elif fluid == "2":
        rho, mu = LIGHT_CRUDE["rho"], LIGHT_CRUDE["mu"]
    else:
        rho, mu = ask("Density (kg/m^3)", 850.0), ask("Viscosity (Pa*s)", 0.005)
    r = pipe_flow(ask("Flow rate (L/s)", 10.0) / 1000, ask("Inner diameter (mm)", 100.0) / 1000,
                  ask("Length (m)", 500.0), rho, mu, ask("Roughness (mm)", 0.045) / 1000,
                  ask("Sum of minor loss K", 4.5), ask("Elevation gain (m)", 10.0),
                  ask("Pump efficiency (0-1)", 0.75))
    for k, v in r.items():
        print(f"  {k:16s}: {v:.4g}" if isinstance(v, float) else f"  {k:16s}: {v}")


if __name__ == "__main__":
    import sys
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(outdir, exist_ok=True)
    print(f"Fluid properties from: {'CoolProp' if HAVE_COOLPROP else 'built-in correlations'}")
    validate()
    rows = run_scenarios(outdir)
    print(f"\nRan {len(rows)} scenarios -> results/scenario_results.csv and 2 charts")
    if "--interactive" in sys.argv:
        interactive()
