# Stage 1-C Risk Register v0

| risk_id | risk | impact | trigger or evidence | mitigation | priority | status |
|---|---|---|---|---|---|---|
| R-001 | Appendix B drawing dimensions not manually reviewed | CAD envelope may use wrong dimensions | manual review table incomplete | complete Appendix B review before freezing CAD dimensions | P0 | open |
| R-002 | robot protrusion exceeds limit | deployment/reference compliance issue | folded robot or adapter protrudes beyond allowed envelope | move mount inward, revise adapter, or document demo-only constraint | P0 | open |
| R-003 | rail keepout invaded | rail/deployer interface conflict | adapter, camera, panel, or fastener overlaps keepout | add rail keepout overlay and redesign placement | P0 | open |
| R-004 | center of gravity out of range | layout may not support credible platform balance | mass CSV shows bus/robot imbalance | redistribute battery/RW/bus placeholders and update mass budget | P0 | open |
| R-005 | robot mount stiffness insufficient | ground demo vibration or pose error; weak dynamics assumptions | adapter too thin or long without reinforcement | add ribs/thickened plate and mark FEA/test as future work | P1 | open |
| R-006 | solar panel or antenna collision | failed deployment or blocked robot task | workspace envelope intersects deployable envelope | adjust panel hinge, robot pose, or keepout zone | P0 | open |
| R-007 | camera FOV occluded | target approach narrative and demo video weakened | robot link, panel, or antenna blocks FOV | relocate camera or adjust folded/pre-grasp pose | P0 | open |
| R-008 | target contact failure | capture scenario not credible | grasp feature unclear or non-grasp region contacted | define target grasp feature and pre-grasp pose | P1 | open |
| R-009 | ground demo vs on-orbit narrative confusion | competition report may overclaim flight readiness | wording mixes demo choreography with flight operations | label ground demo and on-orbit concept separately | P1 | open |
| R-010 | VLA miswritten as low-level controller | architecture claim becomes technically wrong | VLA output described as joint torque | state VLA only makes high-level task decisions | P0 | open |
| R-011 | 12U scaled model confused with 300-500 kg concept platform | report scale logic becomes inconsistent | same CAD called both CubeSat model and 300-500 kg platform | define 12U as display/verification model and 300-500 kg as concept extension | P1 | open |
| R-012 | `T_SB` not recorded before Stage 2 | GJM/RNS model cannot reproduce layout | adapter CAD lacks frame marker | require frame marker and transform export | P0 | open |
| R-013 | material and density not recorded | mass/inertia budget cannot be traced | CSV lacks material/source/confidence | fill source fields before mass property use | P1 | open |
| R-014 | target model inertia missing | Stage 2 capture scenario incomplete | target CSV rows blank | estimate target mass/CG/MOI from CAD or documented primitive | P2 | open |
