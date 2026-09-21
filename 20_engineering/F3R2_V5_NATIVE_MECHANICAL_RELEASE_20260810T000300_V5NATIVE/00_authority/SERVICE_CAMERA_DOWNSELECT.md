# SERVICE_CAMERA down-select — V5 authority seed

Decision: `SERVICE_CAMERA = UNSELECTED`; freeze only `CAMERA_INTERFACE_STANDARD` and `CAMERA_ENVELOPE`.
The current conditional prototype preference is Intel RealSense D405 with the local `D405_305_Mount.step`, but this is not a purchase, model-selection, calibration, or release authority.

| Candidate donor | Local mount envelope (mm) | Mass | FOV / working distance / minimum range | Data | Mountability | Occlusion evidence | Disposition |
|---|---:|---|---|---|---|---|---|
| D435/Gemini2 mount | 95.761 × 53.515 × 28.464 | Camera and mount mass not authorized | No authoritative local camera model or optical data | Connector/USB route not closed | B601 wrist donor geometry exists; camera-side interface is geometry-only | Not evaluated with a selected camera | `VENDOR_DONOR_ONLY` |
| D405/305 mount | 94.448 × 70.906 × 33.962 | Camera, cable and printed mount mass not authorized | Driver, depth, intrinsics, FOV, working distance and minimum range not locally closed | Eye-in-hand TF clue exists; USB/data implementation not closed | Best local evidence: mounted-photo plus TF clue; physical fit still required | Final wrist/gripper/FOV sweep missing | `CONDITIONAL_PROTOTYPE_ROUTE_NOT_RELEASED` |
| UVC32 mount | 70.002 × 69.444 × 32.311 | Not authorized | No authoritative local intrinsics/FOV/range evidence | USB/data and connector details not closed | Four-hole donor geometry only | Not evaluated | `VENDOR_DONOR_ONLY_LOWEST_LOCAL_MATURITY` |

Frozen wrist-side candidate interface: contact cylinder radius 28.5 mm, two geometry-only Ø2.7 mm holes at 22.0 mm spacing, nominal mount-plane tilt 15°. These values are not thread, tolerance, optical-frame or calibration authority.

Activation requires exact camera part number, OEM ICD/CAD, physical fit, mass/CoM, connector and cable, driver/depth/intrinsics, hand–eye calibration, FOV/occlusion and swept-clearance PASS. Until then: `CAMERA_MODEL_SELECTION_HOLD`.
