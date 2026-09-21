# B51 stowage load path

Status: `LOAD_PATH_CONCEPT_DEFINED_PHYSICAL_PATH_NOT_CLOSED`

The intended three-direction paths are:

- vertical restraint: contact pad → replaceable pad seat → twin triangular
  frames → two interface shoes → named primary frames/longerons;
- lateral restraint: low guide pair → local frame webs → the same independent
  primary-structure shoes;
- axial restraint: dedicated stop face → forward/aft frame pair → primary
  frame/longeron attachments.

The live candidate does not realize that path.  Exact BREP evidence shows the
G07 and G08 assemblies seat on the removable-panel surface and remain 3.0 mm
from the canonical primary structure.  The current effective path is therefore
`pad → saddle → removable panel → UNKNOWN`, which is not accepted.

The double-triangle topology remains a useful concept, but no load may be
credited until the corrected canonical skeleton, panel treatment, attachment
faces and assembly direction are defined.  Materials, sections, fasteners,
preload, tolerance and formal launch loads remain `UNKNOWN/TBD`.

