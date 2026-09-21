# B5.1 bridge adapter and double-triangle saddles

Status:

`ENGINEERING_CANDIDATE_WITH_EXPLICIT_H9_H10_CONTACT_HDRM_HOLDS`

These build123d sources implement the B5.1 geometry candidate only. They do
not release hardware for manufacturing, flight, mass properties, FEA, or
dynamic authority.

## Admitted inputs

- Spacecraft task face: `X = 183.0 mm`.
- B601 display-track installation plane: `X = 198.0 mm`.
- Installation reference: `160 x 160 mm`.
- Central passage: `diameter 100.0 mm`.
- Longeron reference centres: `Y/Z = +/-105.65 mm`.
- Installation clock: `25 deg`, status
  `RATIFIED_FOR_B5_1_ENGINEERING_CANDIDATE_ONLY`.
- G07 contact window: `X=[10,60] mm`, `Y=[-66.48,92.89] mm`,
  bottom `Z=234.77 mm`, contact qualification HOLD.
- G08 contact window: `X=[-100,-40] mm`, `Y=[-27.25,104.24] mm`,
  bottom `Z=253.80 mm`, G08 chain-derived and contact qualification HOLD.

## Bridge-adapter topology

The authored load path is:

`B601 root -> CLOCK25 top flange -> short annular pedestal -> forward/aft
crossmember frames -> four diagonal interface webs and shoes -> admitted
task-face frame/longeron reference regions`.

Its axial segmentation is:

| Candidate body | X range (mm) |
|---|---:|
| Four interface shoe/web bodies | 183 to 185 |
| Aft crossmember frame | 185 to 188 |
| Short annular pedestal | 188 to 193 |
| Forward crossmember frame | 193 to 196 |
| CLOCK25 top flange | 196 to 198 |

Adjacent bodies meet only on shared X planes. The four task-face shoes start
at `X=183`; no candidate body enters the admitted `X<183` primary-frame
volume. Every central body preserves the diameter-100 passage. The four
integral witness tabs visualize the 25-degree clock but are explicitly not a
bolt pattern.

## Saddle topology

Each saddle contains:

- two narrow base-tie shoes over the `Y=+/-105.65 mm` longeron-reference
  strips; the central equipment/deck span is not assigned as primary load
  path;
- separate forward and aft open triangular frames;
- one replaceable contact pad;
- low side guides outside the admitted contact Y window;
- one translucent non-physical HDRM reservation envelope below the pad and
  centred between the forward/aft triangular frames.

The primary-load-path bodies start at `Z=113.15 mm`; their lower faces are
candidate contact faces only. Materials, sections, attachment details,
tolerance, pad compliance, preload, release direction, switch hardware, and
HDRM selection remain HOLD.

## Unfrozen engineering-candidate dimensions

The following values exist only to create a coherent geometric candidate and
must not be read as requirements:

- Adapter flange `OD140 x 2`, pedestal `OD130 x 5`, both with `ID100`.
- Crossmember frames `160` outer span, `116` square clear opening.
- Interface web axial thickness `2`, task-face shoes `15 x 15`.
- Saddle base-tie height `4`, triangle frame X thickness `6`, strut width
  `10`, top cap height `6`.
- Replaceable pad thickness `3`, low-guide nominal thickness `8`, height `24`.
- HDRM non-physical reservation `diameter 16 x 36`.

All are tagged `ENGINEERING_CANDIDATE_HOLD` in source/body labels.

## Source and output map

- `b51_bridge_adapter.py` -> `03_CAD/step/B51_BRIDGE_ADAPTER.step`
- `b51_g07_main_saddle.py` -> `03_CAD/step/B51_G07_MAIN_SADDLE.step`
- `b51_g08_grip_saddle.py` -> `03_CAD/step/B51_G08_GRIP_SADDLE.step`

The common implementation and parameter authority split live in
`b51_geometry_common.py`.
