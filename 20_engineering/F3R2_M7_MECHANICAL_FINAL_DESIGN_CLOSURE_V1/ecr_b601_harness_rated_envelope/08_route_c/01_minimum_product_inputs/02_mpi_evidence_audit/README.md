# Route-C MPI evidence audit and Owner input pack

## Machine result

- Gate: `HOLD`
- MPI controlled: `0/8`
- Next stage authorized: `false`
- CAD created/authorized: `0 / false`

This package audits the evidence already present in the repository and provides five blank, unit-bearing Owner input templates. It does not edit the accepted URDF or any prior Route-C/Route-B artifact.

## Decisive boundary

The accepted URDF supplies local J1..J6 kinematics only. RFI files, candidate catalog data, the upstream reBot BOM/readme, directories, and the eight E17 segment names/seeds do not close product, installation, or life authority. Route-B `OD=10 mm`, `R25`, `R30`, and `4001.158 mm` are quarantined and are not inherited.

## Owner completion sequence

1. Complete `B601_ELECTRICAL_AND_DATA_ICD_OWNER_INPUT_TEMPLATE_V1.yaml` for MPI-01/02.
2. Complete `WIRE_LIST_PINOUT_OWNER_INPUT_TEMPLATE_V1.yaml` for MPI-03/04.
3. Complete `INSTALLED_CONSTRUCTION_OWNER_INPUT_TEMPLATE_V1.yaml` for MPI-05/06.
4. Complete `INSTALLATION_ICD_OWNER_INPUT_TEMPLATE_V1.yaml` for MPI-07.
5. Complete `MISSION_LIFE_ALLOCATION_OWNER_INPUT_TEMPLATE_V1.yaml` for MPI-08.
6. Bind controlled source revisions, named owners, units, and uncertainty or bounded tolerance; then repeat independent validation.

Unknown values remain `null`. A zero may be entered only when a controlled source proves that the physical value is zero.

## Rebuild and validate

From the repository root:

```powershell
python 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/01_minimum_product_inputs/02_mpi_evidence_audit/99_tools/build_route_c_mpi_evidence_audit.py
python 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/01_minimum_product_inputs/02_mpi_evidence_audit/99_tools/validate_route_c_mpi_evidence_audit.py
```
