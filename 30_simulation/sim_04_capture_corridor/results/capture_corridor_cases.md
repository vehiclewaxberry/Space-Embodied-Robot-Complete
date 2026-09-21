# Capture Corridor v0 — findings

- Grid: 1620 cases (2 targets x 5 tumble x 3 approach x 3 arm-speed x 3 pose-err x 3 inertia x 2 modes).
- SAFE: 312/1620 (19.3%). All SAFE cases are reaction-aware (312 of them); **0 naive cases are safe** (base reaction 13.1 deg >> 5 deg limit).
- Most common failure reasons:
    - POSE_UNCERTAINTY_FAIL: 540
    - BASE_REACTION_FAIL: 540
    - APPROACH_SPEED_FAIL: 144
    - INERTIA_UNCERTAINTY_FAIL: 84
- Reaction-aware SAFE envelope: tumble_rate in [0.5, 1.0, 2.0, 3.0] deg/s, approach in [0.005, 0.01, 0.02] m/s.
- target_debris (heavy, ~59 kg-m^2) hits INERTIA_UNCERTAINTY_FAIL (post-capture combined rate) at far lower tumble than target_satellite — the heavy target dominates the post-capture momentum budget.

## v0 conclusion
Safe capture is a MULTI-constraint problem: geometric reach + grasp visibility window + controllable base reaction + post-capture stability budget. Naive (non-reaction-aware) arm motion is infeasible everywhere on the 12U v0; reaction-aware planning opens a corridor bounded by tumble rate, approach speed, and (for heavy debris) the post-capture inertia budget.
