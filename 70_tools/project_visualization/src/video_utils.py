"""VIZ-Gate 0 Phase 4 -- shared replay-video helpers.

Read-only replay of EXISTING simulation results (no sweep is ever rerun).
Every video produced through these helpers:
  * carries a provenance footer on EVERY frame (=> first and last frame
    included): runtime git commit + data source files + scenario_hash where
    applicable (iron rule 4);
  * is written with ffmpeg (F:\\ffmpeg-...\\bin on PATH) via
    matplotlib.animation.FFMpegWriter at >= 1280x720, fps 20-30;
  * registers keyframe checks (displayed value vs source-CSV value) that are
    collected into 40_evidence/artifacts/visualization/tables/replay_keyframe_check.csv.

Status-semantics red line (iron rule 3): color constants come from
20_engineering/config/visualization/display_semantics_v1.yaml only; UNKNOWN / missing
evidence is never recolored as safe or unsafe.
"""
import _viz_bootstrap as vb  # noqa: F401  (env pins BEFORE numpy)
import csv
import json
import os
import shutil
import subprocess

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib.animation import FFMpegWriter         # noqa: E402
import yaml                                           # noqa: E402

# ---------------------------------------------------------------- ffmpeg
FFMPEG_BIN_DIR = r"F:\ffmpeg-master-latest-win64-gpl-shared\bin"
FFMPEG = shutil.which("ffmpeg") or os.path.join(FFMPEG_BIN_DIR, "ffmpeg.exe")
FFPROBE = shutil.which("ffprobe") or os.path.join(FFMPEG_BIN_DIR, "ffprobe.exe")
matplotlib.rcParams["animation.ffmpeg_path"] = FFMPEG

VIDEO_DIR = os.path.join(vb.REPO_ROOT, "videos", "visualization")
os.makedirs(VIDEO_DIR, exist_ok=True)
KEYFRAME_CSV = os.path.join(vb.VIZ_TABLES_DIR, "replay_keyframe_check.csv")
COMMIT = vb.repo_commit_short()
CJK_FONT = "Microsoft YaHei"          # present on this machine (checked)

# ---------------------------------------------------------------- semantics
with open(os.path.join(vb.VIZ_CONFIG_DIR, "display_semantics_v1.yaml"),
          encoding="utf-8") as _f:
    SEM = yaml.safe_load(_f)
SC = {k: v["hex"] for k, v in SEM["semantic_colors"].items()}
OBJ_C = SEM["object_colors"]
OV = SEM["overlay_styles"]

with open(os.path.join(vb.VIZ_CONFIG_DIR, "camera_presets_v1.yaml"),
          encoding="utf-8") as _f:
    CAMS = yaml.safe_load(_f)["presets"]


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


# ---------------------------------------------------------------- figure
def make_fig(width_px=1280, height_px=720, dpi=100, facecolor="white"):
    fig = plt.figure(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)
    fig.patch.set_facecolor(facecolor)
    return fig


def add_provenance(fig, sources, scenario_hash=None, extra=None):
    """Persistent provenance footer -- present on EVERY frame (covers the
    iron-rule-4 requirement for first + last frame)."""
    txt = f"git {COMMIT} | data: {', '.join(sources)}"
    if scenario_hash:
        txt += f" | scenario_hash {scenario_hash}"
    if extra:
        txt += f" | {extra}"
    return fig.text(0.995, 0.004, txt, ha="right", va="bottom", fontsize=6.0,
                    color="#555555", family="monospace", zorder=100)


def add_watermark(fig, text="DIAGNOSTIC — NOT GATE VALIDATED", alpha=0.16,
                  fontsize=30, color="#7d0000"):
    """Diagonal watermark on every frame (iron rule 3, flexible animations)."""
    return fig.text(0.5, 0.52, text, ha="center", va="center",
                    fontsize=fontsize, color=color, alpha=alpha,
                    rotation=22, fontweight="bold", zorder=99)


# ---------------------------------------------------------------- 3D meshes
def face_colors(V, F, rgb, alpha=1.0, light=(0.35, -0.5, 0.8),
                shade=(0.45, 1.0)):
    """Same Lambertian shading math as mesh_utils.shaded_collection (reused
    per-frame so a rotating body is re-lit consistently)."""
    tri = V[F]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1)
    ln[ln == 0] = 1.0
    n = n / ln[:, None]
    L = np.asarray(light, float)
    L = L / np.linalg.norm(L)
    lam = np.abs(n @ L)
    lo, hi = shade
    k = lo + (hi - lo) * lam
    base = np.asarray(rgb, float)[:3]
    out = np.empty((len(F), 4))
    out[:, :3] = np.clip(base[None, :] * k[:, None], 0, 1)
    out[:, 3] = alpha
    return out


