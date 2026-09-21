"""Frozen paths, hashes, schemas, flags and package inventory."""

from __future__ import annotations

PACKAGE_REL = (
    "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/"
    "mpi_bridge_consumer_crossbind_source_freeze_v1"
)

SOURCE_PINS = (
    {
        "id": "OWNER_ODR45",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_ODR45_TO_ODR49_MPI_CONFIRMATION_AND_TERMINAL_PATH_V1.yaml",
        "sha256": "69473BC19E020C6422B23C1758CFC343874F641781C9782E982036614C0849B5",
        "format": "yaml",
        "schema": "M7_OWNER_DECISION_ODR45_TO_ODR49_MPI_CONFIRMATION_AND_TERMINAL_PATH_V1",
    },
    {
        "id": "PHYSICAL_DYNAMICS_BRIDGE",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml",
        "sha256": "0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C",
        "format": "yaml",
        "schema": "B601_PHYSICAL_DYNAMICS_BRIDGE_V1",
    },
    {
        "id": "MPI_BRIDGE_GATE",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/08_gate/MPI_BRIDGE_GATE_V1.json",
        "sha256": "60911E3C88387E2ED53601F2B541649BF90D689C57C4E74225226AE6FD10C721",
        "format": "json",
        "schema": "MPI_BRIDGE_GATE_V1",
    },
    {
        "id": "E21_BRIDGED_CONSUMER_GATE",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/05_e21_bridged/E21_BRIDGED_ARM_PLACEMENT_GATE_V2.json",
        "sha256": "7F670C69C6EDCF6CBF783DC22843C9EF53FD82FA88313E913C855FEB0A47E707",
        "format": "json",
        "schema": "E21_BRIDGED_ARM_PLACEMENT_GATE_V2",
    },
    {
        "id": "BRIDGED_MASS_INERTIA",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/06_mass_propagation/SYSTEM_MASS_PROPERTIES_BRIDGED_V1.yaml",
        "sha256": "E5D13A8D105B78C703EFA963BCF73714586E564F9951228AFBA9AF81ECB71528",
        "format": "yaml",
        "schema": "SYSTEM_MASS_PROPERTIES_BRIDGED_V1",
    },
    {
        "id": "MECH_DYNAMICS_V6_CANDIDATE",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/07_rebind/MECH_DYNAMICS_INTERFACE_V6_CANDIDATE.yaml",
        "sha256": "4C52A68AA6E0749A2425D9E8CDB6C9F4477F5D4047C9D6C0BA6F0D95E97D184D",
        "format": "yaml",
        "schema": "MECH_DYNAMICS_INTERFACE_V6_CANDIDATE",
    },
    {
        "id": "EMBODIED_R3_CANDIDATE",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/07_rebind/EMBODIED_MECHANICAL_CONTRACT_R3_CANDIDATE.yaml",
        "sha256": "F3D6EC1D370FB26215A259391D5026CA4C261C7C4880AE6FD70AE2C0F0DDFC56",
        "format": "yaml",
        "schema": "EMBODIED_MECHANICAL_CONTRACT_R3_CANDIDATE",
    },
    {
        "id": "UNIFIED_R2_FRAME_TREE",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/source_only_v2/UNIFIED_R2_SYSTEM_FRAME_TREE_V2.yaml",
        "sha256": "5F8B19DC5BF14EFBB3C6A781C6816D52FE80804DAB328821623E165239999756",
        "format": "yaml",
        "schema": "UNIFIED_R2_SYSTEM_FRAME_TREE_V2",
    },
    {
        "id": "UNIFIED_R2_SOURCE_GATE",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/source_only_v2/UNIFIED_R2_URDF_SOURCE_GATE_V2.json",
        "sha256": "62BF5F629DEA904D63115EEE5FE7DB718A5B5EDE73B5A78B1EBFE36BC1314D7F",
        "format": "json",
        "schema": "UNIFIED_R2_URDF_SOURCE_GATE_V2",
    },
    {
        "id": "INTAKE_GATE",
        "path": "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/current_system_handoff_intake_v1/results/CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_GATE_V1.json",
        "sha256": "23903C1AF1A6F7382A18E0685EF6A6010926B8C812163900BC3843B7A44BE5CE",
        "format": "json",
        "schema": "CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_GATE_V1",
    },
    {
        "id": "INTAKE_TERMINAL",
        "path": "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/current_system_handoff_intake_v1/results/CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_TERMINAL_V1.json",
        "sha256": "543EC2247910E4E5B884EF27CC99F78ECE842B8DBF0AE55891656894ADCEBF10",
        "format": "json",
        "schema": "CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_TERMINAL_V1",
    },
    {
        "id": "PREEXEC_GATE",
        "path": "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/preexecution_binding_security_source_freeze_v1/results/UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_GATE_V1.json",
        "sha256": "BBD13022F1462A59AC650EFC535C448C2004C113832E6C6ACD04C11F3EDE1F08",
        "format": "json",
        "schema": "UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_GATE_V1",
    },
    {
        "id": "PREEXEC_TERMINAL",
        "path": "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/preexecution_binding_security_source_freeze_v1/results/UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_TERMINAL_V1.json",
        "sha256": "7E4AF02594E187942AAE67F7AD568B89E3BFD1BEA1369AAD6251F8C34EFD8D06",
        "format": "json",
        "schema": "UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_TERMINAL_V1",
    },
    {
        "id": "PREEXEC_RECEIPT_VERIFIER_SOURCE",
        "path": "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/preexecution_binding_security_source_freeze_v1/preexec_security/receipts.py",
        "sha256": "D20AD3610764C83FE7D0453A47AF6327D8260160B8C16E44E341836F422B890B",
        "format": "python",
        "schema": None,
    },
    {
        "id": "PREEXEC_STRICT_JSON_SOURCE",
        "path": "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/preexecution_binding_security_source_freeze_v1/preexec_security/strict_json.py",
        "sha256": "789C0FC73A709A8D52CA122D9C94E6D347C03E6D79D91FB4DEC56E2EBAB72E23",
        "format": "python",
        "schema": None,
    },
)

