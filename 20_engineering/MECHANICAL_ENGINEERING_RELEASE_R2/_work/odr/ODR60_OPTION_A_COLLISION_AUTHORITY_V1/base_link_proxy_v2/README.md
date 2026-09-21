# B601 `base_link` operational collision proxy V2

This directory is the STEP-first, fail-closed replacement for the historical V1 HOLD. The V1 diagnostic remains unchanged in `../base_link_proxy/`.

## Design disposition

- Retain 66 valid, fully meshable B50 source solids.
- Replace source traversal solids 58 and 59 (`DM-J4340P:3`) by one tolerance-aware AABB that strictly contains both source bboxes.
- Replace source traversal solid 68 (thin base plate with five non-triangulating faces) by its tolerance-aware AABB.
- Do not consume the accepted-URDF raw `base_link.STL`; its known hash is a negative-control sentinel only.
- The downloaded step.parts `DM-J4340P-2EC` model is retained as a high-confidence catalog candidate but is not promoted: it is 17/18 BRep-valid, differs in volume by +0.15089%, and its exact local `2EC` revision binding is unproved.

The replacement regions inflate by 55.6771% relative to the three substituted source-solid volumes; the complete proxy inflates by 20.8803% relative to the filtered B50 B-Rep. This is deliberate collision conservatism, not mass or hardware geometry.

## Reproduction

From the workspace root:

```powershell
python -X utf8 F:/codex_skill/AgentSkills/agents-skills/cad/scripts/step `
  20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/base_link_proxy_v2/generate_base_link_operational_collision_step_v2.py `
  -o 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/base_link_proxy_v2/B601_BASE_LINK_OPERATIONAL_COLLISION_PROXY_V2.step `
  --stl B601_BASE_LINK_OPERATIONAL_COLLISION_PROXY_V2_PREVIEW.stl `
  --glb B601_BASE_LINK_OPERATIONAL_COLLISION_PROXY_V2_PREVIEW.glb `
  --mesh-tolerance 0.05 --mesh-angular-tolerance 0.15 --force

python -X utf8 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/base_link_proxy_v2/emit_base_link_operational_collision_v2.py --replace --emit
python -X utf8 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/base_link_proxy_v2/validate_base_link_operational_collision_v2.py --replace --write
```

## Scope

The V2 receipt and validation establish only local `base_link` collision geometry. They explicitly do not authorize system-pair evaluation, path search, Route-C mission coverage, mechanical release, or Sim13 consumer admission. The system registry therefore remains at 11,175 enumerated pairs with 9 adjacent exceptions and 11,166 `UNASSESSED_FAIL_CLOSED` pairs.
