"""Local mast-frame prefabrication view, explicitly called by gen_step entries.

Each view contains 17 C02 candidate pieces plus the original parking saddle as
one clearly labelled context instance. No whole-spacecraft manifest is appended.
This is the current static arrangement: first saddle assembly, complete release
motion and physical closure are NOT established by viewing or exporting it.
The independent check_retention_detail.py receipts determine measured scope.
Importing this helper does not load CAD or build geometry.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
PINNED_PRODUCER_SHA256 = "14fd2319207e26410d3cb33efd3a523148a3eefe0af376a6bf50419518b1348c"
PINNED_CONTRACT_SHA256 = "cd4b40745ca081ed7dfa2c89cd7f811a4998ca2baf832e1e73b50dfe2a87ba8c"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def view_description(station_index):
    """Read-only view manifest; no CAD imports and no file writes."""
    k = int(station_index)
    if k not in (0, 1):
        raise ValueError("Only station 0 or 1 is defined")
    producer = HERE / "retention_detail.py"
    contract = RUN / "inputs/RETENTION_DESIGN_CONTRACT.json"
    if sha(producer) != PINNED_PRODUCER_SHA256 or sha(contract) != PINNED_CONTRACT_SHA256:
        raise ValueError("C02 view requires its pinned producer and contract; rebind only after review")
    c = json.loads(contract.read_text(encoding="utf-8-sig"))
    st = c["stations"][str(k)]["states"]["parking"]
    saddle_id = f"hold_saddle_{k}"
    context = st["sources"][saddle_id]
    if context["T_S_local"] != st["T_S_mast"]:
        raise ValueError("Context source is not already in the inherited mast-local frame")
    if sha(context["path"]) != context["sha256"]:
        raise ValueError("Original parking saddle STEP hash mismatch")
    return dict(station_index=k, title=f"WP07_RETENTION_STATION_{k}_LOCAL_STATIC_CANDIDATE",
                coordinate_frame="Inherited local mast frame, mm; S-frame parking transform is NOT applied",
                candidate_part_count=17, context_part_count=1,
                context_original_id=saddle_id, context_view_id="CONTEXT_PARKING_"+saddle_id,
                context_source=context, producer_path=str(producer), contract_path=str(contract),
                producer_sha256=PINNED_PRODUCER_SHA256, contract_sha256=PINNED_CONTRACT_SHA256,
                scope="Local prefabrication candidate. Static view/export is not first-installation, continuous motion or whole-spacecraft closure proof.",
                initial_saddle_installation_status="Use independent CHECK_local.json; view creates no validation credit")


def build_view(station_index):
    """Build one local 18-instance view; root owns guarded CAD execution."""
    info = view_description(station_index)
    spec = importlib.util.spec_from_file_location("wp07_pinned_retention_view_producer", info["producer_path"])
    producer = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = producer
    spec.loader.exec_module(producer)
    built = producer.build_station(info["station_index"], info["contract_path"])
    if len(built["parts"]) != info["candidate_part_count"]:
        raise ValueError("Expected exactly 17 C02 candidate parts")
    # build_station already installed the guarded cadgen font loader. Use the
    # direct reader here: no sidecar cache is written alongside frozen STEP.
    from build123d import Color, import_step
    from cadgen.assembly import AssemblyHelper

    def detach(shape):
        result = type(shape)(shape.wrapped)
        if result.parent is not None or getattr(result, "children", ()):
            raise RuntimeError("Unsafe view shape hierarchy detachment")
        return result.located(shape.global_location)

    assembly = AssemblyHelper(info["title"])
    for instance_id, shape in built["parts"].items():
        kind = built["metadata"]["provenance"][instance_id]["kind"]
        color = ((0.72, 0.38, 0.60) if "NOMINAL" in kind else
                 (0.83, 0.56, 0.22) if "COLLAR" in kind else
                 (0.70, 0.73, 0.78) if "CATALOGUE" in kind else (0.52, 0.63, 0.74))
        assembly.add(detach(shape), instance_id, color=Color(*color))
    context = info["context_source"]
    saddle = detach(import_step(context["path"]))
    if not saddle.is_valid or len(saddle.solids()) != 1:
        raise ValueError("Parking context saddle must be one valid actual solid")
    assembly.add(saddle, info["context_view_id"], color=Color(0.43, 0.49, 0.53))
    # Recheck bytes after pure reads, including all producer-pinned source inputs.
    producer.read_contract(info["contract_path"])
    if sha(context["path"]) != context["sha256"]:
        raise ValueError("Parking saddle changed during view build")
    view = assembly.build()
    view.label = info["title"]
    return view
