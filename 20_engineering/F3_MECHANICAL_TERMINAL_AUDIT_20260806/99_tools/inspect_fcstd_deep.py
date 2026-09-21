#!/usr/bin/env python3
"""Deeper read-only FCStd inspection: link targets, label set, entry size profile.

Answers audit question 15.1 "which file and configuration IS the authoritative
top-level mechanical assembly" by measuring what each candidate actually holds.
"""
import collections
import json
import os
import re
import zipfile

SMALL = (r"F:\Space-Embodied-Robot-HAG_A_20260804\12_f3_p1_hifi_attachment"
         r"\15_f3_p3_top_assembly\SPACE_EMBODIED_ROBOT_TOP_INTEGRATION_F3P3.FCStd")
BIG = (r"F:\Space-Embodied-Robot-HAG_A_20260804\12_f3_p1_hifi_attachment"
       r"\15_f3_p3_top_assembly\F3_P3_TOP_ASSEMBLY.FCStd")

OUT = os.path.join(os.path.dirname(__file__), "..", "01_native_cad",
                   "F3_FCSTD_DEEP_INSPECTION.json")


def doc_xml(path):
    return zipfile.ZipFile(path).read("Document.xml").decode("utf-8", "replace")


def size_profile(path):
    z = zipfile.ZipFile(path)
    infos = sorted(z.infolist(), key=lambda i: -i.file_size)
    return [{"name": i.filename, "uncompressed_bytes": i.file_size} for i in infos[:10]]


def labels(xml):
    """Object Label properties, in document order."""
    return re.findall(r'<Property name="Label"[^>]*>\s*<String value="([^"]*)"', xml)


def main():
    rep = {"schema": "F3_FCSTD_DEEP_INSPECTION_V1", "documents": {}}

    # --- small / property-only candidate ---
    xs = doc_xml(SMALL)
    link_blocks = re.findall(
        r'<Object name="([^"]+)".*?</Object>', xs, flags=re.S)
    linked_docs = re.findall(r'<XLink[^>]*file="([^"]*)"', xs)
    linked_names = re.findall(r'<XLink[^>]*name="([^"]*)"', xs)
    rep["documents"]["SPACE_EMBODIED_ROBOT_TOP_INTEGRATION_F3P3"] = {
        "path": SMALL,
        "role_claimed_by_result_json": "assembly of record (components=15, states=23)",
        "brp_shape_files": 0,
        "labels": labels(xs)[:60],
        "label_count": len(labels(xs)),
        "xlink_external_files": sorted(set(linked_docs)),
        "xlink_target_names": sorted(set(linked_names))[:30],
        "largest_entries": size_profile(SMALL),
    }

    # --- big / geometry-bearing candidate ---
    xb = doc_xml(BIG)
    lb = labels(xb)
    rep["documents"]["F3_P3_TOP_ASSEMBLY"] = {
        "path": BIG,
        "brp_shape_files": len([n for n in zipfile.ZipFile(BIG).namelist()
                                if n.lower().endswith(".brp")]),
        "label_count": len(lb),
        "label_prefix_histogram": dict(
            collections.Counter(re.sub(r"\d+$", "", s) for s in lb).most_common(20)),
        "labels_sample": lb[:15],
        "largest_entries": size_profile(BIG),
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2, ensure_ascii=False)

    d = rep["documents"]["SPACE_EMBODIED_ROBOT_TOP_INTEGRATION_F3P3"]
    print("=== SMALL (registered as 'the assembly') ===")
    print("  labels(%d): %s" % (d["label_count"], d["labels"][:20]))
    print("  xlink external files: %s" % d["xlink_external_files"])
    print("  xlink target names  : %s" % d["xlink_target_names"][:12])
    print("  largest entries:")
    for e in d["largest_entries"][:5]:
        print("     %-28s %d" % (e["name"], e["uncompressed_bytes"]))

    d = rep["documents"]["F3_P3_TOP_ASSEMBLY"]
    print("\n=== BIG (holds the geometry) ===")
    print("  brp=%d  labels=%d" % (d["brp_shape_files"], d["label_count"]))
    print("  label prefixes: %s" % d["label_prefix_histogram"])
    print("  largest entries:")
    for e in d["largest_entries"][:5]:
        print("     %-28s %d" % (e["name"], e["uncompressed_bytes"]))
    print("\nwritten -> %s" % os.path.normpath(OUT))


if __name__ == "__main__":
    main()
