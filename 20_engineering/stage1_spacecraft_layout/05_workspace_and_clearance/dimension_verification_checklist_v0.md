# Dimension Verification Checklist v0

## 1. Rule

This checklist records what must be verified before Stage 1-C CAD dimensions are treated as constraints. Items remain open until supported by manual review, CAD measurement, or documented source evidence.

| item | check target | evidence required | status |
|---|---|---|---|
| 6.5 mm protrusion | external protrusions from permitted surfaces | CAD measurement and Appendix B interpretation | open |
| 8.5 mm rail-to-first-protrusion | distance from rail reference to first protrusion | CAD measurement and Appendix B interpretation | open |
| rail contact zone | no component invades rail/contact surface | CAD section view and keepout overlay | open |
| robot folded envelope | folded arm remains inside allowed stowed envelope or documented demo envelope | folded pose screenshot and dimension export | open |
| solar panel stowed envelope | panel and hinge stow within allowed envelope | stowed screenshot and dimension export | open |
| antenna stowed envelope | antenna stow state does not violate protrusion or rail keepout | stowed screenshot and dimension export | open |
| camera protrusion | camera lens/bracket protrusion checked against external envelope | front face measurement | open |
| RBF/debug interface | remove-before-flight/debug interface does not conflict with rails or robot | interface location screenshot | open |
| target interface | target grasp fixture dimensions recorded and collision envelope defined | target model measurement | open |
| Appendix B manual review | drawing dimensions manually reviewed and entered | completed manual entry table | open |

## 2. Acceptance Rule

No CAD screenshot, report figure, or Stage 2 geometry export should state final compliance until all P0 dimension items above have evidence and review status.
