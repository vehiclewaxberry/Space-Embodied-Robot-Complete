# M5 physical geometry and loads closure

This isolated package advances M4 into source-bound B601 link geometry, exact nine diagnostic geometry snapshots, a corrected load-authority migration, analytic six-DOF joint load distribution, and a metrology-ready contact identification contract.

It does **not** authorize formal FEA, physical contact force/pressure, strength or margin, flight/launch qualification, manufacturing, RL policy training, HIL, or hardware execution. Unknown physical values remain null/HOLD. The historical 6 GiB gate remains `memory_gate_passed: false`; the recorded Owner Override only authorizes the bounded lightweight route.

The decisive geometry result is that the source files named `*_LINKLOCAL.stl` are actually top-assembly-coordinate exports. M5 inverse-localizes them at q=0 and independently reconstructs the stowed source pose before exporting true link-local indexed PLY surfaces in metres.
