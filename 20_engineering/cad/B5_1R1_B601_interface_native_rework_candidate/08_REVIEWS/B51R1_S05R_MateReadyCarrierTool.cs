using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static class B51R1S05RMateReadyCarrierTool
{
    private const int PartType = 1;
    private const int OpenSilent = 1;
    private const int OpenReadOnly = 2;
    private const int CoincidentConstraint = 4;
    private const double Length = 0.02;
    private const double DirectionTolerance = 1.0e-9;
    private const double PositionTolerance = 1.0e-8;
    private const string UrdfSha = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164";

    private static readonly string[,] Properties =
    {
        {"MODEL_ROLE", "KINEMATIC_CARRIER"},
        {"DYNAMIC_AUTHORITY", "ACCEPTED_URDF"},
        {"CAD_MASS_CONTRIBUTION", "ZERO"},
        {"BOM_EXCLUDE", "TRUE"},
        {"SOURCE_URDF_SHA256", UrdfSha}
    };

    private sealed class Frame
    {
        internal string Joint;
        internal double X, Y, Z, Rx, Ry, Rz;
        internal Frame(string joint, double x, double y, double z,
            double rx, double ry, double rz)
        {
            Joint = joint; X = x; Y = y; Z = z;
            Rx = rx; Ry = ry; Rz = rz;
        }
    }

    private sealed class ParentDatum
    {
        internal Frame Frame;
        internal double[] AxisLocal;
        internal bool Fixed;
    }

    private sealed class CarrierSpec
    {
        internal string Link;
        internal string SourceFile;
        internal string OutputFile;
        internal string IncomingJoint;
        internal double[] IncomingAxis;
        internal bool FixedIncoming;
        internal bool Root;
        internal int CoordinateSystemCount;
        internal List<ParentDatum> Outgoing = new List<ParentDatum>();
        internal bool MovingIncoming { get { return IncomingJoint != null && !FixedIncoming; } }
    }

    private sealed class DatumSketch
    {
        internal SketchSegment AxisLine;
        internal SketchPoint[] SeatPoints;
        internal SketchPoint[] ZeroPoints;
        internal Feature SketchFeature;
    }

    private static Frame F(string joint, double x, double y, double z,
        double rx, double ry, double rz)
    {
        return new Frame(joint, x, y, z, rx, ry, rz);
    }

    private static ParentDatum Moving(Frame frame, double x, double y, double z)
    {
        return new ParentDatum { Frame = frame, AxisLocal = new[] { x, y, z }, Fixed = false };
    }

    private static ParentDatum Fixed(Frame frame)
    {
        return new ParentDatum { Frame = frame, Fixed = true };
    }

    private static CarrierSpec S(string link, string incoming, double[] axis,
        bool fixedIncoming, bool root, int csCount, params ParentDatum[] outgoing)
    {
        var spec = new CarrierSpec
        {
            Link = link,
            SourceFile = "B51R1_CARRIER_" + link + ".SLDPRT",
            OutputFile = "B51R1_CARRIER_MR1_" + link + ".SLDPRT",
            IncomingJoint = incoming,
            IncomingAxis = axis,
            FixedIncoming = fixedIncoming,
            Root = root,
            CoordinateSystemCount = csCount
        };
        spec.Outgoing.AddRange(outgoing);
        return spec;
    }

    private static List<CarrierSpec> AllSpecs()
    {
        return new List<CarrierSpec>
        {
            S("base_link", null, null, false, true, 3,
                Moving(F("joint1", -8.416e-5, 0, 0.08465, 0, 0, 0), 0, 0, 1)),
            S("link1", "joint1", new[] {0.0,0.0,1.0}, false, false, 4,
                Moving(F("joint2", 0.020084, 0.031625, 0.05555, -1.5708, 0, 0), 0, 0, -1)),
            S("link2", "joint2", new[] {0.0,0.0,-1.0}, false, false, 4,
                Moving(F("joint3", -0.264, 0, 0, 0, 0, 0), 0, 0, 1)),
            S("link3", "joint3", new[] {0.0,0.0,1.0}, false, false, 4,
                Moving(F("joint4", 0.2426, -0.054, -0.001625, 0, 0, 0), 0, 0, 1)),
            S("link4", "joint4", new[] {0.0,0.0,1.0}, false, false, 4,
                Moving(F("joint5", 0.078308, -0.0375, -0.03, -1.5708, 0, 0), 0, 0, 1)),
            S("link5", "joint5", new[] {0.0,0.0,1.0}, false, false, 4,
                Moving(F("joint6", 0.023692, 0, 0.04, 0, 1.5708, 0), 0, 0, 1)),
            S("link6", "joint6", new[] {0.0,0.0,1.0}, false, false, 4,
                Fixed(F("gripper_joint", 0, 0, 0.15971, 0, -1.5708, 0))),
            S("gripper_link", "gripper_joint", null, true, false, 5,
                Moving(F("gripper_joint1", -0.042091, 2.7531e-5, -1.3031e-5, 0, 0, -1.5708), 1, 0, 0),
                Moving(F("gripper_joint2", -0.042091, -2.7531e-5, 1.3031e-5, 0, 0, 1.5708), 1, 0, 0)),
            S("gripper_left", "gripper_joint1", new[] {1.0,0.0,0.0}, false, false, 3),
            S("gripper_right", "gripper_joint2", new[] {1.0,0.0,0.0}, false, false, 3)
        };
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static void ReleaseCom(object value)
    {
        if (value == null || !Marshal.IsComObject(value)) return;
        try { Marshal.FinalReleaseComObject(value); } catch { }
    }

    private static string Sha256(string path)
    {
        using (FileStream stream = File.OpenRead(path))
        using (SHA256 digest = SHA256.Create())
            return BitConverter.ToString(digest.ComputeHash(stream)).Replace("-", "");
    }

    private static void WriteJsonCreateNew(string path, Dictionary<string, object> data)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        using (FileStream stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
        using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false)))
            writer.Write(new JavaScriptSerializer { MaxJsonLength = Int32.MaxValue }.Serialize(data));
    }

    private static void ProgressCreateNew(string path, string line)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        using (FileStream stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
        using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false)))
            writer.WriteLine(line);
    }

    private static void Progress(string path, string line)
    {
        using (FileStream stream = new FileStream(path, FileMode.Append, FileAccess.Write, FileShare.Read))
        using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false)))
            writer.WriteLine(line);
    }

    private static SldWorks Attach(int expectedProcessId)
    {
        SldWorks app = (SldWorks)Marshal.GetActiveObject("SldWorks.Application");
        Require(app.GetProcessID() == expectedProcessId, "ROT PID mismatch");
        Require(app.Visible && app.StartupProcessCompleted, "SOLIDWORKS is not ready");
        Require(app.GetDocumentCount() == 0 && app.ActiveDoc == null, "Session is not empty");
        return app;
    }

    private static Feature[] TopLevelFeatures(ModelDoc2 model)
    {
        Array values = model.FeatureManager.GetFeatures(true) as Array;
        if (values == null) return new Feature[0];
        var result = new List<Feature>();
        foreach (object value in values)
        {
            Feature feature = value as Feature;
            if (feature != null) result.Add(feature);
        }
        return result.ToArray();
    }

    private static Feature FindUniqueFeature(ModelDoc2 model, string name, string type)
    {
        Feature[] features = TopLevelFeatures(model);
        Feature match = null;
        int count = 0;
        try
        {
            foreach (Feature feature in features)
            {
                if (feature.Name == name && feature.GetTypeName2() == type)
                {
                    count++;
                    if (match == null) match = feature;
                    else ReleaseCom(feature);
                }
                else ReleaseCom(feature);
            }
            Require(count == 1 && match != null,
                "Expected one " + type + " feature named " + name + "; count=" + count);
            return match;
        }
        catch { ReleaseCom(match); throw; }
    }

    private static int FeatureTypeCount(ModelDoc2 model, string type)
    {
        int count = 0;
        Feature[] features = TopLevelFeatures(model);
        try { foreach (Feature feature in features) if (feature.GetTypeName2() == type) count++; }
        finally { foreach (Feature feature in features) ReleaseCom(feature); }
        return count;
    }

    private static int FeatureCount(ModelDoc2 model)
    {
        Feature[] features = TopLevelFeatures(model);
        try { return features.Length; }
        finally { foreach (Feature feature in features) ReleaseCom(feature); }
    }

    private static HashSet<string> FeatureKeys(ModelDoc2 model)
    {
        var result = new HashSet<string>(StringComparer.Ordinal);
        Feature[] features = TopLevelFeatures(model);
        try
        {
            foreach (Feature feature in features)
                result.Add(feature.GetTypeName2() + "|" + feature.Name);
            return result;
        }
        finally { foreach (Feature feature in features) ReleaseCom(feature); }
    }

    private static Feature FindNewFeature(ModelDoc2 model, HashSet<string> before, string expectedType)
    {
        Feature[] features = TopLevelFeatures(model);
        Feature match = null;
        int count = 0;
        try
        {
            foreach (Feature feature in features)
            {
                string key = feature.GetTypeName2() + "|" + feature.Name;
                if (!before.Contains(key) && feature.GetTypeName2() == expectedType)
                {
                    count++;
                    if (match == null) match = feature;
                    else ReleaseCom(feature);
                }
                else ReleaseCom(feature);
            }
            Require(count == 1 && match != null,
                "Expected exactly one new " + expectedType + " feature; count=" + count);
            return match;
        }
        catch { ReleaseCom(match); throw; }
    }

    private static double[] ToArray(object raw, int expectedLength)
    {
        Array input = raw as Array;
        Require(input != null && input.Length == expectedLength,
            "Expected array length " + expectedLength);
        double[] result = new double[expectedLength];
        int i = 0;
        foreach (object value in input) result[i++] = Convert.ToDouble(value);
        return result;
    }

    private static double[] Unit(int index)
    {
        double[] value = {0,0,0}; value[index] = 1; return value;
    }

    private static int AxisIndex(double[] axis)
    {
        for (int i = 0; i < 3; i++) if (Math.Abs(axis[i]) > 0.5) return i;
        throw new InvalidOperationException("Joint axis is not canonical");
    }

    private static double[] Apply(Frame f, double[] v)
    {
        double sx = Math.Sin(f.Rx), cx = Math.Cos(f.Rx);
        double sy = Math.Sin(f.Ry), cy = Math.Cos(f.Ry);
        double sz = Math.Sin(f.Rz), cz = Math.Cos(f.Rz);
        return new[]
        {
            cy*cz*v[0] + (sx*sy*cz-cx*sz)*v[1] + (cx*sy*cz+sx*sz)*v[2],
            cy*sz*v[0] + (sx*sy*sz+cx*cz)*v[1] + (cx*sy*sz-sx*cz)*v[2],
            -sy*v[0] + sx*cy*v[1] + cx*cy*v[2]
        };
    }

    private static double[] Add(Frame f, double[] direction, double scale)
    {
        return new[] {f.X + direction[0]*scale, f.Y + direction[1]*scale, f.Z + direction[2]*scale};
    }

    private static double Dot(double[] a, double[] b)
    {
        return a[0]*b[0] + a[1]*b[1] + a[2]*b[2];
    }

    private static double Norm(double[] a)
    {
        return Math.Sqrt(Dot(a,a));
    }

    private static int[] PlaneSpan(int normalIndex)
    {
        if (normalIndex == 0) return new[] {1,2};
        if (normalIndex == 1) return new[] {0,2};
        return new[] {0,1};
    }

    private static void RequireFrameMatchesCoordinateSystem(ModelDoc2 model, Frame frame)
    {
        ModelDocExtension extension = null;
        MathTransform transform = null;
        try
        {
            extension = model.Extension;
            transform = extension.GetCoordinateSystemTransformByName(
                "CS_JOINT_" + frame.Joint + "_PARENT_SIDE");
            Require(transform != null, "Parent-side coordinate system unavailable: " + frame.Joint);
            double[] raw = ToArray(transform.ArrayData, 16);
            double[] ex = Apply(frame, Unit(0));
            double[] ey = Apply(frame, Unit(1));
            double[] ez = Apply(frame, Unit(2));
            double[] expected =
            {
                ex[0],ex[1],ex[2],ey[0],ey[1],ey[2],ez[0],ez[1],ez[2],
                frame.X,frame.Y,frame.Z,1,0,0,0
            };
            double error = 0;
            for (int i=0;i<16;i++) error = Math.Max(error,Math.Abs(raw[i]-expected[i]));
            Require(error <= 1.0e-12,
                frame.Joint + " RPY basis does not match protected coordinate-system transform; error=" + error);
        }
        finally { ReleaseCom(transform); ReleaseCom(extension); }
    }

    private static void RenamePlaneForNormalAxis(ModelDoc2 model, int normalAxis, string targetName)
    {
        Feature[] features = TopLevelFeatures(model);
        Feature match = null;
        int count = 0;
        try
        {
            foreach (Feature feature in features)
            {
                if (feature.GetTypeName2() != "RefPlane") { ReleaseCom(feature); continue; }
                RefPlane plane = null;
                MathTransform transform = null;
                bool keep = false;
                try
                {
                    plane = feature.GetSpecificFeature2() as RefPlane;
                    Require(plane != null, "IRefPlane unavailable while locating default plane");
                    transform = plane.Transform;
                    double[] raw = ToArray(transform.ArrayData, 16);
                    double[] normal = {raw[6],raw[7],raw[8]};
                    double alignment = Math.Abs(normal[normalAxis] / Norm(normal));
                    if (alignment >= 1.0 - DirectionTolerance)
                    {
                        count++;
                        if (match == null) { match = feature; keep = true; }
                    }
                }
                finally
                {
                    ReleaseCom(transform); ReleaseCom(plane);
                    if (!keep) ReleaseCom(feature);
                }
            }
            Require(count == 1 && match != null,
                "Could not identify unique default plane for normal axis " + normalAxis);
            match.Name = targetName;
        }
        finally { ReleaseCom(match); }
    }

    private static SketchPoint[] CreatePlanePoints(SketchManager manager, Frame f, int normalIndex)
    {
        int[] span = PlaneSpan(normalIndex);
        double[] u = Apply(f, Unit(span[0]));
        double[] v = Apply(f, Unit(span[1]));
        SketchPoint p0 = manager.CreatePoint(f.X, f.Y, f.Z);
        double[] p1v = Add(f, u, Length), p2v = Add(f, v, Length);
        SketchPoint p1 = manager.CreatePoint(p1v[0], p1v[1], p1v[2]);
        SketchPoint p2 = manager.CreatePoint(p2v[0], p2v[1], p2v[2]);
        Require(p0 != null && p1 != null && p2 != null, "3D datum plane point creation failed");
        return new[] {p0,p1,p2};
    }

    private static DatumSketch CreateMovingDatumSketch(ModelDoc2 model, ParentDatum datum)
    {
        Frame f = datum.Frame;
        int axisIndex = AxisIndex(datum.AxisLocal);
        int seatNormal = axisIndex;
        int zeroNormal = axisIndex == 0 ? 2 : (axisIndex == 1 ? 0 : 1);
        double[] axis = Apply(f, datum.AxisLocal);
        double[] end = Add(f, axis, Length);
        SketchManager manager = model.SketchManager;
        bool oldAdd = manager.AddToDB, oldDisplay = manager.DisplayWhenAdded;
        var result = new DatumSketch();
        HashSet<string> before = FeatureKeys(model);
        try
        {
            manager.AddToDB = true; manager.DisplayWhenAdded = false;
            manager.Insert3DSketch(true);
            result.AxisLine = manager.CreateLine(f.X, f.Y, f.Z, end[0], end[1], end[2]);
            result.SeatPoints = CreatePlanePoints(manager, f, seatNormal);
            result.ZeroPoints = CreatePlanePoints(manager, f, zeroNormal);
            manager.Insert3DSketch(true);
            Require(result.AxisLine != null, "3D datum axis line creation failed");
            result.SketchFeature = FindNewFeature(model, before, "3DProfileFeature");
            result.SketchFeature.Name = "SK3D_DATUM_" + f.Joint + "_PARENT_SIDE";
            return result;
        }
        catch
        {
            try { if (manager.ActiveSketch != null) manager.Insert3DSketch(true); } catch { }
            throw;
        }
        finally { manager.AddToDB = oldAdd; manager.DisplayWhenAdded = oldDisplay; ReleaseCom(manager); }
    }

    private static SketchPoint[][] CreateFixedDatumSketch(ModelDoc2 model, Frame f, out Feature sketchFeature)
    {
        SketchManager manager = model.SketchManager;
        bool oldAdd = manager.AddToDB, oldDisplay = manager.DisplayWhenAdded;
        HashSet<string> before = FeatureKeys(model);
        try
        {
            manager.AddToDB = true; manager.DisplayWhenAdded = false;
            manager.Insert3DSketch(true);
            SketchPoint[][] points =
            {
                CreatePlanePoints(manager, f, 0),
                CreatePlanePoints(manager, f, 1),
                CreatePlanePoints(manager, f, 2)
            };
            manager.Insert3DSketch(true);
            sketchFeature = FindNewFeature(model, before, "3DProfileFeature");
            sketchFeature.Name = "SK3D_DATUM_" + f.Joint + "_PARENT_SIDE";
            return points;
        }
        catch
        {
            try { if (manager.ActiveSketch != null) manager.Insert3DSketch(true); } catch { }
            throw;
        }
        finally { manager.AddToDB = oldAdd; manager.DisplayWhenAdded = oldDisplay; ReleaseCom(manager); }
    }

    private static Feature InsertAxis(ModelDoc2 model, SketchSegment line, string name)
    {
        HashSet<string> before = FeatureKeys(model);
        model.ClearSelection2(true);
        Require(line.Select2(false, 0), "Datum axis line selection failed: " + name);
        Require(model.InsertAxis2(true), "InsertAxis2 failed: " + name);
        model.ClearSelection2(true);
        Feature feature = FindNewFeature(model, before, "RefAxis");
        feature.Name = name;
        return feature;
    }

    private static Feature InsertPlane(ModelDoc2 model, SketchPoint[] points, string name)
    {
        Require(points != null && points.Length == 3, "Three points are required for " + name);
        HashSet<string> before = FeatureKeys(model);
        model.ClearSelection2(true);
        Require(points[0].Select2(false, 0), "First plane point selection failed: " + name);
        Require(points[1].Select2(true, 1), "Second plane point selection failed: " + name);
        Require(points[2].Select2(true, 2), "Third plane point selection failed: " + name);
        object created = model.FeatureManager.InsertRefPlane(
            CoincidentConstraint, 0, CoincidentConstraint, 0, CoincidentConstraint, 0);
        Require(created != null, "InsertRefPlane failed: " + name);
        ReleaseCom(created);
        model.ClearSelection2(true);
        Feature feature = FindNewFeature(model, before, "RefPlane");
        feature.Name = name;
        return feature;
    }

    private static void ReleasePoints(SketchPoint[] points)
    {
        if (points == null) return;
        foreach (SketchPoint point in points) ReleaseCom(point);
    }

    private static void AddMovingParentDatum(ModelDoc2 model, ParentDatum datum)
    {
        DatumSketch sketch = null;
        Feature axis = null, seat = null, zero = null;
        try
        {
            sketch = CreateMovingDatumSketch(model, datum);
            string joint = datum.Frame.Joint;
            axis = InsertAxis(model, sketch.AxisLine, "AXIS_" + joint + "_PARENT_SIDE");
            seat = InsertPlane(model, sketch.SeatPoints, "PLANE_SEAT_" + joint + "_PARENT_SIDE");
            zero = InsertPlane(model, sketch.ZeroPoints, "PLANE_ZERO_" + joint + "_PARENT_SIDE");
        }
        finally
        {
            ReleaseCom(zero); ReleaseCom(seat); ReleaseCom(axis);
            if (sketch != null)
            {
                ReleasePoints(sketch.ZeroPoints); ReleasePoints(sketch.SeatPoints);
                ReleaseCom(sketch.AxisLine); ReleaseCom(sketch.SketchFeature);
            }
        }
    }

    private static void AddFixedParentDatum(ModelDoc2 model, ParentDatum datum)
    {
        Feature sketch = null;
        SketchPoint[][] points = null;
        var created = new List<Feature>();
        try
        {
            points = CreateFixedDatumSketch(model, datum.Frame, out sketch);
            string[] axes = {"X","Y","Z"};
            for (int i = 0; i < 3; i++)
                created.Add(InsertPlane(model, points[i], "GFIX_PLN_" + axes[i] + "_PARENT_SIDE"));
        }
        finally
        {
            foreach (Feature feature in created) ReleaseCom(feature);
            if (points != null) foreach (SketchPoint[] group in points) ReleasePoints(group);
            ReleaseCom(sketch);
        }
    }

    private static void AddRecoveryReferences(ModelDoc2 model, CarrierSpec spec)
    {
        if (spec.Root)
        {
            RenamePlaneForNormalAxis(model, 0, "ROOT_PLN_X");
            RenamePlaneForNormalAxis(model, 1, "ROOT_PLN_Y");
            RenamePlaneForNormalAxis(model, 2, "ROOT_PLN_Z");
        }
        if (spec.MovingIncoming)
            RenamePlaneForNormalAxis(model, AxisIndex(spec.IncomingAxis),
                "PLANE_SEAT_" + spec.IncomingJoint + "_CHILD_SIDE");
        foreach (ParentDatum datum in spec.Outgoing)
        {
            RequireFrameMatchesCoordinateSystem(model, datum.Frame);
            if (datum.Fixed) AddFixedParentDatum(model, datum);
            else AddMovingParentDatum(model, datum);
        }
    }

    private static int BodyCount(ModelDoc2 model)
    {
        Array bodies = ((PartDoc)model).GetBodies2(-1, false) as Array;
        if (bodies == null) return 0;
        try { return bodies.Length; }
        finally { foreach (object body in bodies) ReleaseCom(body); }
    }

    private static Dictionary<string, object> ReadNoBodyMassEvidence(ModelDoc2 model)
    {
        ModelDocExtension extension = null;
        try
        {
            extension = model.Extension;
            int status;
            Array values = extension.GetMassProperties2(2, out status, false) as Array;
            Require(status == 2, "Expected swMassPropertiesStatus_NoBody=2; observed " + status);
            return new Dictionary<string, object>
            {
                {"api", "IModelDocExtension.GetMassProperties2"}, {"status", status},
                {"returned_value_count", values == null ? 0 : values.Length}, {"cad_mass_kg", 0.0}
            };
        }
        finally { ReleaseCom(extension); }
    }

    private static List<Dictionary<string, object>> ReadProperties(ModelDoc2 model)
    {
        ModelDocExtension extension = null;
        CustomPropertyManager manager = null;
        var result = new List<Dictionary<string, object>>();
        try
        {
            extension = model.Extension;
            manager = extension.get_CustomPropertyManager("");
            for (int i = 0; i < Properties.GetLength(0); i++)
            {
                string raw, resolved; bool wasResolved, linked;
                int get = manager.Get6(Properties[i,0], false, out raw, out resolved, out wasResolved, out linked);
                int type = manager.GetType2(Properties[i,0]);
                Require(get != 0 && type == 30 && raw == Properties[i,1] && resolved == Properties[i,1],
                    "Document property mismatch: " + Properties[i,0]);
                result.Add(new Dictionary<string, object>
                {
                    {"name", Properties[i,0]}, {"raw", raw}, {"resolved", resolved}, {"type", type}
                });
            }
            return result;
        }
        finally { ReleaseCom(manager); ReleaseCom(extension); }
    }

    private static Dictionary<string, object> InspectAxis(ModelDoc2 model, string name,
        double[] expectedPoint, double[] expectedDirection)
    {
        Feature feature = null; RefAxis axis = null;
        try
        {
            feature = FindUniqueFeature(model, name, "RefAxis");
            axis = feature.GetSpecificFeature2() as RefAxis;
            Require(axis != null, "IRefAxis unavailable: " + name);
            double[] p = ToArray(axis.GetRefAxisParams(), 6);
            double[] d = {p[3]-p[0],p[4]-p[1],p[5]-p[2]};
            double alignment = Math.Abs(Dot(d, expectedDirection)/(Norm(d)*Norm(expectedDirection)));
            double[] r = {expectedPoint[0]-p[0],expectedPoint[1]-p[1],expectedPoint[2]-p[2]};
            double[] cross = {r[1]*d[2]-r[2]*d[1],r[2]*d[0]-r[0]*d[2],r[0]*d[1]-r[1]*d[0]};
            double lineError = Norm(cross)/Norm(d);
            Require(alignment >= 1.0-DirectionTolerance && lineError <= PositionTolerance,
                "Reference axis geometry mismatch: " + name);
            return new Dictionary<string, object>
            {
                {"name",name},{"endpoints",p},{"absolute_alignment",alignment},{"point_to_line_error_m",lineError}
            };
        }
        finally { ReleaseCom(axis); ReleaseCom(feature); }
    }

    private static Dictionary<string, object> InspectPlane(ModelDoc2 model, string name,
        double[] expectedPoint, double[] expectedNormal)
    {
        Feature feature = null; RefPlane plane = null; MathTransform transform = null;
        try
        {
            feature = FindUniqueFeature(model, name, "RefPlane");
            plane = feature.GetSpecificFeature2() as RefPlane;
            Require(plane != null, "IRefPlane unavailable: " + name);
            transform = plane.Transform;
            double[] raw = ToArray(transform.ArrayData, 16);
            double[] n = {raw[6],raw[7],raw[8]};
            double alignment = Math.Abs(Dot(n,expectedNormal)/(Norm(n)*Norm(expectedNormal)));
            double[] delta = {expectedPoint[0]-raw[9],expectedPoint[1]-raw[10],expectedPoint[2]-raw[11]};
            double planeError = Math.Abs(Dot(n,delta))/Norm(n);
            Require(alignment >= 1.0-DirectionTolerance && planeError <= PositionTolerance,
                "Reference plane geometry mismatch: " + name + ", alignment=" + alignment + ", error=" + planeError);
            return new Dictionary<string, object>
            {
                {"name",name},{"raw_transform",raw},{"absolute_alignment",alignment},{"point_to_plane_error_m",planeError}
            };
        }
        finally { ReleaseCom(transform); ReleaseCom(plane); ReleaseCom(feature); }
    }

    private static Dictionary<string, object> InspectCarrier(ModelDoc2 model, CarrierSpec spec)
    {
        Require(BodyCount(model) == 0, spec.Link + " has bodies");
        Require(model.ListExternalFileReferencesCount2() == 0, spec.Link + " has external references");
        Require(FeatureTypeCount(model, "CoordSys") == spec.CoordinateSystemCount,
            spec.Link + " coordinate-system count changed");
        var refs = new List<Dictionary<string, object>>();
        double[] origin = {0,0,0};
        if (spec.Root)
        {
            refs.Add(InspectPlane(model,"ROOT_PLN_X",origin,Unit(0)));
            refs.Add(InspectPlane(model,"ROOT_PLN_Y",origin,Unit(1)));
            refs.Add(InspectPlane(model,"ROOT_PLN_Z",origin,Unit(2)));
        }
        if (spec.MovingIncoming)
        {
            int axisIndex = AxisIndex(spec.IncomingAxis);
            refs.Add(InspectAxis(model,"AXIS_"+spec.IncomingJoint,origin,spec.IncomingAxis));
            refs.Add(InspectPlane(model,"PLANE_SEAT_"+spec.IncomingJoint+"_CHILD_SIDE",origin,Unit(axisIndex)));
            int zeroNormal = axisIndex == 0 ? 2 : (axisIndex == 1 ? 0 : 1);
            refs.Add(InspectPlane(model,"PLANE_ZERO_"+spec.IncomingJoint,origin,Unit(zeroNormal)));
        }
        if (spec.FixedIncoming)
        {
            refs.Add(InspectPlane(model,"GFIX_PLN_X",origin,Unit(0)));
            refs.Add(InspectPlane(model,"GFIX_PLN_Y",origin,Unit(1)));
            refs.Add(InspectPlane(model,"GFIX_PLN_Z",origin,Unit(2)));
        }
        foreach (ParentDatum datum in spec.Outgoing)
        {
            Frame f = datum.Frame; double[] point = {f.X,f.Y,f.Z};
            Feature sketch = FindUniqueFeature(model,"SK3D_DATUM_"+f.Joint+"_PARENT_SIDE","3DProfileFeature");
            ReleaseCom(sketch);
            if (datum.Fixed)
            {
                refs.Add(InspectPlane(model,"GFIX_PLN_X_PARENT_SIDE",point,Apply(f,Unit(0))));
                refs.Add(InspectPlane(model,"GFIX_PLN_Y_PARENT_SIDE",point,Apply(f,Unit(1))));
                refs.Add(InspectPlane(model,"GFIX_PLN_Z_PARENT_SIDE",point,Apply(f,Unit(2))));
            }
            else
            {
                int axisIndex = AxisIndex(datum.AxisLocal);
                int zeroNormal = axisIndex == 0 ? 2 : (axisIndex == 1 ? 0 : 1);
                refs.Add(InspectAxis(model,"AXIS_"+f.Joint+"_PARENT_SIDE",point,Apply(f,datum.AxisLocal)));
                refs.Add(InspectPlane(model,"PLANE_SEAT_"+f.Joint+"_PARENT_SIDE",point,Apply(f,Unit(axisIndex))));
                refs.Add(InspectPlane(model,"PLANE_ZERO_"+f.Joint+"_PARENT_SIDE",point,Apply(f,Unit(zeroNormal))));
            }
        }
        return new Dictionary<string, object>
        {
            {"link",spec.Link},{"feature_count",FeatureCount(model)},
            {"coordinate_system_count",spec.CoordinateSystemCount},{"body_count",0},{"external_reference_count",0},
            {"mass_properties",ReadNoBodyMassEvidence(model)},{"properties",ReadProperties(model)},
            {"mate_reference_features",refs}
        };
    }

    private static int RunCreate(int expectedProcessId, string sourceDirectory,
        string outputDirectory, string receiptPath, string progressPath, int first, int count, string status)
    {
        var receipt = new Dictionary<string, object>
        {
            {"schema","B51R1_S05R_MATE_READY_CARRIER_CREATE_V1"},{"status","FAIL_CLOSED_NOT_STARTED"},
            {"generated_at_utc",DateTime.UtcNow.ToString("o")},{"expected_process_id",expectedProcessId},
            {"save3_call_count",0},{"save_as_call_count",0}
        };
        SldWorks app = null; ModelDoc2 model = null; Process process = null;
        var results = new List<Dictionary<string, object>>();
        try
        {
            Require(!File.Exists(receiptPath) && !File.Exists(progressPath), "Append-only recovery evidence exists");
            Directory.CreateDirectory(outputDirectory);
            List<CarrierSpec> specs = AllSpecs();
            for (int i=first;i<first+count;i++)
                Require(!File.Exists(Path.Combine(outputDirectory,specs[i].OutputFile)), "MR1 output exists: "+specs[i].OutputFile);
            app = Attach(expectedProcessId); process = Process.GetProcessById(expectedProcessId);
            ProgressCreateNew(progressPath,"CREATE_START "+DateTime.UtcNow.ToString("o"));
            for (int i=first;i<first+count;i++)
            {
                CarrierSpec spec = specs[i];
                string source = Path.Combine(sourceDirectory,spec.SourceFile);
                string output = Path.Combine(outputDirectory,spec.OutputFile);
                Require(File.Exists(source),"Source Carrier missing: "+source);
                string sourceBefore = Sha256(source);
                int errors=0,warnings=0;
                model = app.OpenDoc6(source,PartType,OpenSilent,"",ref errors,ref warnings) as ModelDoc2;
                Require(model!=null && errors==0 && warnings==0,"Source open failed: "+spec.Link);
                AddRecoveryReferences(model,spec);
                Require(model.Extension.SaveAs(output,0,1,null,ref errors,ref warnings),"SaveAs failed: "+spec.Link);
                receipt["save_as_call_count"] = Convert.ToInt32(receipt["save_as_call_count"])+1;
                Require(errors==0 && warnings==0,"SaveAs errors/warnings: "+spec.Link+" "+errors+"/"+warnings);
                Dictionary<string,object> inspection=InspectCarrier(model,spec);
                app.CloseDoc(model.GetTitle()); ReleaseCom(model); model=null;
                string sourceAfter=Sha256(source);
                Require(sourceAfter==sourceBefore,"Source Carrier changed: "+spec.Link);
                inspection["source_path"]=source; inspection["source_sha256_before_after"]=sourceBefore;
                inspection["output_path"]=output; inspection["output_bytes"]=new FileInfo(output).Length;
                inspection["output_sha256"]=Sha256(output); results.Add(inspection);
                Progress(progressPath,"CREATE_PASS "+spec.Link+" "+inspection["output_sha256"]);
            }
            app.ExitApp(); ReleaseCom(app); app=null;
            Require(process.WaitForExit(120000),"SOLIDWORKS normal exit timed out");
            receipt["parts"]=results; receipt["created_part_count"]=results.Count;
            receipt["normal_document_close"]=true; receipt["normal_application_exit"]=true;
            receipt["status"]=status; receipt["completed_at_utc"]=DateTime.UtcNow.ToString("o");
            WriteJsonCreateNew(receiptPath,receipt); Progress(progressPath,status); process.Dispose(); return 0;
        }
        catch(Exception ex)
        {
            receipt["parts"]=results; receipt["created_part_count"]=results.Count;
            receipt["status"]="FAIL_CLOSED"; receipt["exception_type"]=ex.GetType().FullName; receipt["exception"]=ex.ToString();
            try { if(app!=null && model!=null) app.CloseDoc(model.GetTitle()); } catch { }
            ReleaseCom(model);
            try { if(app!=null && app.GetDocumentCount()==0) app.ExitApp(); } catch { }
            ReleaseCom(app);
            if(process!=null) try { process.WaitForExit(120000); process.Dispose(); } catch { }
            try { if(!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath,receipt); } catch { }
            try { if(File.Exists(progressPath)) Progress(progressPath,"FAIL "+ex.Message); } catch { }
            return 1;
        }
    }

    private static int RunVerify(int expectedProcessId, string outputDirectory,
        string receiptPath, string progressPath, int first, int count, string status)
    {
        var receipt = new Dictionary<string, object>
        {
            {"schema","B51R1_S05R_MATE_READY_CARRIER_COLD_REOPEN_V1"},{"status","FAIL_CLOSED_NOT_STARTED"},
            {"generated_at_utc",DateTime.UtcNow.ToString("o")},{"expected_process_id",expectedProcessId},
            {"save3_call_count",0},{"save_as_call_count",0}
        };
        SldWorks app=null; ModelDoc2 model=null; Process process=null;
        var results=new List<Dictionary<string,object>>();
        try
        {
            Require(!File.Exists(receiptPath)&&!File.Exists(progressPath),"Append-only cold-reopen evidence exists");
            app=Attach(expectedProcessId); process=Process.GetProcessById(expectedProcessId);
            ProgressCreateNew(progressPath,"COLD_REOPEN_START "+DateTime.UtcNow.ToString("o"));
            List<CarrierSpec> specs=AllSpecs();
            for(int i=first;i<first+count;i++)
            {
                CarrierSpec spec=specs[i]; string path=Path.Combine(outputDirectory,spec.OutputFile);
                Require(File.Exists(path),"MR1 output missing: "+spec.OutputFile);
                string before=Sha256(path); int errors=0,warnings=0;
                model=app.OpenDoc6(path,PartType,OpenSilent|OpenReadOnly,"",ref errors,ref warnings) as ModelDoc2;
                Require(model!=null&&errors==0&&warnings==0,"Cold reopen failed: "+spec.Link);
                Dictionary<string,object> inspection=InspectCarrier(model,spec);
                app.CloseDoc(model.GetTitle()); ReleaseCom(model); model=null;
                string after=Sha256(path); Require(after==before,"MR1 hash changed during cold reopen: "+spec.Link);
                inspection["path"]=path; inspection["bytes"]=new FileInfo(path).Length;
                inspection["sha256_before_after"]=before; results.Add(inspection);
                Progress(progressPath,"COLD_REOPEN_PASS "+spec.Link+" "+before);
            }
            app.ExitApp(); ReleaseCom(app); app=null;
            Require(process.WaitForExit(120000),"SOLIDWORKS normal exit timed out");
            receipt["parts"]=results; receipt["verified_part_count"]=results.Count;
            receipt["normal_document_close"]=true; receipt["normal_application_exit"]=true;
            receipt["status"]=status; receipt["completed_at_utc"]=DateTime.UtcNow.ToString("o");
            WriteJsonCreateNew(receiptPath,receipt); Progress(progressPath,status); process.Dispose(); return 0;
        }
        catch(Exception ex)
        {
            receipt["parts"]=results; receipt["verified_part_count"]=results.Count;
            receipt["status"]="FAIL_CLOSED"; receipt["exception_type"]=ex.GetType().FullName; receipt["exception"]=ex.ToString();
            try { if(app!=null&&model!=null) app.CloseDoc(model.GetTitle()); } catch { }
            ReleaseCom(model);
            try { if(app!=null&&app.GetDocumentCount()==0) app.ExitApp(); } catch { }
            ReleaseCom(app);
            if(process!=null) try { process.WaitForExit(120000); process.Dispose(); } catch { }
            try { if(!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath,receipt); } catch { }
            try { if(File.Exists(progressPath)) Progress(progressPath,"FAIL "+ex.Message); } catch { }
            return 1;
        }
    }

    [STAThread]
    public static int CreatePilot(int expectedProcessId, string sourceDirectory,
        string outputDirectory, string receiptPath, string progressPath)
    {
        return RunCreate(expectedProcessId,sourceDirectory,outputDirectory,receiptPath,progressPath,
            0,2,"S05R_P_BASE_AND_LINK1_MR1_CREATED");
    }

    [STAThread]
    public static int VerifyPilot(int expectedProcessId, string outputDirectory,
        string receiptPath, string progressPath)
    {
        return RunVerify(expectedProcessId,outputDirectory,receiptPath,progressPath,
            0,2,"S05R_PC_BASE_AND_LINK1_MR1_COLD_REOPEN_PASS");
    }

    [STAThread]
    public static int CreateRemaining(int expectedProcessId, string sourceDirectory,
        string outputDirectory, string receiptPath, string progressPath)
    {
        return RunCreate(expectedProcessId,sourceDirectory,outputDirectory,receiptPath,progressPath,
            2,8,"S05R_B_REMAINING_EIGHT_MR1_CREATED");
    }

    [STAThread]
    public static int VerifyAll(int expectedProcessId, string outputDirectory,
        string receiptPath, string progressPath)
    {
        return RunVerify(expectedProcessId,outputDirectory,receiptPath,progressPath,
            0,10,"S05R_BC_ALL_TEN_MR1_COLD_REOPEN_PASS");
    }
}
