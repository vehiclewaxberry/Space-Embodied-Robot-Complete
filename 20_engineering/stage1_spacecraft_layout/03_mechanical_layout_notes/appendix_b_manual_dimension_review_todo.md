# Appendix B Manual Dimension Review TODO

> 2026-07-23 update: the 12U-only subset needed by COMP-PROT-03-A2 was manually reviewed and recorded in `10_research/space_embodied_robotics/comp_prot_03_a2_candidate_model_review/cds_appendix_b_12u_review_record.md`. The 1U/3U/6U and drawing-detail rows not covered by that record remain open.

## 1. Rule

CubeSat Design Specification Appendix B drawing dimensions must be manually reviewed before they are used as hard CAD dimensions. Do not fill any dimension, tolerance, or keepout value unless it has been manually verified from the drawing and recorded with source evidence.

## 2. Items Requiring Manual Review

- 1U outer dimensions.
- 3U outer dimensions.
- 6U outer dimensions.
- 12U outer dimensions.
- rail dimensions.
- rail/contact-surface keepout zones.
- tab or deployment interface dimensions, if used.
- protrusion-related measurement references.
- tolerances relevant to CAD envelope checks.

## 3. Manual Entry Table

| item_id | drawing/page_ref | screenshot_path | dimension_name | value | unit | tolerance | interpretation_note | reviewer | review_date | status |
|---|---|---|---|---|---|---|---|---|---|---|
| APPB-001 | TBD | TBD | 1U outer dimension | manual_review_required | TBD | TBD | do not fill from memory | TBD | TBD | open |
| APPB-002 | TBD | TBD | 3U outer dimension | manual_review_required | TBD | TBD | do not fill from memory | TBD | TBD | open |
| APPB-003 | TBD | TBD | 6U outer dimension | manual_review_required | TBD | TBD | do not fill from memory | TBD | TBD | open |
| APPB-004 | PDF p.34, CDS-14-008 | direct PDF page review; no exported screenshot retained | 12U rail-reference envelope | 366.0 × 226.3 × 226.3 | mm | no drawing tolerance promoted in A2 | candidate input only; existing 340.5 mm block model is not compliant evidence | Codex + Geometry read-only review | 2026-07-23 | reviewed_12U_scope_only |
| APPB-005 | PDF p.34 and p.12 | direct PDF page review; no exported screenshot retained | rail end contact surface | 6.5 × 6.5 minimum; at least 75% rail contact | mm / percent | source text limit | does not prove current CAD fit | Codex + Geometry read-only review | 2026-07-23 | reviewed_12U_scope_only |
| APPB-006 | PDF p.34 and p.11-p.12 | direct PDF page review; no exported screenshot retained | rail/protrusion keepout | 8.5 minimum rail-to-first-protrusion; 6.5 maximum yellow-face protrusion | mm | source text limit | whole-vehicle and deployer-specific checks remain open | Codex + Geometry read-only review | 2026-07-23 | reviewed_12U_scope_only |

## 4. Screenshot Path Convention

Suggested path format:

```text
20_engineering/stage1_spacecraft_layout/01_standards/appendix_b_review/screenshots/<source>_<drawing_id>.png
```

The screenshot folder is not created by this document. It is only a recommended evidence location for the manual review step.

## 5. Prohibition

- Do not enter unverified dimensions from memory.
- Do not infer dimensions from low-resolution screenshots.
- Do not state that the CAD model satisfies Appendix B until the checklist and dimension table are complete.
