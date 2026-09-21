using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static class B51R1S03BS04BBatchCarrierToolV3
{
    private const int PartType = 1;
    private const int OpenSilent = 1;
    private const int OpenReadOnly = 2;
    private const double TransformTolerance = 1.0e-9;
    private const double DirectionTolerance = 1.0e-10;
    private const string UrdfSha = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164";
    private const string PilotSha = "1151ECD78BC18AD9CCBF2B3EC86365879D09B0CCF14425C17A09DD84119F7F62";

    private static readonly string[,] Properties =
    {
        {"MODEL_ROLE", "KINEMATIC_CARRIER"},
        {"DYNAMIC_AUTHORITY", "ACCEPTED_URDF"},
        {"CAD_MASS_CONTRIBUTION", "ZERO"},
        {"BOM_EXCLUDE", "TRUE"},
        {"SOURCE_URDF_SHA256", UrdfSha}
    };

    public sealed class VerificationManifest
    {
        public List<VerificationItem> parts { get; set; }
    }

    public sealed class VerificationItem
    {
        public string link { get; set; }
        public string path { get; set; }
        public string sha256 { get; set; }
        public int feature_count { get; set; }
    }

    private sealed class Frame
    {
        internal string Name;
        internal double X, Y, Z, Rx, Ry, Rz;

        internal Frame(string name, double x, double y, double z,
            double rx, double ry, double rz)
        {
            Name = name; X = x; Y = y; Z = z; Rx = rx; Ry = ry; Rz = rz;
        }
    }

    private sealed class CarrierSpec
    {
        internal string Link;
        internal string FileName;
        internal string IncomingJoint;
        internal double[] Axis;
        internal bool FixedIncoming;
        internal List<Frame> Outgoing = new List<Frame>();

        internal bool IsPilot { get { return Link == "base_link"; } }
        internal bool HasIncoming { get { return !String.IsNullOrEmpty(IncomingJoint); } }
        internal bool IsMoving { get { return HasIncoming && !FixedIncoming; } }
    }

    private static Frame F(string joint, double x, double y, double z,
        double rx, double ry, double rz)
    {
        return new Frame("CS_JOINT_" + joint + "_PARENT_SIDE", x, y, z, rx, ry, rz);
    }

    private static CarrierSpec Spec(string link, string incomingJoint, double[] axis,
        bool fixedIncoming, params Frame[] outgoing)
    {
        var result = new CarrierSpec
        {
            Link = link,
            FileName = "B51R1_CARRIER_" + link + ".SLDPRT",
            IncomingJoint = incomingJoint,
            Axis = axis,
            FixedIncoming = fixedIncoming
        };
        result.Outgoing.AddRange(outgoing);
        return result;
    }

    private static List<CarrierSpec> BatchSpecs()
    {
        return new List<CarrierSpec>
        {
            Spec("link1", "joint1", new double[] {0,0,1}, false,
                F("joint2", 0.020084, 0.031625, 0.05555, -1.5708, 0, 0)),
            Spec("link2", "joint2", new double[] {0,0,-1}, false,
                F("joint3", -0.264, 0, 0, 0, 0, 0)),
            Spec("link3", "joint3", new double[] {0,0,1}, false,
                F("joint4", 0.2426, -0.054, -0.001625, 0, 0, 0)),
            Spec("link4", "joint4", new double[] {0,0,1}, false,
                F("joint5", 0.078308, -0.0375, -0.03, -1.5708, 0, 0)),
            Spec("link5", "joint5", new double[] {0,0,1}, false,
                F("joint6", 0.023692, 0, 0.04, 0, 1.5708, 0)),
            Spec("link6", "joint6", new double[] {0,0,1}, false,
                F("gripper_joint", 0, 0, 0.15971, 0, -1.5708, 0)),
            Spec("gripper_link", "gripper_joint", null, true,
                F("gripper_joint1", -0.042091, 2.7531e-5, -1.3031e-5, 0, 0, -1.5708),
                F("gripper_joint2", -0.042091, -2.7531e-5, 1.3031e-5, 0, 0, 1.5708)),
            Spec("gripper_left", "gripper_joint1", new double[] {1,0,0}, false),
            Spec("gripper_right", "gripper_joint2", new double[] {1,0,0}, false)
        };
    }

    private static List<CarrierSpec> AllSpecs()
    {
        var result = new List<CarrierSpec>
        {
            Spec("base_link", null, null, false,
                F("joint1", -8.416e-5, 0, 0.08465, 0, 0, 0))
        };
        result.AddRange(BatchSpecs());
        return result;
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

    private static void StartProgress(string path, string message)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        using (FileStream stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.ReadWrite))
        using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false)))
            writer.WriteLine(DateTime.UtcNow.ToString("o") + " " + message);
    }

    private static void Progress(string path, string message)
    {
        using (FileStream stream = new FileStream(path, FileMode.Append, FileAccess.Write, FileShare.ReadWrite))
        using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false)))
            writer.WriteLine(DateTime.UtcNow.ToString("o") + " " + message);
    }

    private static SldWorks Attach(int expectedProcessId)
    {
        SldWorks app = (SldWorks)Marshal.GetActiveObject("SldWorks.Application");
        Require(app.GetProcessID() == expectedProcessId, "ROT PID mismatch");
        Require(app.Visible && app.StartupProcessCompleted, "SOLIDWORKS is not ready");
        Require(app.GetDocumentCount() == 0 && app.ActiveDoc == null, "Session is not empty");
        return app;
    }

    private static double[] ToArray(object raw)
    {
        Array input = raw as Array;
        Require(input != null, "Expected numeric COM array");
        double[] output = new double[input.Length];
        int index = 0;
        foreach (object value in input) output[index++] = Convert.ToDouble(value);
        return output;
    }

    private static Feature[] TopLevelFeatures(ModelDoc2 model)
    {
        FeatureManager manager = null;
        try
        {
            manager = model.FeatureManager;
            Array raw = manager.GetFeatures(true) as Array;
            if (raw == null) return new Feature[0];
            var result = new List<Feature>();
            foreach (object item in raw)
            {
                Feature feature = item as Feature;
                if (feature != null) result.Add(feature);
            }
            return result.ToArray();
        }
        finally { ReleaseCom(manager); }
    }

    private static int FeatureCount(ModelDoc2 model)
    {
        Feature[] features = TopLevelFeatures(model);
        try { return features.Length; }
        finally { foreach (Feature feature in features) ReleaseCom(feature); }
    }

    private static int FeatureTypeCount(ModelDoc2 model, string type)
    {
        int count = 0;
        Feature[] features = TopLevelFeatures(model);
        try
        {
            foreach (Feature feature in features)
                if (feature.GetTypeName2() == type) count++;
            return count;
        }
        finally { foreach (Feature feature in features) ReleaseCom(feature); }
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
            if (count != 1 || match == null)
            {
                ReleaseCom(match);
                throw new InvalidOperationException(
                    "Expected exactly one " + type + " named " + name + "; count=" + count);
            }
            return match;
        }
        catch { throw; }
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
            Require(extension != null, "ModelDocExtension unavailable for mass readback");
            int status = -1;
            object raw = extension.GetMassProperties2(2, out status, false);
            Array values = raw as Array;
            Require(status == 2,
                "Expected swMassPropertiesStatus_NoBody=2; observed " + status);
            return new Dictionary<string, object>
            {
                {"api", "IModelDocExtension.GetMassProperties2"},
                {"status", status}, {"expected_status", "swMassPropertiesStatus_NoBody"},
                {"returned_value_count", values == null ? 0 : values.Length},
                {"cad_mass_kg", 0.0}, {"basis", "NO_SOLID_BODY_AND_API_NO_BODY_STATUS"}
            };
        }
        finally { ReleaseCom(extension); }
    }

    private static List<Dictionary<string, object>> RunProperties(ModelDoc2 model, string expectedAction)
    {
        var results = new List<Dictionary<string, object>>();
        for (int i = 0; i < Properties.GetLength(0); i++)
        {
            B51R1DocumentTextPropertyResult result =
                B51R1NativeDocumentTextPropertyWriter.EnsureDocumentTextProperty(
                    model, Properties[i, 0], Properties[i, 1]);
            Require(result.Action == expectedAction, result.Name + " action mismatch: " + result.Action);
            results.Add(new Dictionary<string, object>
            {
                {"name", result.Name}, {"value", result.Value}, {"action", result.Action},
                {"field_type", result.FieldType},
                {"configuration_duplicate_count", result.ConfigurationDuplicateCount}
            });
        }
        return results;
    }

    private static Feature AddCoordinateSystem(ModelDoc2 model, Frame frame)
    {
        bool rotate = Math.Abs(frame.Rx) + Math.Abs(frame.Ry) + Math.Abs(frame.Rz) > 1.0e-15;
        Feature feature = model.FeatureManager.CreateCoordinateSystemUsingNumericalValues(
            true, frame.X, frame.Y, frame.Z, rotate, frame.Rx, frame.Ry, frame.Rz);
        Require(feature != null, "Coordinate-system creation failed: " + frame.Name);
        feature.Name = frame.Name;
        return feature;
    }

    private static Dictionary<int, Feature> DefaultPlanes(ModelDoc2 model)
    {
        var result = new Dictionary<int, Feature>();
        Feature[] features = TopLevelFeatures(model);
        try
        {
            foreach (Feature feature in features)
            {
                if (feature.GetTypeName2() == "RefPlane")
                {
                    int axis = -1;
                    if (feature.Name == "Right Plane" || feature.Name == "右视基准面") axis = 0;
                    if (feature.Name == "Top Plane" || feature.Name == "上视基准面") axis = 1;
                    if (feature.Name == "Front Plane" || feature.Name == "前视基准面") axis = 2;
                    Require(axis >= 0, "Unexpected default plane name: " + feature.Name);
                    Require(!result.ContainsKey(axis), "Duplicate default plane normal axis");
                    result[axis] = feature;
                }
                else ReleaseCom(feature);
            }
            Require(result.Count == 3, "Expected exactly three default reference planes");
            return result;
        }
        catch
        {
            foreach (Feature feature in result.Values) ReleaseCom(feature);
            throw;
        }
    }

    private static void InsertAxisFromPlanes(ModelDoc2 model, string name,
        Feature planeA, Feature planeB)
    {
        model.ClearSelection2(true);
        Require(planeA.Select2(false, 0), "First axis plane selection failed: " + name);
        Require(planeB.Select2(true, 0), "Second axis plane selection failed: " + name);
        Require(model.InsertAxis2(true), "InsertAxis2 failed: " + name);
        model.ClearSelection2(true);
    }

    private static Feature FindOnlyFeatureOfType(ModelDoc2 model, string type)
    {
        Feature[] features = TopLevelFeatures(model);
        Feature match = null;
        int count = 0;
        try
        {
            foreach (Feature feature in features)
            {
                if (feature.GetTypeName2() == type)
                {
                    count++;
                    if (match == null) match = feature;
                    else ReleaseCom(feature);
                }
                else ReleaseCom(feature);
            }
            if (count != 1 || match == null)
            {
                ReleaseCom(match);
                throw new InvalidOperationException("Expected one feature of type " + type);
            }
            return match;
        }
        catch { throw; }
    }

    private static void AddJointReferences(ModelDoc2 model, CarrierSpec spec)
    {
        Dictionary<int, Feature> planes = DefaultPlanes(model);
        string insertedAxisName = null;
        try
        {
            if (spec.FixedIncoming)
            {
                planes[0].Name = "GFIX_PLN_X";
                planes[1].Name = "GFIX_PLN_Y";
                planes[2].Name = "GFIX_PLN_Z";
                return;
            }
            if (!spec.IsMoving) return;
            int axisIndex = Math.Abs(spec.Axis[0]) > 0.5 ? 0 :
                (Math.Abs(spec.Axis[1]) > 0.5 ? 1 : 2);
            int firstNormal = axisIndex == 0 ? 1 : 0;
            int secondNormal = axisIndex == 2 ? 1 : 2;
            insertedAxisName = "AXIS_" + spec.IncomingJoint;
            InsertAxisFromPlanes(model, insertedAxisName,
                planes[firstNormal], planes[secondNormal]);
            int zeroNormal = axisIndex == 0 ? 2 : (axisIndex == 1 ? 0 : 1);
            planes[zeroNormal].Name = "PLANE_ZERO_" + spec.IncomingJoint;
        }
        finally { foreach (Feature feature in planes.Values) ReleaseCom(feature); }
        if (insertedAxisName != null)
        {
            Feature axis = FindOnlyFeatureOfType(model, "RefAxis");
            try { axis.Name = insertedAxisName; }
            finally { ReleaseCom(axis); }
        }
    }

    private static List<Frame> ExpectedFrames(CarrierSpec spec)
    {
        var frames = new List<Frame>
        {
            new Frame("CS_LINK_" + spec.Link, 0,0,0,0,0,0)
        };
        if (spec.HasIncoming)
            frames.Add(new Frame("CS_JOINT_" + spec.IncomingJoint + "_CHILD_SIDE", 0,0,0,0,0,0));
        frames.AddRange(spec.Outgoing);
        frames.Add(new Frame("CS_VISUAL_MOUNT_" + spec.Link, 0,0,0,0,0,0));
        return frames;
    }

    private static double[] ExpectedTransform(Frame frame)
    {
        int rotations = (Math.Abs(frame.Rx) > 1.0e-15 ? 1 : 0) +
            (Math.Abs(frame.Ry) > 1.0e-15 ? 1 : 0) +
            (Math.Abs(frame.Rz) > 1.0e-15 ? 1 : 0);
        Require(rotations <= 1, "Controlled Carrier RPY must contain at most one nonzero angle");
        double[] value = {1,0,0,0,1,0,0,0,1,frame.X,frame.Y,frame.Z,1,0,0,0};
        if (Math.Abs(frame.Rx) > 1.0e-15)
        {
            double c = Math.Cos(frame.Rx), s = Math.Sin(frame.Rx);
            value[4] = c; value[5] = s; value[7] = -s; value[8] = c;
        }
        else if (Math.Abs(frame.Ry) > 1.0e-15)
        {
            double c = Math.Cos(frame.Ry), s = Math.Sin(frame.Ry);
            value[0] = c; value[2] = -s; value[6] = s; value[8] = c;
        }
        else if (Math.Abs(frame.Rz) > 1.0e-15)
        {
            double c = Math.Cos(frame.Rz), s = Math.Sin(frame.Rz);
            value[0] = c; value[1] = s; value[3] = -s; value[4] = c;
        }
        return value;
    }

    private static Dictionary<string, object> InspectCoordinateSystem(
        ModelDoc2 model, Frame expected)
    {
        Feature feature = null;
        ModelDocExtension extension = null;
        MathTransform transform = null;
        try
        {
            feature = FindUniqueFeature(model, expected.Name, "CoordSys");
            extension = model.Extension;
            transform = extension.GetCoordinateSystemTransformByName(expected.Name);
            Require(transform != null, "Named transform unavailable: " + expected.Name);
            double[] raw = ToArray(transform.ArrayData);
            double[] target = ExpectedTransform(expected);
            Require(raw.Length == 16, "Coordinate-system transform length mismatch");
            double error = 0.0;
            for (int i = 0; i < 16; i++) error = Math.Max(error, Math.Abs(raw[i] - target[i]));
            Require(error <= TransformTolerance,
                expected.Name + " raw local-to-model transform error=" + error);
            return new Dictionary<string, object>
            {
                {"name", expected.Name}, {"raw_local_to_model_transform", raw},
                {"expected_local_to_model_transform", target},
                {"maximum_absolute_error", error}
            };
        }
        finally { ReleaseCom(transform); ReleaseCom(extension); ReleaseCom(feature); }
    }

    private static Dictionary<string, object> InspectPlane(
        ModelDoc2 model, string name, int expectedNormalAxis)
    {
        Feature feature = null;
        RefPlane plane = null;
        MathTransform transform = null;
        try
        {
            feature = FindUniqueFeature(model, name, "RefPlane");
            plane = feature.GetSpecificFeature2() as RefPlane;
            Require(plane != null, "IRefPlane unavailable: " + name);
            transform = plane.Transform;
            double[] raw = ToArray(transform.ArrayData);
            double norm = Math.Sqrt(raw[6]*raw[6] + raw[7]*raw[7] + raw[8]*raw[8]);
            Require(norm > 0, "Plane normal has zero norm: " + name);
            double alignment = Math.Abs(raw[6 + expectedNormalAxis] / norm);
            Require(Math.Abs(1.0 - alignment) <= DirectionTolerance,
                "Plane normal mismatch: " + name);
            return new Dictionary<string, object>
            {
                {"name", name}, {"raw_plane_to_model_transform", raw},
                {"expected_normal_axis_index", expectedNormalAxis},
                {"absolute_axis_alignment", alignment}
            };
        }
        finally { ReleaseCom(transform); ReleaseCom(plane); ReleaseCom(feature); }
    }

    private static Dictionary<string, object> InspectAxis(ModelDoc2 model,
        string name, double[] expectedDirection)
    {
        Feature feature = null;
        RefAxis axis = null;
        try
        {
            feature = FindUniqueFeature(model, name, "RefAxis");
            axis = feature.GetSpecificFeature2() as RefAxis;
            Require(axis != null, "IRefAxis unavailable: " + name);
            double[] p = ToArray(axis.GetRefAxisParams());
            Require(p.Length == 6, "Reference-axis endpoint count mismatch: " + name);
            double dx = p[3]-p[0], dy = p[4]-p[1], dz = p[5]-p[2];
            double norm = Math.Sqrt(dx*dx + dy*dy + dz*dz);
            Require(norm > 0, "Reference-axis endpoints coincide: " + name);
            double expectedNorm = Math.Sqrt(expectedDirection[0]*expectedDirection[0] +
                expectedDirection[1]*expectedDirection[1] + expectedDirection[2]*expectedDirection[2]);
            double alignment = Math.Abs((dx*expectedDirection[0] + dy*expectedDirection[1] +
                dz*expectedDirection[2]) / (norm * expectedNorm));
            Require(Math.Abs(1.0 - alignment) <= DirectionTolerance,
                "Reference-axis direction mismatch: " + name);
            return new Dictionary<string, object>
            {
                {"name", name}, {"observed_endpoints_m", p},
                {"expected_unoriented_direction", expectedDirection},
                {"absolute_axis_alignment", alignment}
            };
        }
        finally { ReleaseCom(axis); ReleaseCom(feature); }
    }

    private static Dictionary<string, object> InspectModel(
        ModelDoc2 model, CarrierSpec spec, string expectedPropertyAction)
    {
        Require(BodyCount(model) == 0, spec.Link + " has bodies");
        Require(model.ListExternalFileReferencesCount2() == 0,
            spec.Link + " has external references");
        List<Frame> frames = ExpectedFrames(spec);
        Require(FeatureTypeCount(model, "CoordSys") == frames.Count,
            spec.Link + " coordinate-system count mismatch");
        var frameResults = new List<Dictionary<string, object>>();
        foreach (Frame frame in frames) frameResults.Add(InspectCoordinateSystem(model, frame));
        var referenceResults = new List<Dictionary<string, object>>();
        if (spec.FixedIncoming)
        {
            referenceResults.Add(InspectPlane(model, "GFIX_PLN_X", 0));
            referenceResults.Add(InspectPlane(model, "GFIX_PLN_Y", 1));
            referenceResults.Add(InspectPlane(model, "GFIX_PLN_Z", 2));
            Require(FeatureTypeCount(model, "RefAxis") == 0,
                spec.Link + " fixed carrier unexpectedly contains a reference axis");
        }
        else if (spec.IsMoving)
        {
            referenceResults.Add(InspectAxis(model, "AXIS_" + spec.IncomingJoint, spec.Axis));
            int axisIndex = Math.Abs(spec.Axis[0]) > 0.5 ? 0 :
                (Math.Abs(spec.Axis[1]) > 0.5 ? 1 : 2);
            int zeroNormal = axisIndex == 0 ? 2 : (axisIndex == 1 ? 0 : 1);
            referenceResults.Add(InspectPlane(model, "PLANE_ZERO_" + spec.IncomingJoint, zeroNormal));
            Require(FeatureTypeCount(model, "RefAxis") == 1,
                spec.Link + " moving carrier reference-axis count mismatch");
        }
        return new Dictionary<string, object>
        {
            {"link", spec.Link}, {"feature_count", FeatureCount(model)},
            {"coordinate_system_count", frames.Count}, {"body_count", 0},
            {"external_reference_count", 0},
            {"mass_properties", ReadNoBodyMassEvidence(model)},
            {"property_results", RunProperties(model, expectedPropertyAction)},
            {"coordinate_systems", frameResults}, {"joint_reference_features", referenceResults}
        };
    }

    private static CarrierSpec FindSpec(List<CarrierSpec> specs, string link)
    {
        foreach (CarrierSpec spec in specs)
            if (spec.Link == link) return spec;
        throw new InvalidOperationException("Unknown Carrier link in manifest: " + link);
    }

    [STAThread]
    public static int Create(int expectedProcessId, string templatePath, string carrierDirectory,
        string receiptPath, string progressPath)
    {
        var receipt = new Dictionary<string, object>
        {
            {"schema", "B51R1_S03B_BATCH_CARRIER_CREATE_RECEIPT_V1"},
            {"status", "FAIL_CLOSED_NOT_STARTED"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"expected_process_id", expectedProcessId}, {"save_as_call_count", 0}
        };
        SldWorks app = null;
        ModelDoc2 activeModel = null;
        Process process = null;
        var partResults = new List<Dictionary<string, object>>();
        try
        {
            Require(!File.Exists(receiptPath) && !File.Exists(progressPath),
                "Append-only S03B evidence output exists");
            List<CarrierSpec> specs = BatchSpecs();
            foreach (CarrierSpec spec in specs)
                Require(!File.Exists(Path.Combine(carrierDirectory, spec.FileName)),
                    "Controlled Carrier output already exists: " + spec.FileName);
            string pilotPath = Path.Combine(carrierDirectory, "B51R1_CARRIER_base_link.SLDPRT");
            Require(File.Exists(pilotPath) && Sha256(pilotPath) == PilotSha,
                "Pilot precondition failed");
            StartProgress(progressPath, "S03B_START");
            app = Attach(expectedProcessId);
            process = Process.GetProcessById(expectedProcessId);
            foreach (CarrierSpec spec in specs)
            {
                Progress(progressPath, "CREATE_BEGIN " + spec.Link);
                activeModel = app.NewDocument(templatePath, 0, 0, 0) as ModelDoc2;
                Require(activeModel != null && activeModel.GetType() == PartType,
                    "New part failed: " + spec.Link);
                Progress(progressPath, "NEW_DOCUMENT_PASS " + spec.Link);
                AddJointReferences(activeModel, spec);
                Progress(progressPath, "JOINT_REFERENCES_PASS " + spec.Link);
                List<Frame> frames = ExpectedFrames(spec);
                foreach (Frame frame in frames)
                {
                    Feature created = AddCoordinateSystem(activeModel, frame);
                    ReleaseCom(created);
                }
                Progress(progressPath, "COORDINATE_SYSTEMS_PASS " + spec.Link);
                List<Dictionary<string, object>> addedProperties =
                    RunProperties(activeModel, "ADDED_ONLY_IF_NEW");
                Progress(progressPath, "PROPERTIES_PASS " + spec.Link);
                string outputPath = Path.Combine(carrierDirectory, spec.FileName);
                int errors = 0, warnings = 0;
                Require(activeModel.Extension.SaveAs(outputPath, 0, 1, null, ref errors, ref warnings),
                    "SaveAs failed: " + spec.Link);
                receipt["save_as_call_count"] = Convert.ToInt32(receipt["save_as_call_count"]) + 1;
                Require(errors == 0 && warnings == 0,
                    spec.Link + " SaveAs errors=" + errors + " warnings=" + warnings);
                Dictionary<string, object> inspection =
                    InspectModel(activeModel, spec, "NO_OP_EXACT_MATCH");
                inspection["initial_property_results"] = addedProperties;
                inspection["path"] = outputPath;
                app.CloseDoc(activeModel.GetTitle());
                ReleaseCom(activeModel); activeModel = null;
                inspection["part_bytes"] = new FileInfo(outputPath).Length;
                inspection["part_sha256"] = Sha256(outputPath);
                partResults.Add(inspection);
                Progress(progressPath, "CREATE_PASS " + spec.Link + " " + inspection["part_sha256"]);
            }
            Require(Sha256(pilotPath) == PilotSha, "Pilot changed during S03B");
            app.ExitApp(); ReleaseCom(app); app = null;
            Require(process.WaitForExit(30000), "Normal ExitApp timed out");
            receipt["parts"] = partResults;
            receipt["created_part_count"] = partResults.Count;
            receipt["pilot_sha256_before_and_after"] = PilotSha;
            receipt["normal_document_close"] = true;
            receipt["normal_application_exit"] = true;
            receipt["status"] = "S03B_REMAINING_NINE_CARRIERS_CREATED";
            receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");
            WriteJsonCreateNew(receiptPath, receipt);
            Progress(progressPath, "S03B_PASS");
            process.Dispose(); return 0;
        }
        catch (Exception ex)
        {
            receipt["parts"] = partResults;
            receipt["created_part_count"] = partResults.Count;
            receipt["status"] = "FAIL_CLOSED";
            receipt["error_type"] = ex.GetType().FullName;
            receipt["error_message"] = ex.Message;
            receipt["error_stack"] = ex.ToString();
            try { if (app != null && activeModel != null) app.CloseDoc(activeModel.GetTitle()); } catch { }
            ReleaseCom(activeModel);
            try { if (app != null && app.GetDocumentCount() == 0) app.ExitApp(); } catch { }
            ReleaseCom(app);
            if (process != null) try { process.WaitForExit(30000); process.Dispose(); } catch { }
            try { if (!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath, receipt); } catch { }
            try { if (File.Exists(progressPath)) Progress(progressPath, "S03B_FAIL " + ex.Message); } catch { }
            return 1;
        }
    }

    [STAThread]
    public static int Verify(int expectedProcessId, string manifestPath,
        string receiptPath, string progressPath)
    {
        var receipt = new Dictionary<string, object>
        {
            {"schema", "B51R1_S04B_ALL_CARRIER_COLD_REOPEN_RECEIPT_V1"},
            {"status", "FAIL_CLOSED_NOT_STARTED"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"expected_process_id", expectedProcessId}, {"save_api_call_count", 0}
        };
        SldWorks app = null;
        ModelDoc2 activeModel = null;
        Process process = null;
        var results = new List<Dictionary<string, object>>();
        try
        {
            Require(!File.Exists(receiptPath) && !File.Exists(progressPath),
                "Append-only S04B evidence output exists");
            VerificationManifest manifest = new JavaScriptSerializer().Deserialize<VerificationManifest>(
                File.ReadAllText(manifestPath, Encoding.UTF8));
            Require(manifest != null && manifest.parts != null && manifest.parts.Count == 10,
                "Verification manifest must contain exactly ten parts");
            var seenLinks = new HashSet<string>(StringComparer.Ordinal);
            foreach (VerificationItem item in manifest.parts)
            {
                Require(seenLinks.Add(item.link), "Duplicate link in verification manifest: " + item.link);
                Require(File.Exists(item.path) && Sha256(item.path) == item.sha256,
                    "Carrier hash precondition failed: " + item.link);
            }
            StartProgress(progressPath, "S04B_START");
            app = Attach(expectedProcessId);
            process = Process.GetProcessById(expectedProcessId);
            List<CarrierSpec> specs = AllSpecs();
            foreach (VerificationItem item in manifest.parts)
            {
                Progress(progressPath, "COLD_REOPEN_BEGIN " + item.link);
                CarrierSpec spec = FindSpec(specs, item.link);
                int errors = 0, warnings = 0;
                activeModel = app.OpenDoc6(item.path, PartType, OpenSilent | OpenReadOnly,
                    "", ref errors, ref warnings);
                Require(activeModel != null && errors == 0 && warnings == 0 && activeModel.IsOpenedReadOnly(),
                    "Read-only cold reopen failed: " + item.link);
                Dictionary<string, object> inspection =
                    InspectModel(activeModel, spec, "NO_OP_EXACT_MATCH");
                Require(Convert.ToInt32(inspection["feature_count"]) == item.feature_count,
                    item.link + " feature count differs from S03B/S04P authority");
                inspection["path"] = item.path;
                inspection["expected_sha256"] = item.sha256;
                app.CloseDoc(activeModel.GetTitle());
                ReleaseCom(activeModel); activeModel = null;
                Require(Sha256(item.path) == item.sha256,
                    item.link + " changed during read-only cold reopen");
                inspection["part_sha256_before_and_after"] = item.sha256;
                results.Add(inspection);
                Progress(progressPath, "COLD_REOPEN_PASS " + item.link);
            }
            Require(results.Count == 10, "Not all ten Carriers were verified");
            app.ExitApp(); ReleaseCom(app); app = null;
            Require(process.WaitForExit(30000), "Normal ExitApp timed out");
            receipt["parts"] = results;
            receipt["verified_part_count"] = results.Count;
            receipt["normal_document_close"] = true;
            receipt["normal_application_exit"] = true;
            receipt["status"] = "S04B_10_OF_10_NATIVE_CARRIERS_COLD_REOPEN_PASS";
            receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");
            WriteJsonCreateNew(receiptPath, receipt);
            Progress(progressPath, "S04B_PASS");
            process.Dispose(); return 0;
        }
        catch (Exception ex)
        {
            receipt["parts"] = results;
            receipt["verified_part_count"] = results.Count;
            receipt["status"] = "FAIL_CLOSED";
            receipt["error_type"] = ex.GetType().FullName;
            receipt["error_message"] = ex.Message;
            receipt["error_stack"] = ex.ToString();
            try { if (app != null && activeModel != null) app.CloseDoc(activeModel.GetTitle()); } catch { }
            ReleaseCom(activeModel);
            try { if (app != null && app.GetDocumentCount() == 0) app.ExitApp(); } catch { }
            ReleaseCom(app);
            if (process != null) try { process.WaitForExit(30000); process.Dispose(); } catch { }
            try { if (!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath, receipt); } catch { }
            try { if (File.Exists(progressPath)) Progress(progressPath, "S04B_FAIL " + ex.Message); } catch { }
            return 1;
        }
    }
}
