# Collision Keepout Zone Plan v0

## 1. Purpose

This plan defines the keepout zones to be modeled and visualized in Stage 1-C. It is a layout requirement document, not a completed collision analysis.

## 2. Keepout Zones

| zone | definition | affected objects | required output |
|---|---|---|---|
| servicer body keepout | volume occupied by the 12U/6U bus body plus clearance margin to be defined | robot links, end-effector, target | body collision overlay |
| solar panel keepout | stowed and deployed panel swept volume | robot, camera FOV, antenna | left/right panel clearance view |
| rail keepout | rail/contact-surface and deployment interface exclusion volume | adapter, robot, camera, protrusions | rail keepout overlay |
| robot arm motion keepout | swept volume from folded to maximum extension and task poses | solar panels, antenna, servicer body, target | workspace envelope plot or CAD view |
| camera FOV keepout | volume that must remain clear for target observation | robot links, panels, antenna | FOV occlusion view |
| target non-grasp region keepout | target body surfaces not intended for contact | end-effector and links | approach/capture contact map |

## 3. Contact and Approach Requirements

- End-effector approach speed limit must be defined before dynamic contact simulation or ground contact testing.
- Contact-stage impedance control requirements must be documented before claiming compliant capture.
- The target non-grasp region must be visually separated from allowed grasp features.

## 4. Visualization Requirements

Stage 1-C CAD or plotting output should show:

- transparent body keepout volume.
- solar panel and antenna swept envelopes.
- robot maximum workspace.
- camera FOV.
- target collision envelope and allowed grasp feature.

These visuals are design checks only and must not be described as simulation validation.
