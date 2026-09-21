# B5.1 interface control drawing contract

Drawing level:

`ENGINEERING_DEFINITION_DRAWING_NOT_MANUFACTURING_RELEASE`

## Controlling datum chain

`CS_S -> TASK_FACE_X=183 -> B51 bridge adapter -> M_PLANE_X=198 -> A0`

The dynamics/PDR track at 185.25 mm and the V2.2 display track at 198.0 mm
remain separate. Their 12.75 mm difference must not be collapsed.

## Candidate load path

`B601 base wrench -> 25 degree top flange -> short center pedestal -> forward
and aft crossmembers -> named interface shoes -> main frames/longerons`

Decks, equipment panels, and exterior skins are excluded from the primary
load path.

## Frozen or admitted geometry

- task face X: 183.0 mm
- V2.2 display installation plane X: 198.0 mm
- dynamics/PDR interface coordinate X: 185.25 mm
- longeron reference centers: Y/Z = +/-105.65 mm
- MID1 frame: X=61.0 mm
- MID2 frame: X=-61.0 mm
- top installation reference: 160 x 160 mm
- central passage reservation: diameter 100 mm
- B5.1 clocking candidate: 25 degrees about the B601 A0/J1 axis

## Open physical fields

Bolt pattern, hole count and size, locating pins, interface shoes, material,
thickness qualification, tolerance, preload, locking, grounding, thermal
isolation, connector routing, tool clearance, six-dimensional load cases, and
launcher interface remain `UNKNOWN/TBD/HOLD`.
