# T005-A/B/C native articulation verification contract

Current verdict:

`T005 FAIL / G3 HOLD_NO_ACCEPTED_6R_RUN_2P_AND_NATIVE_LIMIT_MATES_MISSING`

## Accepted authority

- URDF SHA-256:
  `1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164`
- topology: `10 links / 6 revolute + 1 fixed + 2 prismatic`
- model-only mass sum: `4.6955559493429862 kg`
- prismatic mimic count: `0`

The two prismatic joints are independent. Both use joint-local `+X` with
opposite joint-frame rotations and numerical limits `[0, 0.0715] m`. Before
zero calibration, these endpoints may be called only `MIN_NUMERIC` and
`MAX_NUMERIC`, not full-open or full-closed.

## What T005 established and did not establish

The parent run created seven rigid segments and six
concentric-plus-coincident mate pairs. It then drove coordinated absolute
segment `Transform2` values; it did not create native joint-angle drivers,
native angular limits, a Mate Controller, gripper child parts, or either
prismatic joint.

After six rejected `0.75 deg` off-axis trials, the first random legal vector

`[0.027636394858497226, -0.66990466086214, -0.6105793310540046, -1.5127109592851438, -1.3629301337689044, -1.6719054180833184]`

failed after rebuild:

- link5 max transform-element error:
  `0.00035157303526744954`;
- link6:
  `0.012812317049107874`;
- gripper_link:
  `0.012812316890332333`.

No random pose passed and the full assembly was not saved. The separate T003
diagnostic passed only after document reopen. That proves history dependence is
a strong candidate; it does not prove a cache root cause and cannot replace a
resettable native mechanism.

## Common entry conditions

T005-A/B/C are blocked until all of the following are true:

1. All ten URDF link roles and nine named joints exist in native CAD.
2. Each of six R joints has one native rotational freedom, one authoritative
   driver, a q0 zero reference, registered URDF axis/sign, and native lower and
   upper limits.
3. The fixed joint is a named zero-DOF relation reproducing its URDF transform.
4. Each P joint has its own native part partition, driver, zero reference,
   axis/sign, and native `[0, 0.0715] m` limits. No mimic or one-width
   substitute is allowed.
5. No joint has redundant drivers or an uncontrolled rotation branch.
6. URDF, scripts, imported helpers, assembly, parts, and frozen pose vectors
   have SHA-256 manifests.
7. Each command is logged before execution; failures preserve command,
   pre/post transforms, joint readback, mate solution, suppression state, and
   rebuild result.
8. World-frame comparisons report separately:
   - `e_p = ||p_CAD-p_URDF||_2`;
   - `e_R = acos((trace(R_ref^T R_CAD)-1)/2)`;
   - `e_q = wrap(q_read-q_cmd)`;
   - the existing compatibility metric `e_max`.

The existing `e_max <= 2.0e-7` may remain as a diagnostic compatibility
threshold. Numeric acceptance thresholds for `e_p`, `e_R`, and `e_q` are
`TBD_HUMAN_AUTHORITY`; before they are approved, a run cannot produce G3 PASS.

## T005-A — independent pose reconstruction

Pose set:

- q0;
- the frozen 20 legal random poses generated from seed `6015106`;
- STOW;
- total: `22`.

Every pose starts from the same hash-identical clean copy or standard initial
state and inherits no preceding test state. Cold reopen is permitted in A.
Both P joints are held at the explicitly recorded numerical value `0`; this is
not a closed-state claim.

For each pose, verify all ten link frames, the end frame, six R readbacks, two
P readbacks, all mate states, and reference containment.

Exit: `22/22`, zero warning/error, zero mate flip, zero suppression drift. A
proves independent reconstruction only; it does not prove sequential reset.

## T005-B — uninterrupted sequential native driving

Use one open document without close, reopen, reload, configuration recovery, or
absolute segment-transform writes:

`q0 -> q01 ... q20 -> STOW -> q0`

Total arm states: `23`.

Only native joint drivers may be changed. Every state records driver command,
joint readback, all link transforms, mate alignment/solution, suppression,
rebuild result, and all four error metrics. Final q0 must meet the same
thresholds as initial q0.

Independently execute the two-P sequence in the same document:

`[0,0] -> [0.03575,0] -> [0,0.03575] -> [0.03575,0.03575] -> [0.0715,0.0715] -> [0,0] m`

Exit: all 23 arm states and all P states pass with no link jump, sign reversal,
mate-solution flip, hidden suppression change, or document reopen. Any required
reopen is a T005-B failure.

## T005-C — configuration persistence and cold reopen

Save and verify at minimum:

- q0;
- STOW;
- one frozen intermediate random pose;
- symmetric P min/mid/max;
- asymmetric P states `[0.0715,0]` and `[0,0.0715] m`.

Verify configuration names, driver values, native limits, mate
solution/suppression, all ten link frames, all joint readbacks, reference
containment, and file hashes before close, after same-process reopen, and after
an independent cold-process reopen.

Exit: every frozen state passes in a new process. Reopen is a persistence test
in C; it is never an allowed repair for B.

## Minimum discriminating experiments

Run each baseline and single-variable intervention three times from the same
PRETEST hash:

1. no-history control: q0 directly to the first random pose;
2. single-J1 through single-J6 `0.75 deg` off-axis isolation;
3. direction-only versus off-axis-only factorial split;
4. legacy absolute-Transform2 path versus unique native-driver path;
5. root-to-tip, tip-to-root, rebuild-per-joint, and native-driver solve order;
6. relative joint readback from `T_parent^-1 T_child` after removing URDF
   origins.

A root cause may be upgraded to confirmed only when the baseline reproduces
`3/3` and one controlled intervention removes it `3/3`.

## Prohibited upgrades

Until all entry and A/B/C exit conditions pass, none of these claims is
permitted:

`T005_PASS`, `6R_NATIVE_DRIVE_PASS`, `6R_RESETTABLE_SEQUENCE_PASS`,
`6R+1F+2P_COMPLETE`, `NATIVE_LIMIT_MATES_PASS`,
`GRIPPER_FULL_OPEN_OR_CLOSED_CALIBRATED`,
`CONFIGURATION_PERSISTENCE_PASS`, `COLD_REOPEN_ACCEPTANCE_PASS`, or `G3_PASS`.

