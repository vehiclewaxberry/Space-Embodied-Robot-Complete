# Deployable State Checklist v0

## 1. Deployable States

| state | ground demo meaning | on-orbit safety meaning | required evidence | status |
|---|---|---|---|---|
| stowed | panel/antenna/robot fixed in compact display position | launch or safe storage envelope | CAD stowed view and dimension check | open |
| locked | mechanical lock or demonstration fixture holds deployable | lock prevents accidental motion | lock placeholder and release logic note | open |
| released | lock removed or demo command issued | deployment sequence begins | state transition note | open |
| deployed | deployable reaches display or work position | operational geometry reached | deployed envelope view | open |
| working | robot/camera/panel used in task demonstration | normal mission operation | workspace and FOV evidence | open |
| abnormal safe | emergency stop or safe folded posture | collision and power-safe state | safe posture and keepout evidence | open |

## 2. Timing Distinction

- Ground demo timing may be manual, scripted, or staged for the video.
- On-orbit safety timing must be written as a concept or requirement only unless verified by a deployment design.
- The report must distinguish demonstration choreography from flight deployment logic.

## 3. Required Deployables

- robot arm folded/deployed/safe state.
- left and right solar panel stowed/deployed state.
- antenna stowed/deployed state.
- any target grasp handle or cooperative fixture if it has moving parts.
