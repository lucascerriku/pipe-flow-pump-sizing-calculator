# Hand calculation (validation case)

**Case:** water at 20 °C flowing at 5 L/s through 100 m of 50 mm commercial steel pipe, with no fittings and no elevation change.

## Inputs

| Quantity | Value |
|---|---|
| Flow rate, Q | 0.005 m³/s |
| Inner diameter, D | 0.050 m |
| Length, L | 100 m |
| Roughness, ε | 0.045 mm = 4.5 × 10⁻⁵ m |
| Density, ρ | 998.2 kg/m³ |
| Viscosity, μ | 1.002 × 10⁻³ Pa·s |

## Step 1: Velocity

A = π(0.05)²/4 = 1.963 × 10⁻³ m²

V = Q / A = 0.005 / 1.963 × 10⁻³ = **2.546 m/s**

## Step 2: Reynolds number

Re = ρVD/μ = (998.2)(2.546)(0.05) / 1.002 × 10⁻³ ≈ **126,900**

Re is above 4000, so the flow is **turbulent**.

## Step 3: Friction factor

Relative roughness: ε/D = 4.5 × 10⁻⁵ / 0.05 = 9.0 × 10⁻⁴

Swamee-Jain:

f = 0.25 / [log₁₀(ε/3.7D + 5.74/Re⁰·⁹)]² ≈ **0.0214**

This agrees with reading the Moody chart at Re ≈ 1.3 × 10⁵ and ε/D ≈ 0.0009.

## Step 4: Pressure drop (Darcy-Weisbach)

Dynamic pressure: ρV²/2 = 998.2 × 2.546² / 2 = 3,235 Pa

ΔP = f (L/D)(ρV²/2) = 0.0214 × (100/0.05) × 3,235 ≈ **138 kPa**

## Result

| | Hand calculation | Code |
|---|---|---|
| Velocity | 2.546 m/s | 2.546 m/s |
| Reynolds number | ≈ 126,900 | 126,873 |
| Friction factor | ≈ 0.0214 | 0.0214 |
| Pressure drop | ≈ 138 kPa | 138.2 kPa |

The code agrees with the hand calculation to within 1%.
