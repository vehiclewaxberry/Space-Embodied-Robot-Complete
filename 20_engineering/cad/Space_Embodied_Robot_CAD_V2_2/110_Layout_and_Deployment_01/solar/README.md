# Solar Gate 1–3 isolated outputs

This directory is an additive, isolated V2.2 design branch. It does not open
or modify the canonical V2.2 top assembly or
`100_Mechanical_Continuation`.

## Generate a pose

From the competition workspace root, set `SOLAR_POSE_DEG` to a numeric
verification angle and run the CAD skill STEP generator against the explicit
source/output pair. Example:

```powershell
$env:SOLAR_OUTPUT_MODE='pose'
$env:SOLAR_POSE_DEG='30'
python C:\Users\stude\.codex\plugins\cache\text-to-cad\cad\0.3.9\skills\cad\scripts\step `
  20_engineering\cad\Space_Embodied_Robot_CAD_V2_2\110_Layout_and_Deployment_01\solar\solar_deployment_test_rig.py=20_engineering\cad\Space_Embodied_Robot_CAD_V2_2\110_Layout_and_Deployment_01\solar\solar_deployment_pose_030deg.step
```

## Generate the sampled diagnostic

```powershell
$env:SOLAR_OUTPUT_MODE='sweep'
python C:\Users\stude\.codex\plugins\cache\text-to-cad\cad\0.3.9\skills\cad\scripts\step `
  20_engineering\cad\Space_Embodied_Robot_CAD_V2_2\110_Layout_and_Deployment_01\solar\solar_deployment_test_rig.py=20_engineering\cad\Space_Embodied_Robot_CAD_V2_2\110_Layout_and_Deployment_01\solar\solar_deployment_sweep_samples.step
```

`0/5/15/30/60/90 deg` are discrete geometry checks only. They do not redefine
the formal `PARTIAL` configuration, whose angle remains `UNKNOWN`.

