# sim_07 ANCF beam benchmark results v1 (Gate B item 1)

```json
{
  "params": {
    "L_m": 0.2,
    "mu_kg_m": 1.74197,
    "EI_Nm2": 0.0089042,
    "EA_N": 2968.1
  },
  "b1_static": {
    "tip_ancf_m": 0.00199979,
    "tip_analytic_m": 0.002,
    "rel_err": "1.03e-04",
    "newton_residual": "4.3e-12",
    "PASS(<1%)": true
  },
  "b2_freq": {
    "f1_hz": 1.00021,
    "f1_analytic": 1.0002,
    "err_f1": "2.14e-06",
    "f2_hz": 6.2687,
    "f2_analytic": 6.2682,
    "err_f2": "8.00e-05",
    "envelope_f1_hz": {
      "flexible_low": 0.7001,
      "nominal": 1.0002,
      "flexible_high": 1.3002
    },
    "PASS(<5%)": true
  },
  "b3_zero_strain": {
    "U_37deg_J": "-1.68e-14",
    "U_90deg_J": "1.07e-14",
    "PASS": true
  },
  "b4_energy_drift": {
    "rtol1e-8": "2.52e-09",
    "rtol1e-10": "1.60e-09",
    "PASS(<1e-6@tight)": true
  },
  "b5_convergence": [
    {
      "n_el": 2,
      "f1": 1.00069,
      "f1_err": "4.83e-04",
      "tip_err": "1.91e-04"
    },
    {
      "n_el": 4,
      "f1": 1.00024,
      "f1_err": "3.27e-05",
      "tip_err": "1.04e-04"
    },
    {
      "n_el": 8,
      "f1": 1.00021,
      "f1_err": "2.14e-06",
      "tip_err": "1.03e-04"
    },
    {
      "n_el": 16,
      "f1": 1.0002,
      "f1_err": "5.12e-07",
      "tip_err": "1.03e-04"
    }
  ]
}
```
