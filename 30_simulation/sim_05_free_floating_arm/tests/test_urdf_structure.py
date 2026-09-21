"""URDF structural checks for arm_b601_v1 (no dynamics)."""
import os
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SIM05 = os.path.dirname(HERE)
sys.path.insert(0, SIM05)

from b601_model import URDF_PATH  # noqa: E402


def _root():
    return ET.parse(URDF_PATH).getroot()


def test_six_revolute_joints():
    """Exactly 6 revolute joints named joint1..joint6; gripper_joint fixed;
    two prismatic finger joints."""
    root = _root()
    joints = {j.get("name"): j.get("type") for j in root.findall("joint")}
    rev = sorted(n for n, t in joints.items() if t == "revolute")
    assert rev == ["joint%d" % i for i in range(1, 7)], rev
    assert joints["gripper_joint"] == "fixed"
    pris = sorted(n for n, t in joints.items() if t == "prismatic")
    assert pris == ["gripper_joint1", "gripper_joint2"], pris
    return 0.0


def test_tree_structure():
    """Single root (base_link), every other link has exactly one parent joint,
    all links reachable, no cycles."""
    root = _root()
    links = [l.get("name") for l in root.findall("link")]
    parent_of = {}
    children = {}
    for j in root.findall("joint"):
        c = j.find("child").get("link")
        p = j.find("parent").get("link")
        assert c not in parent_of, "link %s has two parent joints" % c
        parent_of[c] = p
        children.setdefault(p, []).append(c)
    roots = [l for l in links if l not in parent_of]
    assert roots == ["base_link"], roots
    # BFS reachability + cycle check
    seen = set()
    stack = ["base_link"]
    while stack:
        n = stack.pop()
        assert n not in seen, "cycle at %s" % n
        seen.add(n)
        stack.extend(children.get(n, []))
    assert seen == set(links), set(links) - seen
    return 0.0


def test_mesh_references():
    """Every mesh reference is a relative path (no absolute paths, no drive
    letters, no package://) and the file exists next to the URDF."""
    root = _root()
    base_dir = os.path.dirname(URDF_PATH)
    n = 0
    for m in root.iter("mesh"):
        fn = m.get("filename")
        assert fn, "mesh without filename"
        assert not os.path.isabs(fn), "absolute mesh path: %s" % fn
        assert "://" not in fn and ":" not in fn, "non-relative mesh path: %s" % fn
        assert not fn.startswith(("/", "\\")), "rooted mesh path: %s" % fn
        full = os.path.normpath(os.path.join(base_dir, fn))
        assert os.path.isfile(full), "missing mesh file: %s" % full
        n += 1
    assert n == 20, "expected 20 mesh refs (10 visual + 10 collision), got %d" % n
    return 0.0


if __name__ == "__main__":
    for fn in [test_six_revolute_joints, test_tree_structure, test_mesh_references]:
        print("%s: PASS (worst=%.3e)" % (fn.__name__, fn() or 0.0))
