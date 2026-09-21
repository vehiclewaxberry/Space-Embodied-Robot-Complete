# V22 mechanical continuation snapshot review

## Render route

- The unmodified CAD snapshot CLI was attempted first.
- That first attempt failed immediately because the optional Playwright bundled
  Chromium executable was not installed; no render process remained running.
- `snapshot_with_system_chrome.py` then ran the same installed CAD snapshot
  implementation while injecting the already-installed system Chrome
  executable. No browser was downloaded and no plugin file was modified.

## Reviewed outputs

- `full_assembly_isometric_20260726T125048Z.png`
- `mechanical_mainline_isometric_20260726T125107Z.png`
- `b601_mount_interface_20260726T125117Z.png`
- `arm_stow_solar_root_20260726T125127Z.png`
- `c5_width_end_view_20260726T125139Z.png`

## Visual findings

- The bus, bilateral stowed solar wings, B601 front adapter/mount, root
  mechanisms, support reservations, exterior functional surfaces, and detached
  capture-stack display reference all render as non-empty BREP geometry.
- The detached capture stack at the B5 display anchor is visibly separated
  from the bus. This is intentional and is labeled
  `DETACHED_DISPLAY_ANCHOR_NOT_KINEMATICS`; it is not a B601 pose.
- The B601 front view shows the central interface, offset connector reservation,
  front load-spreader plate, diagonal proposal ribs, and straight four-way
  staging webs. The red translucent root keep-out/axis objects are explicitly
  non-physical references.
- The end views make the bilateral root hardware and stowed-wing package visibly
  wider than the bus body. The screenshot is diagnostic only; deterministic
  face measurements establish `238.3 mm > 226.3 mm`, and the assembly Y bounds
  establish the represented root-mechanism lower bound `302.3 mm`.
- Bilateral wing frames and three inset cell-zone bodies per wing are visible;
  they remain display proposals and do not establish solar deployment
  clearance or panel performance.
- Main-arm and wrist/gripper supports are present, but exterior context can
  occlude their support pads in a full assembly view. Their occurrence bboxes
  and labels were therefore checked deterministically instead of upgraded from
  appearance.

## Renderer limitation

The shortcut `--focus` views retained broader assembly context in the produced
images. No claim of successful visual occurrence isolation is made. Geometry
identity and dimensions use CAD `refs`, `measure`, `align`, and `frame` outputs,
not screenshot appearance.

## Review conclusion

No visual issue contradicted the deterministic geometry contract. The model is
acceptable as isolated mechanical-integration staging geometry subject to its
claim limits. C5, contact-face qualification, release design, structural
qualification, native SolidWorks configurations, BOM exclusion, and mass
exclusion remain unverified or inapplicable.
