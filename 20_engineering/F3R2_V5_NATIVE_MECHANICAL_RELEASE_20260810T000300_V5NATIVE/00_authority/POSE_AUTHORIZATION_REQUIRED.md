# Pose authorization required — V5

No service pose is promoted by CAD automation. L0 joint topology, axes, limits and accepted dynamics remain unchanged.

| Pose | q (deg) | Class | Permitted V5 use |
|---|---|---|---|
| Q_DEPLOYED_HOME | [-90,-120,-60,0,-30,0] | `AUTHORIZED_RUNTIME_INPUT` | Control/dynamics initialization; must be revalidated against V5 geometry |
| Q_RELEASE_CLEAR | [-90,-120,-120,-60,-30,0] | `AUTHORIZED_GEOMETRIC_END_STATE` | End state only; release sequence still requires authority and native validation |
| Q_SERVICE_READY | [-90,-60,-120,-30,0,0] | `AUTHORIZED_RUNTIME_INPUT_WITH_SERVICE_RATIFICATION_HOLD` | Pre-service staging only |
| Q_STOW_ENGINEERING | [145.572,-168,-57,-41.143,-20.954,-3] | `CANDIDATE` | Engineering fit-up seed; not a runtime/control authority |
| Q_SERVICE_DOCKING | — | `NOT_AUTHORIZED` | Candidate search only |
| Q_SERVICE_GRASP | — | `NOT_AUTHORIZED` | Candidate search only |
| Q_SERVICE_TRANSPORT | — | `NOT_AUTHORIZED` | Candidate search only |
| Q_SERVICE_ASSEMBLY | — | `NOT_AUTHORIZED` | Candidate search only |
| Q_RETRIEVED | — | `NOT_AUTHORIZED` | Candidate search only |

For each missing service state, Loop 2 may emit an `IK_CANDIDATE_SET` ranked by joint margin, arm–bus/wing clearance, base reaction, camera visibility and EE pose error. Human approval is required before any candidate becomes authoritative.
