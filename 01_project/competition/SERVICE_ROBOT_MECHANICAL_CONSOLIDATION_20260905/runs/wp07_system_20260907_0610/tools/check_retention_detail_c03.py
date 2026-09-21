"""C03 comparator correction of executed C02 retention STEP measurements.

Geometry/contract/STEP unchanged. C02 456 PASS/19 INCOMPLETE remains archived.
Fixes only reserved result keys and subtraction from an empty actual Common.

No producer import and no CAD at module import. Root executes under run_guard.
--mode local checks station geometry, positive stops, actual saddle full-stroke
and conditional bench insertion paths. --mode neighbours --state STATE checks
only NEW material against every frozen assembly neighbour using AABB then BRep.
The baseline was not a globally collision-free/qualified retention mechanism.
No local PASS grants whole-mechanism, thread, force or physical release credit.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import itertools
import json
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
IDENTITY = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def aabb_overlap(a, b, tolerance=0.0):
    return all(a["min_mm"][i] <= b["max_mm"][i]+tolerance and
               b["min_mm"][i] <= a["max_mm"][i]+tolerance for i in range(3))


def expected_ids(station, c):
    return {f"hold_fold_mast_{station}", *[f"hold_shoe_guide_{station}_{int(x)}" for x in c["parameters"]["guide_axis_x_mm"]],
            *[f"WP07_guide_{kind}_{station}_{int(x)}" for kind in ("washer", "screw") for x in c["parameters"]["guide_axis_x_mm"]],
            *[f"WP07_lower_collar_{station}_{side}" for side in ("front","rear")],
            *[f"WP07_lower_{kind}_{station}_{int(x)}" for kind in ("screw","washer_outer","washer_inner","nut") for x in c["parameters"]["lower_collar_bolt_x_mm"]]}


class Audit:
    def __init__(self, receipt_path, output, mode, state=None):
        self.receipt_path = Path(receipt_path).resolve()
        self.e = read(self.receipt_path)
        self.cp = Path(self.e["contract_path"])
        self.c = read(self.cp)
        if self.c["schema"] != "WP07_RETENTION_GUIDE_END_DESIGN_V2":
            raise ValueError("Requires C02 removable-lower-collar contract")
        self.k = int(self.e["station_index"])
        self.st = self.c["stations"][str(self.k)]
        self.p, self.tol = self.c["parameters"], self.c["acceptance"]
        self.snapshots = {str(self.receipt_path): sha(self.receipt_path), str(self.cp.resolve()): sha(self.cp)}
        if self.snapshots[str(self.cp.resolve())] != self.e["contract_sha256"]:
            raise ValueError("Contract changed after emission")
        if self.p != self.e["parameters"]:
            raise ValueError("Emitted parameters differ from frozen contract")
        if set(self.e["parts"]) != expected_ids(self.k, self.c):
            raise ValueError("Replacement/addition instance set differs")
        for path, digest in self.c["source_inputs"].items():
            if sha(path) != digest:
                raise ValueError("Frozen source changed: " + path)
            self.snapshots[str(Path(path).resolve())] = digest
        if sha(self.e["producer_path"]) != self.e["producer_sha256"]:
            raise ValueError("Producer changed after emission")
        self.snapshots[str(Path(self.e["producer_path"]).resolve())] = self.e["producer_sha256"]
        for name, data in self.st["states"].items():
            if self.e["placements"][name] != data["T_S_mast"]:
                raise ValueError("Frozen mast transform not inherited: " + name)
            for row in self.e["parts"].values():
                if row["T_S_local_by_state"][name] != data["T_S_mast"]:
                    raise ValueError("Part transform not inherited: " + name)
            for instance, row in data["sources"].items():
                if row["T_S_local"] != data["T_S_mast"]:
                    raise ValueError("Source is not in assumed mast frame: " + instance)
        parts = {key: {**row, "T_S_local": IDENTITY} for key, row in self.e["parts"].items()}
        for state_name, s in self.st["states"].items():
            for key, row in s["sources"].items():
                parts[f"old:{state_name}:{key}"] = {**row, "T_S_local": IDENTITY}
        for role,row in self.c["catalogue_parts"].items():
            parts["catalogue:"+role]={**row,"T_S_local":IDENTITY}
        gmod = module(self.c["geometry_reader"], "wp07_retention_independent_geometry")
        self.g = gmod.Geometry(dict(parts=parts, tolerances=self.tol), self.snapshots)
        # Override its historical scene reader before any load: no sidecar writes
        # beside immutable source STEP files. Font guard already ran in Geometry.
        from build123d import import_step
        self.g.import_step = import_step
        self.bearing = module(self.c["bearing_reader"], "wp07_retention_independent_bearing")
        self.output = Path(output).resolve()
        self.out = dict(schema="WP07_RETENTION_DETAIL_CHECK_C03", status="RUNNING", station_index=self.k,
                        mode=mode, state=state, receipt_path=str(self.receipt_path),
                        checker_path=str(Path(__file__).resolve()), checker_sha256=sha(__file__),
                        checks=[], diagnostics=[],
                        scope="Nominal end-capture candidate only; existing retention/drive/arm/support qualification remains OPEN.",
                        physical_assembly_completed=False, structural_strength_verified=False,
                        actual_thread_verified=False, manufacturing_release=False)
        self.save()

    def save(self):
        self.out["input_sha256"] = self.snapshots
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps(self.out, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    def check(self, name, fn):
        try:
            passed, details = fn()
            details = dict(details)
            for reserved in ("id", "status"):
                if reserved in details:
                    details["measurement_" + reserved] = details.pop(reserved)
            row = dict(id=name, status="PASS" if passed else "FAIL", **details)
        except Exception as exc:
            row = dict(id=name, status="INCOMPLETE", error_type=type(exc).__name__, error=str(exc))
        self.out["checks"].append(row)
        if self.out["mode"] == "local" or len(self.out["checks"]) % 50 == 0 or row["status"] != "PASS":
            self.save()
        return row

    def finish(self):
        self.check("frozen_input_hashes_after_measurement", lambda: (
            all(sha(path) == digest for path, digest in self.snapshots.items()), dict(checked_files=len(self.snapshots))))
        statuses = [row["status"] for row in self.out["checks"]]
        self.out["status"] = "FAIL" if "FAIL" in statuses else "INCOMPLETE" if "INCOMPLETE" in statuses else "PASS"
        self.out["scope_status"] = ("LOCAL_NOMINAL_GEOMETRY_AND_CONDITIONAL_BENCH_PATHS_" if self.out["mode"] == "local"
                                    else "NEW_MATERIAL_VS_FROZEN_NEIGHBOURS_") + self.out["status"]
        self.out["completed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        self.out["counts"] = {s: statuses.count(s) for s in ("PASS", "FAIL", "INCOMPLETE")}
        self.save()
        return self.out

    def cylinder(self, d, z0, z1, x=0):
        return self.g.Solid.make_cylinder(d/2, z1-z0, self.g.Plane(origin=(x, 0, z0)))

    def box(self, x0, x1, z0, z1):
        width = self.p["ear_width_y_mm"]
        return self.g.Solid.make_box(x1-x0, width, z1-z0, self.g.Plane(origin=(x0, -width/2, z0)))

    def move(self, shape, z):
        return shape.moved(self.g.Location((0, 0, z)))

    def translate(self, shape, vector):
        return shape.moved(self.g.Location(tuple(vector)))

    def box6(self, bounds):
        a,b=bounds
        return self.g.Solid.make_box(*(b[i]-a[i] for i in range(3)),self.g.Plane(origin=tuple(a)))

    def box_cover_sweep(self,shape,boxes,vector):
        """Conservative analytic translation of boxes containing actual STEP.

        The unswept union must contain ALL actual material, not merely two poses.
        Translating each whole box then taking their union bounds every point of
        every intermediate pose. Closed guide/bolt holes may be filled only in
        the conservative cover; actual part/source equivalence remains separate.
        """
        cover=sweep=None
        for a,b in boxes:
            item=self.box6((a,b))
            cover=item if cover is None else cover+item
            sa=[a[i]+min(0,vector[i]) for i in range(3)]
            sb=[b[i]+max(0,vector[i]) for i in range(3)]
            item=self.box6((sa,sb));sweep=item if sweep is None else sweep+item
        residual=self.volume(shape-cover)
        if residual>self.tol["volume_mm3"]:
            raise ValueError(f"Actual STEP not fully contained by translation cover: {residual}")
        return sweep,dict(method="Actual STEP contained by feature-box union; exact continuous Minkowski sweep of conservative boxes",actual_outside_cover_mm3=residual,translation_mm=vector)

    def collar_boxes(self,side,lo):
        p=self.p;h=p["ear_thickness_mm"];xi=p["lower_collar_inner_x_half_mm"];xo=p["lower_collar_outer_x_half_mm"]
        yi=p["lower_collar_inner_y_half_mm"];yo=p["lower_collar_crossbar_outer_y_half_mm"];sx=p["lower_collar_side_web_outer_x_half_mm"];fy=p["lower_collar_flange_y_half_mm"]
        def bounds(xa,xb,ya,yb,za=lo,zb=lo+h):
            return ([xa,ya if side>0 else -yb,za],[xb,yb if side>0 else -ya,zb])
        result=[bounds(-sx,sx,yi,yo)]
        for sign in (-1,1):
            xa,xb=(xi,xo) if sign>0 else (-xo,-xi);result.append(bounds(xa,xb,0,fy))
            xa,xb=(xi,sx) if sign>0 else (-sx,-xi);result.append(bounds(xa,xb,0,yo))
            xa,xb=(p["key_tongue_inner_x_abs_mm"],p["key_tongue_outer_x_abs_mm"]) if sign>0 else (-p["key_tongue_outer_x_abs_mm"],-p["key_tongue_inner_x_abs_mm"])
            result.append(bounds(xa,xb,0,yi,lo+p["key_tongue_z0_above_lo_mm"],lo+p["key_tongue_z1_above_lo_mm"]))
        return result

    def cylinder_y(self,d,y0,y1,x,z):
        return self.g.Solid.make_cylinder(d/2,y1-y0,self.g.Plane(origin=(x,y0,z),z_dir=(0,1,0)))

    def volume(self, shape):
        return self.g.volume(shape)

    def clear(self, a, b, allowance=None):
        result = self.g.separation(a, b)
        if allowance is None:
            outside = result["intersection_volume_mm3"]
        else:
            common = a & b
            if common is None or not common.solids():
                # Actual Common has no material solids. Its measured zero is
                # retained; no empty-shape subtraction or tolerance relaxation.
                outside = 0.0
                result["common_material_topology"] = "NO_SOLIDS"
            else:
                outside = self.volume(common - allowance)
        result["unallowed_intersection_volume_mm3"] = outside
        if allowance is not None:
            result["allowance"] = "Only declared unqualified thread cylinder; no thread/strength credit"
        return outside <= self.tol["volume_mm3"], result

    def difference_bound(self, actual, allowed):
        vol, outside = self.volume(actual), self.volume(actual-allowed)
        return outside <= self.tol["volume_mm3"], dict(actual_difference_volume_mm3=vol, outside_declared_domain_mm3=outside)

    def top_face_sweep(self, shape, retreat):
        """Actual trimmed top face prism; endpoint containment validates prismatic assumption."""
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.GeomAbs import GeomAbs_Plane
        from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
        from OCP.gp import gp_Vec
        top = shape.bounding_box().max.Z
        faces = []
        for face in shape.faces():
            surface = BRepAdaptor_Surface(face.wrapped)
            if surface.GetType() == GeomAbs_Plane:
                pl = surface.Plane()
                if abs(abs(pl.Axis().Direction().Z())-1) < 1e-10 and abs(pl.Location().Z()-top) <= self.tol["linear_mm"]:
                    faces.append(face)
        if len(faces) != 1:
            raise ValueError("Need one actual trimmed top face for full prismatic sweep")
        distance = shape.bounding_box().size.Z + retreat
        raw = BRepPrimAPI_MakePrism(faces[0].wrapped, gp_Vec(0, 0, -distance), True).Shape()
        sweep = self.g.Solid(raw)
        if not sweep.is_valid or len(sweep.solids()) != 1:
            raise ValueError("Actual top-face full stroke prism invalid")
        residual = max(self.volume(shape-sweep), self.volume(self.move(shape, -retreat)-sweep))
        if residual > self.tol["volume_mm3"]:
            raise ValueError("Actual saddle endpoints not contained in full stroke prism")
        return sweep, dict(method="Actual STEP trimmed top face extruded through full plate+stroke", endpoint_outside_volume_mm3=residual,
                           saddle_thickness_mm=shape.bounding_box().size.Z, stroke_mm=retreat, sweep_facts=self.g.facts(sweep))

    def lower_hardware_paths(self,shapes,installed,lo,threads):
        p=self.p; k=self.k; z=lo+p["ear_thickness_mm"]/2; travel=p["m3_hardware_insertion_travel_mm"]
        # Frozen catalogue poses are independently rebuilt, never taken from
        # producer metadata. Actual STEP symmetric difference must be negligible.
        for x in p["lower_collar_bolt_x_mm"]:
            ids={role:f"WP07_lower_{role}_{k}_{int(x)}" for role in ("washer_outer","screw","washer_inner","nut")}
            for role,cat,base in (("washer_outer","washer",4.0),("screw","screw",4.5),("washer_inner","washer",-4.5),("nut","nut",-6.9)):
                actual=shapes[ids[role]]
                reference=self.g.load("catalogue:"+cat).moved(self.g.Plane(origin=(x,base,z),x_dir=(1,0,0),z_dir=(0,1,0)).location)
                def identity(actual=actual,reference=reference):
                    difference=self.volume(actual-reference)+self.volume(reference-actual)
                    return difference<=self.tol["volume_mm3"],dict(symmetric_difference_mm3=difference,reference="Actual frozen catalogue STEP, independently posed")
                self.check("catalogue_material_identity:"+ids[role],identity)
                expected={"washer_outer":[4,4.5],"screw":[-7.5,7.5],"washer_inner":[-4.5,-4],"nut":[-6.9,-4.5]}[role]
                def stack(actual=actual,expected=expected):
                    box=actual.bounding_box(); measured=[box.min.Y,box.max.Y]
                    return max(abs(a-b) for a,b in zip(measured,expected))<=self.tol["linear_mm"],dict(actual_axial_extents_mm=measured,expected_mm=expected,nominal_tip_protrusion_mm=.6,full_thread_engagement_verified=False)
                self.check("actual_lower_stack_extents:"+ids[role],stack)
                if role.startswith("washer"):
                    a,b=expected;sign=1 if role=="washer_outer" else -1
                    cage=self.cylinder_y(7,a,b,x,z)-self.cylinder_y(3.2,a-1,b+1,x,z)
                    sa=a+min(0,sign*travel);sb=b+max(0,sign*travel)
                    sweep=self.cylinder_y(7,sa,sb,x,z)-self.cylinder_y(3.2,sa-1,sb+1,x,z)
                elif role=="screw":
                    sign=1
                    cage=self.cylinder_y(3,-7.5,4.5,x,z)+self.cylinder_y(5.5,4.5,7.5,x,z)
                    sweep=self.cylinder_y(3,-7.5,4.5+travel,x,z)+self.cylinder_y(5.5,4.5,7.5+travel,x,z)
                else:
                    sign=-1
                    # Solid outer cylinder is conservative for a hex nut. Its
                    # nominal thread void is not credited as a free straight bore.
                    cage=self.cylinder_y(6.351,-6.9,-4.5,x,z)
                    sweep=self.cylinder_y(6.351,-6.9-travel,-4.5,x,z)
                self.check("actual_hardware_inside_continuous_cover:"+ids[role],lambda actual=actual,cage=cage,sign=sign:(
                    self.volume(actual-cage)<=self.tol["volume_mm3"],dict(actual_outside_cage_mm3=self.volume(actual-cage),translation_mm=[0,sign*travel,0],method="Actual catalogue STEP contained by continuously swept coaxial primitive cover")))
                for oid,obstacle in installed.items():
                    allowance=None
                    if role=="nut" and oid==ids["screw"]:
                        allowance=self.cylinder_y(3+2*self.tol["linear_mm"],-7.5-self.tol["linear_mm"],-4.5+self.tol["linear_mm"],x,z)
                    self.check(f"lower_hardware_insertion:{ids[role]}:{oid}",lambda sweep=sweep,obstacle=obstacle,allowance=allowance:self.clear(sweep,obstacle,allowance))
                installed[ids[role]]=actual
            threads[frozenset([ids["nut"],ids["screw"]])]=self.cylinder_y(3+2*self.tol["linear_mm"],-6.9-self.tol["linear_mm"],-4.5+self.tol["linear_mm"],x,z)
            front=f"WP07_lower_collar_{k}_front";rear=f"WP07_lower_collar_{k}_rear"
            for a,b,plane in ((ids["washer_outer"],front,4),(rear,ids["washer_inner"],-4),(ids["washer_inner"],ids["nut"],-4.5),(ids["screw"],ids["washer_outer"],4.5)):
                def area(a=a,b=b,plane=plane):
                    result=self.bearing.contact_area(shapes[a],shapes[b],[0,1,0],plane,self.tol["linear_mm"])
                    if result["status"]!="MEASURED":raise RuntimeError(json.dumps(result))
                    return result["contact_area_mm2"]>=self.tol["nominal_bearing_area_min_mm2"],result
                self.check(f"lower_stack_actual_bearing:{int(x)}:{a}:{b}",area)
            driver=self.cylinder_y(p["m3_driver_envelope_d_mm"],6,6+p["m3_tool_envelope_length_mm"],x,z)
            socket=self.cylinder_y(p["m3_tool_envelope_d_mm"],-4.5-p["m3_tool_envelope_length_mm"],-4.5,x,z)-self.cylinder_y(p["m3_nut_tool_inner_d_mm"],-5.5-p["m3_tool_envelope_length_mm"],-3.5,x,z)
            for name,tool in (("head_driver",driver),("nut_socket",socket)):
                for oid,obstacle in installed.items():
                    self.check(f"lower_tools_before_rods:{int(x)}:{name}:{oid}",lambda tool=tool,obstacle=obstacle:self.clear(tool,obstacle))
            self.check("lower_opposed_tools_simultaneous:"+str(int(x)),lambda:self.clear(driver,socket))
        def mating_area():
            result=self.bearing.contact_area(shapes[f"WP07_lower_collar_{k}_front"],shapes[f"WP07_lower_collar_{k}_rear"],[0,1,0],0,self.tol["linear_mm"])
            if result["status"]!="MEASURED":raise RuntimeError(json.dumps(result))
            return result["contact_area_mm2"]>=self.tol["nominal_bearing_area_min_mm2"],result
        self.check("lower_collar_actual_shared_mating_face_once",mating_area)
        self.out["m3_tool_boundary"]="Frozen WP06 nominal D2.5 driver and OD8/ID6.4 nut socket envelopes; tool handle and hand envelope not represented. Tools withdraw before rods; reverse disassembly first removes rods."

    def local(self):
        p, g, k = self.p, self.g, self.k
        hi = self.st["guide_top_local_z_mm"]; lo = hi-p["effective_guide_length_mm"]
        play = p["axial_capture_play_mm"]
        ear_z = [(lo, lo+p["ear_thickness_mm"]), (hi-play-p["ear_thickness_mm"], hi-play)]
        mast_id = f"hold_fold_mast_{k}"
        shapes = {key: g.load(key) for key in self.e["parts"]}
        mast = shapes[mast_id]
        collar_ids=[f"WP07_lower_collar_{k}_{tag}" for tag in ("front","rear")]
        collars=[shapes[key] for key in collar_ids]
        lower_support=collars[0]+collars[1]
        old_mast = g.load(f"old:parking:{mast_id}")
        saddle_id = f"hold_saddle_{k}"
        saddle = g.load(f"old:parking:{saddle_id}")
        # A single local replacement may serve three states only after actual
        # source material invariance is measured, not inferred from shared IDs.
        for state in ("service","released"):
            for key in (mast_id,*[f"hold_shoe_guide_{k}_{int(x)}" for x in p["guide_axis_x_mm"]]):
                def source_invariance(state=state,key=key):
                    a=g.load(f"old:parking:{key}");b=g.load(f"old:{state}:{key}")
                    difference=self.volume(a-b)+self.volume(b-a)
                    return difference<=self.tol["volume_mm3"],dict(symmetric_difference_mm3=difference)
                self.check(f"frozen_local_source_invariance:{state}:{key}",source_invariance)
            def frozen_saddle(state=state):
                expected=self.move(saddle,-p["saddle_travel_mm"]);actual=g.load(f"old:{state}:{saddle_id}")
                difference=self.volume(actual-expected)+self.volume(expected-actual)
                return difference<=self.tol["volume_mm3"],dict(symmetric_difference_mm3=difference,expected_local_retreat_mm=p["saddle_travel_mm"])
            self.check("frozen_state_saddle_retreat:"+state,frozen_saddle)
        for key, shape in shapes.items():
            def facts(shape=shape):
                f = g.facts(shape)
                return f["shape_valid"] and f["solid_count"] == 1 and f["volume_mm3"] > 0, f
            self.check("solid:"+key, facts)
        groove_domain=None
        for side in (-1,1):
            xa,xb=(p["key_groove_inner_x_abs_mm"],6.01) if side>0 else (-6.01,-p["key_groove_inner_x_abs_mm"])
            item=self.box6(([xa,-11,lo+p["key_groove_z0_above_lo_mm"]],[xb,11,lo+p["key_groove_z1_above_lo_mm"]]))
            groove_domain=item if groove_domain is None else groove_domain+item
        self.check("mast_removed_only_declared_key_grooves",lambda:self.difference_bound(old_mast-mast,groove_domain))
        self.check("mast_full_declared_grooves_cut",lambda:(self.volume(mast&groove_domain)<=self.tol["volume_mm3"],dict(residual_groove_material_mm3=self.volume(mast&groove_domain),remaining_nominal_X_wall_mm=1.5,strength_verified=False)))
        allowed_ears = None
        for x in p["guide_axis_x_mm"]:
            xa, xb = ((p["ear_inner_x_abs_mm"], p["ear_outer_x_abs_mm"]) if x > 0
                      else (-p["ear_outer_x_abs_mm"], -p["ear_inner_x_abs_mm"]))
            for z0, z1 in ear_z[1:]:
                ear = self.box(xa, xb, z0, z1)
                allowed_ears = ear if allowed_ears is None else allowed_ears + ear
        self.check("mast_added_material_only_ears", lambda: self.difference_bound(mast-old_mast, allowed_ears))
        self.check("mast_ears_positive_material", lambda: (self.volume(mast-old_mast) > 1, dict(added_volume_mm3=self.volume(mast-old_mast))))
        threads = {}
        installed={mast_id:mast,saddle_id:saddle}
        # First saddle insertion starts with its top below the complete pivot boss.
        def first_saddle():
            retreat=saddle.bounding_box().max.Z+20
            sweep,info=self.top_face_sweep(saddle,retreat)
            ok,measure=self.clear(sweep,mast)
            return ok,dict(**info,measurement=measure,start_saddle_top_local_z_mm=-20,
                           initial_prepositioned_saddle_assumption=False)
        self.check("first_closed_saddle_from_below_over_pivot",first_saddle)
        for side,tag in ((1,"front"),(-1,"rear")):
            key=f"WP07_lower_collar_{k}_{tag}"; shape=shapes[key]
            holder={}
            def cover(shape=shape,side=side):
                holder["sweep"],info=self.box_cover_sweep(shape,self.collar_boxes(side,lo),[0,side*p["lower_collar_insertion_travel_mm"],0])
                return True,info
            self.check("collar_actual_continuous_cover:"+tag,cover)
            for oid,obstacle in installed.items():
                self.check(f"collar_insertion:{tag}:{oid}",lambda obstacle=obstacle:self.clear(holder["sweep"],obstacle))
            installed[key]=shape
            # Geometric axial limits without assuming frictional clamp force.
            ap=p["key_axial_play_each_way_mm"];probe=self.tol["stop_probe_travel_mm"]
            for sign in (-1,1):
                self.check(f"collar_positive_key_stop:{tag}:{sign}",lambda shape=shape,sign=sign:(
                    self.volume(self.move(shape,sign*(ap+probe))&mast)>=self.tol["positive_stop_overlap_min_mm3"],
                    dict(overlap_mm3=self.volume(self.move(shape,sign*(ap+probe))&mast),attempted_motion_mm=sign*(ap+probe),friction_assumed=False)))
                plane=lo+(p["key_groove_z1_above_lo_mm"] if sign>0 else p["key_groove_z0_above_lo_mm"])
                def key_area(shape=shape,sign=sign,plane=plane):
                    result=self.bearing.contact_area(self.move(shape,sign*ap),mast,[0,0,1],plane,self.tol["linear_mm"])
                    if result["status"]!="MEASURED":raise RuntimeError(json.dumps(result))
                    return result["contact_area_mm2"]>=self.tol["nominal_bearing_area_min_mm2"],result
                self.check(f"collar_key_actual_bearing:{tag}:{sign}",key_area)
        self.lower_hardware_paths(shapes,installed,lo,threads)
        for x in p["guide_axis_x_mm"]:
            sx = str(int(x)); rod_id = f"hold_shoe_guide_{k}_{sx}"
            wi = f"WP07_guide_washer_{k}_{sx}"; si = f"WP07_guide_screw_{k}_{sx}"
            rod, washer, screw = shapes[rod_id], shapes[wi], shapes[si]
            old = g.load(f"old:parking:{rod_id}")
            head = self.cylinder(p["lower_head_d_mm"], lo-p["lower_head_h_mm"], lo, x)
            pilot = self.cylinder(p["guide_thread_pilot_d_mm"], hi-p["guide_thread_pilot_depth_mm"], hi+1, x)
            self.check("guide_removed_only_pilot:"+sx, lambda old=old, rod=rod, pilot=pilot: self.difference_bound(old-rod, pilot))
            self.check("guide_added_only_head:"+sx, lambda old=old, rod=rod, head=head: self.difference_bound(rod-old, head))
            self.check("guide_head_complete:"+sx, lambda rod=rod, head=head: (self.volume(head-rod) <= self.tol["volume_mm3"], dict(missing_head_material_mm3=self.volume(head-rod))))
            # Real guide material centreline intervals prove endpoints/pilot depth.
            def guide_interval(rod=rod, x=x):
                result = g.line_intervals(rod, dict(point=[x, 0, 0], dir=[0, 0, 1]))
                values = result["material_intervals_mm"]
                expected = [[lo-p["lower_head_h_mm"], hi-p["guide_thread_pilot_depth_mm"]]]
                ok = len(values) == 1 and max(abs(a-b) for a,b in zip(values[0], expected[0])) <= self.tol["linear_mm"]
                return ok, dict(measurement=result, expected_intervals_mm=expected)
            self.check("guide_axis_actual_intervals:"+sx, guide_interval)
            for i, (z0, z1) in enumerate(ear_z):
                probe = self.cylinder(p["guide_clearance_hole_d_mm"]-2*self.tol["linear_mm"], z0, z1, x)
                support=lower_support if i==0 else mast
                self.check(f"ear_actual_through_bore:{sx}:{i}", lambda probe=probe,support=support: self.clear(probe, support))
            def bearing(a, b, z):
                result = self.bearing.contact_area(a, b, [0, 0, 1], z, self.tol["linear_mm"])
                if result["status"] != "MEASURED":
                    raise RuntimeError("Bearing measurement incomplete: " + json.dumps(result))
                return result["contact_area_mm2"] >= self.tol["nominal_bearing_area_min_mm2"], result
            self.check("lower_head_actual_bearing:"+sx, lambda rod=rod: bearing(rod, lower_support, lo))
            self.check("top_washer_actual_stop_bearing:"+sx, lambda washer=washer: bearing(self.move(washer, -play), mast, hi-play))
            dz = self.tol["stop_probe_travel_mm"]
            self.check("positive_Z_head_stop:"+sx, lambda rod=rod: (
                self.volume(self.move(rod, dz)&lower_support) >= self.tol["positive_stop_overlap_min_mm3"],
                dict(overlap_mm3=self.volume(self.move(rod, dz)&lower_support), attempted_motion_mm=dz,
                     condition="At collar nominal position; collar keys separately bound +/-0.1 axial float")))
            self.check("negative_Z_washer_stop:"+sx, lambda washer=washer: (
                self.volume(self.move(washer, -play-dz)&mast) >= self.tol["positive_stop_overlap_min_mm3"],
                dict(overlap_mm3=self.volume(self.move(washer, -play-dz)&mast), attempted_motion_mm=-play-dz,
                     condition="Screw/washer remain coupled to rod; thread holding not evaluated")))
            tip = hi+p["retaining_washer_h_mm"]-p["retaining_screw_underhead_length_mm"]
            thread = self.cylinder(p["retaining_screw_shank_d_mm"]+2*self.tol["linear_mm"], tip-self.tol["linear_mm"], hi+self.tol["linear_mm"], x)
            threads[frozenset([rod_id, si])] = thread
            # Swept cylinders are conservative outer envelopes, not sparse poses.
            travel = p["rod_insertion_travel_mm"]
            rod_sweep = self.cylinder(p["guide_d_mm"], lo-travel, hi, x) + self.cylinder(p["lower_head_d_mm"], lo-p["lower_head_h_mm"]-travel, lo, x)
            for obstacle_id, obstacle in installed.items():
                self.check(f"bench_rod_from_below:{sx}:{obstacle_id}", lambda a=rod_sweep,b=obstacle: self.clear(a,b))
            installed[rod_id]=rod
            travel = p["retainer_insertion_travel_mm"]
            washer_sweep = self.cylinder(p["retaining_washer_od_mm"], hi, hi+p["retaining_washer_h_mm"]+travel, x) - self.cylinder(p["retaining_washer_id_mm"], hi-1, hi+p["retaining_washer_h_mm"]+travel+1, x)
            for obstacle_id, obstacle in installed.items():
                self.check(f"bench_washer_from_above:{sx}:{obstacle_id}", lambda a=washer_sweep,b=obstacle: self.clear(a,b))
            installed[wi]=washer
            uh=hi+p["retaining_washer_h_mm"]; ht=uh+p["retaining_screw_head_h_mm"]
            screw_sweep=self.cylinder(p["retaining_screw_shank_d_mm"],tip,uh+travel,x)+self.cylinder(p["retaining_screw_head_d_mm"],uh,ht+travel,x)
            for obstacle_id,obstacle in installed.items():
                allowance=thread if obstacle_id==rod_id else None
                self.check(f"bench_screw_from_above:{sx}:{obstacle_id}",lambda a=screw_sweep,b=obstacle,allowance=allowance:self.clear(a,b,allowance))
            installed[si]=screw
            driver=self.cylinder(p["driver_envelope_d_mm"],ht-p["retaining_screw_socket_depth_mm"],ht+p["driver_envelope_length_mm"]+travel,x)
            for obstacle_id,obstacle in installed.items():
                self.check(f"bench_round_driver_envelope:{sx}:{obstacle_id}",lambda a=driver,b=obstacle:self.clear(a,b))
        for (a, ashape),(b,bshape) in itertools.combinations(shapes.items(),2):
            allowance=threads.get(frozenset([a,b]))
            self.check(f"final_pair:{a}:{b}",lambda a=ashape,b=bshape,allowance=allowance:self.clear(a,b,allowance))
        holder={}
        def saddle_sweep():
            holder["shape"], info=self.top_face_sweep(saddle,p["saddle_travel_mm"])
            return True, info
        self.check("actual_saddle_full_stroke_prism",saddle_sweep)
        for key,shape in shapes.items():
            self.check("saddle_full80_vs:"+key,lambda shape=shape:self.clear(holder["shape"],shape))
        self.out["conditional_bench_sequence"] = self.c["installation_sequence"]
        self.out["bench_boundary"] = "Initial closed saddle sweep includes bare mast and pivot boss. Each insertion uses all earlier local pieces in stated order; M3 tools leave before rods. Rigid sweeps also bound inverse extraction order. Cap/foot/pivot pin/drive/ancillaries absent; external fixture unmodeled. M2 driver is round envelope, not chosen bit."
        self.out["length_definitions"]=self.c["length_definitions"]
        self.out["whole_assembly_neighbour_check"] = "Separate --mode neighbours --state for all 3 states plus changed-WP07-neighbour integration required"

    def neighbours(self,state):
        if state not in self.st["states"]:
            raise ValueError("Unknown state")
        manifest=read(self.c["source_manifest"])
        source_parts={row["part_key"]:row for row in manifest["parts"]}
        instances=manifest["states"][state]["instances"]
        if len(instances)!=585 or len({r["id"] for r in instances})!=585:
            raise ValueError("Expected frozen 585 unique original instances")
        # AABB metadata is credited only while the corresponding original STEP
        # bytes remain frozen, even for neighbours that need no kernel load.
        for row in instances:
            source=source_parts[row["part_key"]]
            path=str(Path(source["path"]).resolve())
            if path not in self.snapshots:
                digest=sha(path)
                if digest != source["sha256"]:
                    raise ValueError("Neighbour STEP changed: " + row["id"])
                self.snapshots[path]=digest
        T=self.st["states"][state]["T_S_mast"]
        for key in self.e["parts"]:
            shape=self.g.load(key)
            source_key=f"old:{state}:{key}"
            if source_key in self.g.job["parts"]:
                delta=shape-self.g.load(source_key)
            else:
                delta=shape
            if self.volume(delta)<=self.tol["volume_mm3"]:
                self.check("positive_new_material:"+key,lambda:(False,dict(reason="No added material")))
                continue
            delta=delta.moved(self.g.location(T))
            box=self.g.facts(delta)["bbox_mm"]
            for row in instances:
                # Same-station replacements are covered by all-pair local checks;
                # other station remains a real original neighbour in this check.
                if row["id"] in self.e["parts"]:
                    continue
                name=f"delta_neighbour:{state}:{key}:{row['id']}"
                def pair(row=row,delta=delta,box=box):
                    if not aabb_overlap(box,row["bounds_mm"],self.tol["linear_mm"]):
                        return True,dict(method="Conservative world AABB separation",neighbour_role=row.get("representation_role"),neighbour_source_sha256=source_parts[row["part_key"]]["sha256"])
                    idx=f"world:{state}:{row['id']}"
                    self.g.job["parts"][idx]={**source_parts[row["part_key"]],"T_S_local":row["T_S_local"]}
                    ok, info=self.clear(delta,self.g.load(idx))
                    info.update(method="Actual new-material delta BRep vs actual frozen neighbour BRep",neighbour_role=row.get("representation_role"))
                    return ok,info
                self.check(name,pair)
        self.out["coverage"] = dict(frozen_state=state,frozen_instance_count=585,
            changed_other_wp07_modules="Not represented by frozen WP05 source. Integration checker must use actual WP07 replacements/additions.",
            baseline_existing_collisions="No closure credit; this run only prohibits additional material collisions")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--station",type=int,choices=(0,1),required=True)
    p.add_argument("--receipt",type=Path)
    p.add_argument("--output",type=Path)
    p.add_argument("--mode",choices=("local","neighbours"),default="local")
    p.add_argument("--state",choices=("service","parking","released"))
    args=p.parse_args()
    if args.mode=="neighbours" and not args.state:
        p.error("--mode neighbours requires --state")
    receipt=args.receipt or RUN/f"results/retention_detail/station_{args.station}/EMISSION_RECEIPT.json"
    suffix=args.mode+("_"+args.state if args.state else "")
    output=args.output or RUN/f"results/retention_detail_c03/station_{args.station}/CHECK_{suffix}.json"
    archive = RUN / "inputs/history/C02_run0/ARCHIVE_MANIFEST.json"
    archive_sha = "91b82c6d3aca64bb5a425cc3eb1a1973cb3b29c5c26d58af33714c1dcde2a37e"
    if sha(archive) != archive_sha:
        raise ValueError("Executed C02 evidence archive manifest changed")
    archive_data = read(archive)
    for row in archive_data["files"]:
        if sha(row["archive_path"]) != row["sha256"]:
            raise ValueError("Executed C02 archived evidence changed: " + row["archive_path"])
    audit=Audit(receipt,output,args.mode,args.state)
    audit.snapshots[str(archive.resolve())] = archive_sha
    for row in archive_data["files"]:
        audit.snapshots[str(Path(row["archive_path"]).resolve())] = row["sha256"]
    audit.out["correction_lineage"] = dict(
        version="C03_COMPARATOR_ONLY", original_geometry_generator_changed=False,
        original_geometry_contract_changed=False, original_STEP_regenerated=False,
        executed_C02_archive_path=str(archive), executed_C02_archive_sha256=archive_sha,
        C02_station0_counts=archive_data["counts"],
        changes=["Preserve returned measurement status under measurement_status without keyword collision",
                 "Actual Common without solids has measured zero material; skip invalid empty subtraction"],
        original_C02_INCOMPLETE_preserved=True,
        note="C03 reruns actual measurements; prior missing bearing results are not inferred or promoted")
    audit.save()
    if audit.k != args.station:
        raise ValueError("Station differs from receipt")
    if args.mode=="local":audit.local()
    else:audit.neighbours(args.state)
    result=audit.finish()
    print(json.dumps(dict(status=result["status"],counts=result["counts"],output=str(output))))
    return 0 if result["status"]=="PASS" else 2


if __name__=="__main__":
    raise SystemExit(main())