class MeshActor:
    """A posed display mesh whose transform can be updated per frame."""

    def __init__(self, ax, V, F, hexcolor, alpha=1.0):
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        self.V0 = np.asarray(V, float)
        self.F = np.asarray(F, np.int64)
        self.rgb = hex_rgb(hexcolor)
        self.alpha = alpha
        self.pc = Poly3DCollection(self.V0[self.F],
                                   facecolors=face_colors(self.V0, self.F,
                                                          self.rgb, alpha),
                                   edgecolors="none", linewidths=0.0)
        ax.add_collection3d(self.pc)

    def set_transform(self, T):
        V = self.V0 @ np.asarray(T, float)[:3, :3].T + np.asarray(T, float)[:3, 3]
        self.pc.set_verts(V[self.F])
        self.pc.set_facecolor(face_colors(V, self.F, self.rgb, self.alpha))
        return V

    def set_vertices(self, V):
        V = np.asarray(V, float)
        self.pc.set_verts(V[self.F])
        self.pc.set_facecolor(face_colors(V, self.F, self.rgb, self.alpha))
        return V

    def set_alpha(self, alpha):
        self.alpha = alpha


# ---------------------------------------------------------------- rendering
def check_nonblank(fig, min_std=10.0):
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].astype(float)
    return float(buf.std()) >= min_std, float(buf.std())


def render_video(path, fig, n_frames, draw_frame, fps=24, crf=21):
    """Render n_frames via draw_frame(k) into an H.264 mp4."""
    writer = FFMpegWriter(fps=fps, codec="libx264",
                          extra_args=["-pix_fmt", "yuv420p", "-crf", str(crf),
                                      "-preset", "medium"])
    with writer.saving(fig, path, fig.dpi):
        for k in range(n_frames):
            draw_frame(k)
            if k == 0:
                ok, std = check_nonblank(fig)
                if not ok:
                    raise RuntimeError(f"first frame blank (std={std:.1f}): {path}")
            writer.grab_frame()
    return path


def video_info(path):
    """(duration_s, size_MB, width, height) via ffprobe."""
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height:format=duration,size", "-of", "json", path],
        capture_output=True, text=True, timeout=60)
    d = json.loads(out.stdout)
    return (float(d["format"]["duration"]),
            int(d["format"]["size"]) / 1e6,
            int(d["streams"][0]["width"]), int(d["streams"][0]["height"]))


# ---------------------------------------------------------------- keyframes
KF_HEADER = ["video", "frame_index", "video_time_s", "quantity",
             "anim_value", "csv_value", "abs_diff", "tolerance", "match",
             "source", "note"]


def kf_row(video, frame, t, qty, anim, csvv, source, tol=0.0, note=""):
    """One keyframe consistency record: `anim` is EXACTLY the value used to
    render the on-screen text; `csvv` is re-read from the source file.
    tol = 0 for values read straight from the CSV; for recomputed values it is
    half an ULP of the CSV's printed precision (float display rounding)."""
    if isinstance(anim, str) or isinstance(csvv, str):
        diff = "" if str(anim) == str(csvv) else "STR_MISMATCH"
        match = str(anim) == str(csvv)
    else:
        diff = abs(float(anim) - float(csvv))
        match = diff <= tol
    return {"video": video, "frame_index": frame, "video_time_s": round(t, 3),
            "quantity": qty, "anim_value": anim, "csv_value": csvv,
            "abs_diff": diff, "tolerance": tol, "match": bool(match),
            "source": source, "note": note}


def update_keyframe_csv(video, rows, path=KEYFRAME_CSV):
    """Replace this video's rows in the shared keyframe-check CSV."""
    existing = []
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            # Treat an accidental filename-form alias (``name.mp4``) as the
            # same logical video, so repeated builders cannot leave duplicate
            # keyframe groups behind.
            logical = os.path.splitext(video)[0]
            existing = [r for r in csv.DictReader(f)
                        if os.path.splitext(r.get("video", ""))[0] != logical]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=KF_HEADER, extrasaction="ignore")
        w.writeheader()
        for r in existing + list(rows):
            w.writerow(r)
    bad = [r for r in rows if str(r["match"]) not in ("True", "true")]
    return len(rows), bad
