# CAD Viewer handoff

- Explicit STEP:
  `v22_mechanical_continuation.step`
- Viewer skill version: installed `text-to-cad` `0.3.9`.
- Required launcher attempted:

  `npm --prefix <cad-viewer>/scripts/viewer run agent:start -- --host 127.0.0.1 --dir <this-directory> --json`

- Result: failed immediately with exit code `1` and
  `npm error Missing script: "agent:start"`.
- Installed runtime `package.json` exposes only `serve`, `start`, and MoveIt2
  scripts.
- Root-level recovery used the bundled `start` backend without a `--port`
  argument, so the runtime selected its documented default port `4178`. The
  backend was bound to this artifact directory; `GET /__cad/server` and the
  explicit STEP page both returned HTTP `200`.
- Live review:
  `http://127.0.0.1:4178/?file=v22_mechanical_continuation.step`
- Deterministic CAD CLI inspection and the generated PNG snapshot packet remain
  the evidence authority; the live Viewer is a review aid.