SOURCE_PIN_BY_ID = {item["id"]: item for item in SOURCE_PINS}

MANDATORY_FALSE_FLAGS = (
    "system_urdf_available",
    "interface_instantiated",
    "current_system_bound",
    "production_dynamics_ready",
    "physical_contact_ready",
    "contact_execution_authorized",
    "grasp_execution_authorized",
    "grasp_training_authorized",
    "next_stage_authorized",
    "release_credit",
)

CHANNELS = ("frame", "mass", "inertia", "wrench", "collision_geometry")

INTERNAL_SOURCE_FILES = (
    "README.md",
    "pytest.ini",
    "crossbind/__init__.py",
    "crossbind/constants.py",
    "crossbind/strict_io.py",
    "crossbind/source_bundle.py",
    "crossbind/bridge.py",
    "crossbind/receipt.py",
    "crossbind/policy.py",
    "crossbind/negative_controls.py",
    "crossbind/package.py",
    "contracts/MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_FREEZE_CONTRACT_V1.json",
    "contracts/SYSTEM_BINDING_V3_CANDIDATE_RECEIPT_SCHEMA_V1.json",
    "contracts/MPI_BRIDGE_TO_SIM13_CROSSBIND_NEGATIVE_CONTROL_CONTRACT_V1.json",
    "freeze_mpi_bridge_to_sim13_crossbind.py",
    "run_mpi_bridge_to_sim13_crossbind_negative_controls.py",
    "validate_mpi_bridge_to_sim13_crossbind_source_freeze.py",
    "independent_audit_mpi_bridge_to_sim13_crossbind.py",
    "verify_mpi_bridge_to_sim13_crossbind_read_only_replay.py",
    "tests/conftest.py",
    "tests/test_sources_and_bridge.py",
    "tests/test_receipt_and_policy.py",
    "tests/test_controls_and_inventory.py",
)

GENERATED_FILES = (
    "manifest/MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_MANIFEST_V1.json",
    "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_PYTEST_RECEIPT_V1.json",
    "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_VALIDATION_V1.json",
    "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_NEGATIVE_CONTROLS_V1.json",
    "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_INDEPENDENT_AUDIT_V1.json",
    "results/MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_FREEZE_GATE_V1.json",
    "results/MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_FREEZE_TERMINAL_V1.json",
)

EXACT_FILE_ALLOWLIST = frozenset(INTERNAL_SOURCE_FILES + GENERATED_FILES)
EXACT_DIRECTORY_ALLOWLIST = frozenset(("crossbind", "contracts", "manifest", "evidence", "results", "tests"))

FORBIDDEN_SUFFIXES = frozenset(
    (".urdf", ".sdf", ".xacro", ".step", ".stp", ".fcstd", ".stl", ".obj", ".dae", ".ply", ".gltf", ".glb")
)
FORBIDDEN_CACHE_PARTS = frozenset(("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"))

GATE_REL = "results/MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_FREEZE_GATE_V1.json"
TERMINAL_REL = "results/MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_FREEZE_TERMINAL_V1.json"
MANIFEST_REL = "manifest/MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_MANIFEST_V1.json"
PYTEST_REL = "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_PYTEST_RECEIPT_V1.json"
VALIDATION_REL = "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_VALIDATION_V1.json"
NEGATIVE_REL = "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_NEGATIVE_CONTROLS_V1.json"
AUDIT_REL = "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_INDEPENDENT_AUDIT_V1.json"
