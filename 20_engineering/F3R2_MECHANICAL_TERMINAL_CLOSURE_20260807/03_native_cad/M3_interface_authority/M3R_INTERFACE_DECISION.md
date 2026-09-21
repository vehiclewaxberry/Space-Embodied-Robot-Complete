# M3R interface-authority decision

## Decision

The local search found no released OEM B601 interface ICD, no released OEM
mounting drawing, and no accepted project physical interface contract. It did
find vendor product geometry (A2) and a measurable active assembly (B2).

The former `8 x M3 @ PCD 90.51 mm` claim is rejected. The STEP contains four
physical `HM4-75` screw axes; each shaft was represented by two cylindrical
face records and the former script counted faces instead of unique axes. The
correct competition input is therefore:

> `4 x M4-class fastener stack on a 64 x 64 mm square`
>
> equivalent PCD `90.50965 mm`, clocked approximately `+25 deg` about the
> spacecraft X axis.

This input is authorized only as `AS_BUILT_MEASURED_COMPETITION_INTERFACE`.
It is not an OEM flight-interface claim.

## Spacecraft-side ruling

The legacy FreeCAD adapter is real standalone B-rep but is not instantiated in
the active F3R2 top assembly. Its M8 BCD130 pattern is rejected for the current
design because the +Y hole is breached by the harness slot and the historical
arm-side role conflicts with the vendor/as-built M4 evidence. Its four M6
clearance holes at `(+/-70, +/-70) mm` are complete and agree with the
historical spacecraft-side label. The M6 square is selected only as the
competition-prototype primary-pattern candidate; no live Central_Boss/load-
bridge mating pattern has yet been verified. The M8 pattern is omitted.

## Adapter architecture

The generated competition-prototype geometry candidate is a two-part adapter:

1. `B601_BASE_INTERFACE_RING_F3R2`: four M4-class pickup locations, recessed
   into the central passage so the accepted arm position does not move.
2. `B601_LOAD_SPREADING_ADAPTER_F3R2`: stiff 160 mm load-spreading body, joined
   to the ring by a new controlled M5 transition pattern and attached to a
   future competition load bridge by the candidate four-hole M6 square.

The M5 inter-stage pattern is new F3R2 engineering geometry, not a recovered
OEM feature. Rev B carries each M5 clearance through the full 8.0 mm Stage-A
bearing zone and through the 6.405 mm remaining Stage-B section. A single
asymmetric dowel candidate at `(55, 0) mm` removes the former 45-degree
geometric ambiguity. Dowel fit class/tolerances, through-fastener length,
nut/washer access, preload and margin-of-safety checks remain holds until an
authorized load case and physical fit-up exist. The four M6 clearance holes
have only 6.7 mm nominal net edge margin and require a dedicated edge-bearing,
tear-out and local-bending assessment.

## Gate state

- `M3_AS_BUILT_COMPETITION_INTERFACE_AUTHORIZED`: **PASS**
- FreeCAD/STEP ring+body geometric candidate: **PASS**
- `M3_TWO_STAGE_ADAPTER_INTERFACE_CLOSED`: **HOLD** - SolidWorks native parts
  and assembly are absent, cold reopen/native interference are unrun, the M6
  mating load-bridge geometry is unverified, B601 physical fit-up is unrun,
  the clocking-dowel fit/tolerance is unresolved, and the M6 edge margin has
  not been structurally assessed
- OEM flight interface: **NOT CLAIMED**
- accepted URDF, mass ledger, donor and F3R1: **immutable**
