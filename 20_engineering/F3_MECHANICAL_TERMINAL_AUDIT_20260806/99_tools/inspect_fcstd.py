#!/usr/bin/env python3
"""Read-only FCStd inspector.

FCStd is a zip container; this reads Document.xml without launching FreeCAD and
without writing anything back. Used to establish what the F3-P3 "top assembly"
documents actually contain (geometry vs. property-only placeholders).
"""
import collections
import json
import os
import re
import sys
import zipfile

TARGETS = [
    ("SPACE_EMBODIED_ROBOT_TOP_INTEGRATION_F3P3",
     r"F:\Space-Embodied-Robot-HAG_A_20260804\12_f3_p1_hifi_attachment"
     r"\15_f3_p3_top_assembly\SPACE_EMBODIED_ROBOT_TOP_INTEGRATION_F3P3.FCStd"),
    ("F3_P3_TOP_ASSEMBLY",
     r"F:\Space-Embodied-Robot-HAG_A_20260804\12_f3_p1_hifi_attachment"
     r"\15_f3_p3_top_assembly\F3_P3_TOP_ASSEMBLY.FCStd"),
]

OUT = os.path.join(os.path.dirname(__file__), "..", "01_native_cad",
                   "F3_FCSTD_CONTENT_INSPECTION.json")


def inspect(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    brp = [n for n in names if n.lower().endswith(".brp")]
    xml = z.read("Document.xml").decode("utf-8", "replace")

    typed = re.findall(r'<Object\s+type="([^"]+)"\s+name="([^"]+)"', xml)
    listed = re.findall(r'<Object\s+name="([^"]+)"', xml)
    props = re.findall(r'<Property\s+name="([^"]+)"', xml)

    type_counts = collections.Counter(t for t, _ in typed)
    return {
        "path": path,
        "zip_entries": len(names),
        "brp_shape_files": len(brp),
        "document_xml_bytes": len(xml),
        "object_declarations": len(listed),
        "typed_objects": len(typed),
        "object_type_histogram": dict(type_counts.most_common()),
        "object_names_sample": [n for _, n in typed[:20]],
        "distinct_property_names": len(set(props)),
        "has_solid_geometry": len(brp) > 0,
    }


def main():
    report = {
        "schema": "F3_FCSTD_CONTENT_INSPECTION_V1",
        "method": "zip/Document.xml static read; FreeCAD NOT launched; zero writes to source",
        "documents": {},
    }
    for tag, path in TARGETS:
        if not os.path.isfile(path):
            report["documents"][tag] = {"status": "MISSING", "path": path}
            continue
        report["documents"][tag] = inspect(path)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    for tag, d in report["documents"].items():
        print("=== %s ===" % tag)
        if d.get("status") == "MISSING":
            print("   MISSING")
            continue
        print("   zip_entries        = %d" % d["zip_entries"])
        print("   brp_shape_files    = %d" % d["brp_shape_files"])
        print("   typed_objects      = %d" % d["typed_objects"])
        print("   has_solid_geometry = %s" % d["has_solid_geometry"])
        for t, c in list(d["object_type_histogram"].items())[:12]:
            print("      %-44s %d" % (t, c))
        print("   names[:10] = %s" % d["object_names_sample"][:10])
    print("\nwritten -> %s" % os.path.normpath(OUT))


if __name__ == "__main__":
    sys.exit(main())
