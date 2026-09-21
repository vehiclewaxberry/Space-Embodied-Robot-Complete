# B5.0 B601 Engineering Requirements

Status: `AUTHORIZED_CANDIDATE_DESIGN`

These requirements govern the isolated B5.0 candidate. They do not release a
manufacturing or flight design.

| ID | Requirement | Verification |
|---|---|---|
| B50-REQ-001 | The accepted `arm_b601_v1.urdf` shall remain byte-identical and shall own link/joint topology, axes, limits, model masses, centres of mass and inertias. | SHA-256 and field-by-field extraction |
| B50-REQ-002 | The L1 CAD shall expose 10 link identities and 9 joint identities: 6 revolute, 1 fixed and 2 prismatic. | Native assembly/component and frame census |
| B50-REQ-003 | `joint2` shall retain axis `0 0 -1`; no visual alignment may reverse it. | Joint-axis comparator |
| B50-REQ-004 | Vendor B601 STEP geometry shall be traceable as `GEOMETRY_REFERENCE_ONLY` and shall never overwrite L0 mass or kinematics. | Properties, provenance ledger and mass-owner audit |
| B50-REQ-005 | B106 shall remain `NOT_FOUND_IN_PHASE0_BOUNDED_SEARCH`; no local B106 geometry claim is permitted. | Asset inventory |
| B50-REQ-006 | All new native production references shall resolve inside the B5.0 candidate root. | Cold reopen and component-path audit |
| B50-REQ-007 | Candidate link geometry shall use the extracted real B601 semantic groups where available. G05 Link6 and G08 Gripper registration shall remain `CHAIN_DERIVED_HOLD`. | Donor-registration ledger |
| B50-REQ-008 | The two spacecraft mount tracks, 198 mm display and 185.25 mm dynamics, shall remain separately named; the 12.75 mm difference shall not be hidden in a joint origin. | Frame ledger and configuration/property readback |
| B50-REQ-009 | The base adapter shall express a primary load path, central harness passage and service directions. Bolt pattern, material, fastener grade and structural capacity remain `TBD/HOLD`. | CAD views and interface ledger |
| B50-REQ-010 | Stowage shall use base primary support plus auxiliary support/HDRM envelopes. Contact, preload, pad material, launch lock and release qualification remain `HOLD`. | State and interface review |
| B50-REQ-011 | The end effector shall preserve accepted gripper topology. Any modular capture tool, F/T sensor or camera geometry shall be separately identifiable and have physical TCP `UNKNOWN`. | BOM identity and frame ledger |
| B50-REQ-012 | The harness representation shall show ports, restraints, bend/service envelopes and keep bend radius, connector type, thermal control and flight qualification `TBD`. | Route review |
| B50-REQ-013 | Every primary STEP shall pass CAD reference/facts/planes/positioning inspection and reviewed multi-view snapshots. | CAD CLI evidence |
| B50-REQ-014 | Candidate STEP/STL/URDF outputs shall be reproducibly derived and sealed. No CAD-computed mass shall enter the L0 ledger. | Generator hashes and layer mapping |
| B50-REQ-015 | Any baseline drift, outside production reference, manual-drag state, SolidWorks process leak, unresolved save state or mass-owner duplication shall fail closed. | Gate scripts |

## Explicit non-requirements

- No launch-load, vibration, thermal-vacuum, radiation, life, tribology or
  flight-qualification conclusion is authorized.
- No motor, reducer, bearing, fastener, connector, pad, HDRM or material is
  procurement-selected by this CAD activity.
- URDF effort and velocity fields are preserved data, not verified actuator
  performance.
- The accepted digital model mass is not a physical weigh-in.
- B106 geometry is not substituted, reconstructed or claimed.
