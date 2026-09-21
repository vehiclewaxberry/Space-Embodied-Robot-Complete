using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static class B51R1S05R2J01R14NativePilotTool
{
    private const int PartType = 1;
    private const int AssemblyType = 2;
    private const int OpenSilent = 1;
    private const int OpenReadOnly = 2;
    private const int SaveSilent = 1;

    private const int MateCoincident = 0;
    private const int MateAngle = 6;
    private const int MateHinge = 22;
    private const int MateAlignAligned = 0;
    private const int CreateMateSuccess = 1;
    private const int FeatureNoError = 0;

    private const int SelectDatumPlane = 4;
    private const int SelectDatumAxis = 5;
    private const int MateEntityMark = 1;
    private const int HingeSeatMark = 32768;
    private const int AngleReferenceMark = 67108864;

    private const int UnderConstrained = 2;
    private const int FullyConstrained = 3;
    private const int RemainingDofsRestricted = 0;

    private const double JointX = -8.416e-5;
    private const double JointY = 0.0;
    private const double JointZ = 0.08465;
    private const double Lower = -2.8;
    private const double NativeMinimum = 0.0;
    private const double NativeMaximum = 5.6;
    private const double NativeQ0 = 2.8;
    private const double OneDegree = Math.PI / 180.0;

    private const double ReferenceTranslationTolerance = 1.0e-8;
    private const double ReferenceRotationTolerance = 1.0e-8;
    private const double FkTranslationTolerance = 5.0e-6;
    private const double FkRotationTolerance = 5.0e-6;
    private const double JointTolerance = 1.0e-6;
    private const double LimitTolerance = 1.0e-6;

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static void ReleaseCom(object value)
    {
        if (value == null || !Marshal.IsComObject(value)) return;
        try { Marshal.FinalReleaseComObject(value); } catch { }
    }

    private static bool SameComIdentity(object first, object second)
    {
        if (first == null || second == null) return false;
        if (Object.ReferenceEquals(first, second)) return true;
        if (!Marshal.IsComObject(first) || !Marshal.IsComObject(second)) return first.Equals(second);
        IntPtr firstUnknown = IntPtr.Zero, secondUnknown = IntPtr.Zero;
        try
        {
            firstUnknown = Marshal.GetIUnknownForObject(first);
            secondUnknown = Marshal.GetIUnknownForObject(second);
            return firstUnknown == secondUnknown;
        }
        finally
        {
            if (secondUnknown != IntPtr.Zero) Marshal.Release(secondUnknown);
            if (firstUnknown != IntPtr.Zero) Marshal.Release(firstUnknown);
        }
    }

    private static bool TrySelectionIdentity(object value, out string selectionPath,
        out string selectionToken, out string featureName, out string featureType)
    {
        selectionPath = null;
        selectionToken = null;
        featureName = null;
        featureType = null;
        Feature feature = value as Feature;
        if (feature == null) return false;
        try
        {
            featureName = feature.Name;
            featureType = feature.GetTypeName2();
            selectionPath = feature.GetNameForSelection(out selectionToken);
            return !String.IsNullOrWhiteSpace(selectionPath) &&
                !String.IsNullOrWhiteSpace(selectionToken) &&
                !String.IsNullOrWhiteSpace(featureName) &&
                !String.IsNullOrWhiteSpace(featureType);
        }
        catch { return false; }
    }

    private static bool MatchesContextSelection(object value, string expectedFeatureName,
        string expectedFeatureType, string expectedSelectionToken, Component2 expectedComponent,
        ModelDoc2 model)
    {
        string path, token, name, type;
        if (expectedComponent == null || model == null ||
            !TrySelectionIdentity(value, out path, out token, out name, out type)) return false;
        string prefix = expectedFeatureName + "@" + expectedComponent.Name2 + "@";
        if (!path.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) return false;
        string assemblySuffix = path.Substring(prefix.Length);
        string currentTitle = model.GetTitle();
        if (String.IsNullOrWhiteSpace(currentTitle)) return false;
        currentTitle = currentTitle.TrimEnd('*');
        string currentTitleWithoutExtension = Path.GetFileNameWithoutExtension(currentTitle);
        return name.Equals(expectedFeatureName, StringComparison.Ordinal) &&
            type.Equals(expectedFeatureType, StringComparison.Ordinal) &&
            token.Equals(expectedSelectionToken, StringComparison.OrdinalIgnoreCase) &&
            (assemblySuffix.Equals(currentTitle, StringComparison.OrdinalIgnoreCase) ||
             assemblySuffix.Equals(currentTitleWithoutExtension, StringComparison.OrdinalIgnoreCase));
    }

    private static bool MatchesAssemblySelection(object value, string expectedFeatureName,
        string expectedFeatureType, string expectedSelectionToken)
    {
        string path, token, name, type;
        return TrySelectionIdentity(value, out path, out token, out name, out type) &&
            name.Equals(expectedFeatureName, StringComparison.Ordinal) &&
            type.Equals(expectedFeatureType, StringComparison.Ordinal) &&
            token.Equals(expectedSelectionToken, StringComparison.OrdinalIgnoreCase) &&
            path.Equals(expectedFeatureName, StringComparison.Ordinal);
    }

    private static bool MatchesUnorderedContextPair(object[] actual, ModelDoc2 model,
        string firstName, string firstType, string firstToken, Component2 firstComponent,
        string secondName, string secondType, string secondToken, Component2 secondComponent)
    {
        return actual.Length == 2 &&
            ((MatchesContextSelection(actual[0], firstName, firstType, firstToken, firstComponent, model) &&
              MatchesContextSelection(actual[1], secondName, secondType, secondToken, secondComponent, model)) ||
             (MatchesContextSelection(actual[0], secondName, secondType, secondToken, secondComponent, model) &&
              MatchesContextSelection(actual[1], firstName, firstType, firstToken, firstComponent, model)));
    }

    private static object[] ObjectArray(object raw, string label)
    {
        Array values = raw as Array;
        Require(values != null, label + " is not an array");
        var result = new List<object>();
        foreach (object value in values) result.Add(value);
        return result.ToArray();
    }

    private static bool SameUnorderedComPair(object[] actual, object first, object second)
    {
        return actual.Length == 2 &&
            ((SameComIdentity(actual[0], first) && SameComIdentity(actual[1], second)) ||
             (SameComIdentity(actual[0], second) && SameComIdentity(actual[1], first)));
    }

    private static List<Dictionary<string, object>> MateSelectionLedger(
        Dictionary<string, object> attempt, int expectedCount, string label)
    {
        var ledger = attempt["entity_selections"] as List<Dictionary<string, object>>;
        Require(ledger != null && ledger.Count == expectedCount,
            label + " selection ledger count mismatch");
        return ledger;
    }

    private static bool MatchesSelectionLedger(object actual, Dictionary<string, object> expected)
    {
        if (actual == null || expected == null ||
            !expected.ContainsKey("identity_gate_pass") || !(bool)expected["identity_gate_pass"]) return false;
        string path, token, name, type;
        if (!TrySelectionIdentity(actual, out path, out token, out name, out type)) return false;
        string expectedPath = expected["assembly_context_selection_path"] as string;
        string expectedToken = expected["selection_type_token"] as string;
        string expectedName = expected["semantic_feature_name"] as string;
        string expectedType = expected["semantic_feature_type"] as string;
        string expectedOwner = expected["expected_owner_component"] as string;
        string expectedOwnerPath = expected["expected_owner_path"] as string;
        string selectedOwner = expected["selected_owner_component"] as string;
        string selectedOwnerPath = expected["selected_owner_path"] as string;
        if (String.IsNullOrWhiteSpace(expectedPath) || String.IsNullOrWhiteSpace(expectedToken) ||
            String.IsNullOrWhiteSpace(expectedName) || String.IsNullOrWhiteSpace(expectedType)) return false;
        bool identityMatch = path.Equals(expectedPath, StringComparison.OrdinalIgnoreCase) &&
            token.Equals(expectedToken, StringComparison.OrdinalIgnoreCase) &&
            name.Equals(expectedName, StringComparison.Ordinal) &&
            type.Equals(expectedType, StringComparison.Ordinal);
        if (!identityMatch) return false;
        if (expectedOwner == null)
            return expectedOwnerPath == null && selectedOwner == null && selectedOwnerPath == null &&
                path.Equals(expectedName, StringComparison.Ordinal);
        return !String.IsNullOrWhiteSpace(expectedOwnerPath) &&
            expectedOwner.Equals(selectedOwner, StringComparison.Ordinal) &&
            !String.IsNullOrWhiteSpace(selectedOwnerPath) &&
            Path.GetFullPath(expectedOwnerPath).Equals(Path.GetFullPath(selectedOwnerPath),
                StringComparison.OrdinalIgnoreCase) &&
            path.StartsWith(expectedName + "@" + expectedOwner + "@",
                StringComparison.OrdinalIgnoreCase);
    }

    private static bool MatchesUnorderedLedgerPair(object[] actual,
        Dictionary<string, object> first, Dictionary<string, object> second)
    {
        return actual.Length == 2 &&
            ((MatchesSelectionLedger(actual[0], first) && MatchesSelectionLedger(actual[1], second)) ||
             (MatchesSelectionLedger(actual[0], second) && MatchesSelectionLedger(actual[1], first)));
    }

    private static bool ValidMateAlignment(int value)
    {
        return value == MateAlignAligned;
    }

    private static Dictionary<string, object> EntitySummary(object value)
    {
        var result = new Dictionary<string, object>
        {
            { "managed_runtime_type", value == null ? null : value.GetType().FullName },
            { "is_com_object", value != null && Marshal.IsComObject(value) },
            { "is_feature", value is Feature }, { "is_ref_plane", value is RefPlane },
            { "is_ref_axis", value is RefAxis }
        };
        Feature feature = value as Feature;
        if (feature != null)
        {
            result["runtime_type"] = "Feature";
            result["name"] = feature.Name;
            result["feature_type"] = feature.GetTypeName2();
            try
            {
                string selectionToken;
                result["selection_path"] = feature.GetNameForSelection(out selectionToken);
                result["selection_token"] = selectionToken;
            }
            catch (Exception ex)
            {
                result["selection_path"] = null;
                result["selection_token"] = null;
                result["selection_identity_diagnostic_exception"] = ex.GetType().FullName + ": " + ex.Message;
            }
            return result;
        }
        if (value is RefPlane)
        {
            result["runtime_type"] = "RefPlane";
            result["name"] = null;
            result["feature_type"] = "RefPlane";
            return result;
        }
        if (value is RefAxis)
        {
            result["runtime_type"] = "RefAxis";
            result["name"] = null;
            result["feature_type"] = "RefAxis";
            return result;
        }
        result["runtime_type"] = value == null ? null : value.GetType().FullName;
        result["name"] = null;
        result["feature_type"] = null;
        return result;
    }

    private static void ReleaseComItems(IEnumerable<object> values)
    {
        if (values == null) return;
        foreach (object value in values) ReleaseCom(value);
    }

    private static int SelectedObjectCount(ModelDoc2 model)
    {
        SelectionMgr manager = null;
        try
        {
            manager = model.SelectionManager as SelectionMgr;
            Require(manager != null, "Selection manager is unavailable");
            return manager.GetSelectedObjectCount2(-1);
        }
        finally { ReleaseCom(manager); }
    }

    private static string Sha256(string path)
    {
        using (FileStream stream = File.OpenRead(path))
        using (SHA256 digest = SHA256.Create())
            return BitConverter.ToString(digest.ComputeHash(stream)).Replace("-", "");
    }

    private static void WriteJsonCreateNew(string path, Dictionary<string, object> data)
    {
        Require(!File.Exists(path), "Append-only JSON exists: " + path);
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        using (FileStream stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
        using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false)))
            writer.Write(new JavaScriptSerializer { MaxJsonLength = Int32.MaxValue }.Serialize(data));
    }

    private static void ProgressCreateNew(string path, string text)
    {
        Require(!File.Exists(path), "Append-only progress log exists: " + path);
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        using (FileStream stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
        using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false)))
            writer.WriteLine(text);
    }

    private static void Progress(string path, string text)
    {
        using (FileStream stream = new FileStream(path, FileMode.Append, FileAccess.Write, FileShare.Read))
        using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false)))
            writer.WriteLine(text);
    }

    private static int IncrementCounter(Dictionary<string, object> receipt, string key)
    {
        int value = Convert.ToInt32(receipt[key]) + 1;
        receipt[key] = value;
        return value;
    }

    private static SldWorks Attach(int expectedProcessId)
    {
        SldWorks app = (SldWorks)Marshal.GetActiveObject("SldWorks.Application");
        Require(app.GetProcessID() == expectedProcessId, "ROT PID mismatch");
        Require(app.Visible && app.StartupProcessCompleted, "SOLIDWORKS is not ready");
        Require(app.GetDocumentCount() == 0 && app.ActiveDoc == null, "Session is not empty");
        return app;
    }

    private static double[] ToArray(object raw, int required)
    {
        Array values = raw as Array;
        Require(values != null && values.Length >= required, "Unexpected numeric array");
        double[] result = new double[values.Length];
        for (int i = 0; i < values.Length; i++) result[i] = Convert.ToDouble(values.GetValue(i));
        return result;
    }

    private static double Dot(double[] a, double[] b)
    {
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    }

    private static double Norm(double[] value)
    {
        return Math.Sqrt(Dot(value, value));
    }

    private static double[] Normalize(double[] value)
    {
        double norm = Norm(value);
        Require(norm > 1.0e-14, "Cannot normalize zero vector");
        return new[] { value[0] / norm, value[1] / norm, value[2] / norm };
    }

    private static double[] Cross(double[] a, double[] b)
    {
        return new[]
        {
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]
        };
    }

    private static double Clamp(double value, double low, double high)
    {
        return Math.Max(low, Math.Min(high, value));
    }

    private static Feature[] Features(ModelDoc2 model, bool topLevelOnly)
    {
        object raw = model.FeatureManager.GetFeatures(topLevelOnly);
        Array values = raw as Array;
        if (values == null) return new Feature[0];
        var result = new List<Feature>();
        foreach (object value in values)
        {
            Feature feature = value as Feature;
            if (feature != null) result.Add(feature);
        }
        return result.ToArray();
    }

    private static Feature FindFeature(ModelDoc2 model, string name, string type)
    {
        Feature[] features = Features(model, false);
        Feature match = null;
        try
        {
            int count = 0;
            foreach (Feature feature in features)
            {
                if (feature.Name == name && (type == null || feature.GetTypeName2() == type))
                {
                    match = feature;
                    count++;
                }
            }
            Require(count == 1, "Feature lookup is not unique: " + name + ", count=" + count);
            return match;
        }
        finally
        {
            foreach (Feature feature in features)
                if (!Object.ReferenceEquals(feature, match)) ReleaseCom(feature);
        }
    }

    private static void FindFeaturePair(ModelDoc2 model, string firstName, string secondName,
        out Feature first, out Feature second)
    {
        Feature[] features = Features(model, false);
        first = null;
        second = null;
        try
        {
            int firstCount = 0, secondCount = 0;
            foreach (Feature feature in features)
            {
                if (feature.Name == firstName) { first = feature; firstCount++; }
                if (feature.Name == secondName) { second = feature; secondCount++; }
            }
            Require(firstCount == 1 && secondCount == 1,
                "Feature-pair lookup is not unique: " + firstName + "/" + secondName);
        }
        finally
        {
            foreach (Feature feature in features)
                if (!Object.ReferenceEquals(feature, first) && !Object.ReferenceEquals(feature, second)) ReleaseCom(feature);
        }
    }

    private static double[] PlaneLocalNormal(Feature feature)
    {
        RefPlane plane = null;
        MathTransform transform = null;
        try
        {
            plane = feature.GetSpecificFeature2() as RefPlane;
            Require(plane != null, "Feature is not a reference plane: " + feature.Name);
            transform = plane.Transform;
            double[] raw = ToArray(transform.ArrayData, 16);
            return Normalize(new[] { raw[6], raw[7], raw[8] });
        }
        finally { ReleaseCom(transform); ReleaseCom(plane); }
    }

    private static double[] PlaneLocalOrigin(Feature feature)
    {
        RefPlane plane = null;
        MathTransform transform = null;
        try
        {
            plane = feature.GetSpecificFeature2() as RefPlane;
            Require(plane != null, "Feature is not a reference plane: " + feature.Name);
            transform = plane.Transform;
            double[] raw = ToArray(transform.ArrayData, 16);
            return new[] { raw[9], raw[10], raw[11] };
        }
        finally { ReleaseCom(transform); ReleaseCom(plane); }
    }

    private static double[] ComponentTransform(Component2 component)
    {
        MathTransform transform = null;
        try
        {
            transform = component.GetTotalTransform(false);
            Require(transform != null, "Component total transform is unavailable: " + component.Name2);
            return ToArray(transform.ArrayData, 16);
        }
        finally { ReleaseCom(transform); }
    }

    private static double[] ApplyDirection(double[] transform, double[] vector)
    {
        return Normalize(new[]
        {
            transform[0] * vector[0] + transform[3] * vector[1] + transform[6] * vector[2],
            transform[1] * vector[0] + transform[4] * vector[1] + transform[7] * vector[2],
            transform[2] * vector[0] + transform[5] * vector[1] + transform[8] * vector[2]
        });
    }

    private static double[] ApplyPoint(double[] transform, double[] point)
    {
        return new[]
        {
            transform[0] * point[0] + transform[3] * point[1] + transform[6] * point[2] + transform[9],
            transform[1] * point[0] + transform[4] * point[1] + transform[7] * point[2] + transform[10],
            transform[2] * point[0] + transform[5] * point[1] + transform[8] * point[2] + transform[11]
        };
    }

    private static double[] WorldPlaneNormal(Component2 component, string featureName)
    {
        ModelDoc2 part = component.GetModelDoc2() as ModelDoc2;
        Feature feature = null;
        try
        {
            Require(part != null, "Component model unavailable: " + component.Name2);
            feature = FindFeature(part, featureName, "RefPlane");
            return ApplyDirection(ComponentTransform(component), PlaneLocalNormal(feature));
        }
        finally { ReleaseCom(feature); ReleaseCom(part); }
    }

    private static double[] WorldPlaneOrigin(Component2 component, string featureName)
    {
        ModelDoc2 part = component.GetModelDoc2() as ModelDoc2;
        Feature feature = null;
        try
        {
            Require(part != null, "Component model unavailable: " + component.Name2);
            feature = FindFeature(part, featureName, "RefPlane");
            return ApplyPoint(ComponentTransform(component), PlaneLocalOrigin(feature));
        }
        finally { ReleaseCom(feature); ReleaseCom(part); }
    }

    private static double[][] WorldAxisEndpoints(Component2 component, string featureName)
    {
        ModelDoc2 part = component.GetModelDoc2() as ModelDoc2;
        Feature feature = null;
        RefAxis axis = null;
        try
        {
            Require(part != null, "Component model unavailable: " + component.Name2);
            feature = FindFeature(part, featureName, "RefAxis");
            axis = feature.GetSpecificFeature2() as RefAxis;
            Require(axis != null, "Feature is not an axis: " + featureName);
            double[] raw = ToArray(axis.GetRefAxisParams(), 6);
            double[] transform = ComponentTransform(component);
            return new[]
            {
                ApplyPoint(transform, new[] { raw[0], raw[1], raw[2] }),
                ApplyPoint(transform, new[] { raw[3], raw[4], raw[5] })
            };
        }
        finally { ReleaseCom(axis); ReleaseCom(feature); ReleaseCom(part); }
    }

    private static Dictionary<string, object> PlaneReferenceWitness(Component2 component, string featureName)
    {
        ModelDoc2 part = component.GetModelDoc2() as ModelDoc2;
        Feature feature = null;
        RefPlane plane = null;
        MathTransform planeTransform = null;
        try
        {
            Require(part != null, "Component model unavailable: " + component.Name2);
            feature = FindFeature(part, featureName, "RefPlane");
            plane = feature.GetSpecificFeature2() as RefPlane;
            Require(plane != null, "Feature is not a plane: " + featureName);
            planeTransform = plane.Transform;
            double[] localTransform = ToArray(planeTransform.ArrayData, 16);
            double[] localNormal = Normalize(new[] { localTransform[6], localTransform[7], localTransform[8] });
            double[] localOrigin = { localTransform[9], localTransform[10], localTransform[11] };
            double[] componentTransform = ComponentTransform(component);
            return new Dictionary<string, object>
            {
                { "component", component.Name2 }, { "feature", featureName },
                { "plane_transform_raw", localTransform }, { "local_normal", localNormal },
                { "local_origin_m", localOrigin }, { "world_normal", ApplyDirection(componentTransform, localNormal) },
                { "world_origin_m", ApplyPoint(componentTransform, localOrigin) }
            };
        }
        finally
        {
            ReleaseCom(planeTransform); ReleaseCom(plane); ReleaseCom(feature); ReleaseCom(part);
        }
    }

    private static Dictionary<string, object> AxisReferenceWitness(Component2 component, string featureName)
    {
        ModelDoc2 part = component.GetModelDoc2() as ModelDoc2;
        Feature feature = null;
        RefAxis axis = null;
        try
        {
            Require(part != null, "Component model unavailable: " + component.Name2);
            feature = FindFeature(part, featureName, "RefAxis");
            axis = feature.GetSpecificFeature2() as RefAxis;
            Require(axis != null, "Feature is not an axis: " + featureName);
            double[] localEndpoints = ToArray(axis.GetRefAxisParams(), 6);
            double[] transform = ComponentTransform(component);
            double[] worldStart = ApplyPoint(transform, new[] { localEndpoints[0], localEndpoints[1], localEndpoints[2] });
            double[] worldEnd = ApplyPoint(transform, new[] { localEndpoints[3], localEndpoints[4], localEndpoints[5] });
            return new Dictionary<string, object>
            {
                { "component", component.Name2 }, { "feature", featureName },
                { "local_endpoints_raw_m", localEndpoints },
                { "world_start_m", worldStart }, { "world_end_m", worldEnd },
                { "world_direction", Normalize(new[]
                    { worldEnd[0] - worldStart[0], worldEnd[1] - worldStart[1], worldEnd[2] - worldStart[2] }) }
            };
        }
        finally { ReleaseCom(axis); ReleaseCom(feature); ReleaseCom(part); }
    }

    private static Dictionary<string, object> ReferenceGeometryWitness(Component2 parent, Component2 child)
    {
        return new Dictionary<string, object>
        {
            { "parent_limit_plane", PlaneReferenceWitness(parent, "PLANE_LIMIT_REF_joint1_PARENT_SIDE") },
            { "parent_zero_plane", PlaneReferenceWitness(parent, "PLANE_ZERO_joint1_PARENT_SIDE") },
            { "child_zero_plane", PlaneReferenceWitness(child, "PLANE_ZERO_joint1") },
            { "parent_axis", AxisReferenceWitness(parent, "AXIS_joint1_PARENT_SIDE") },
            { "child_axis", AxisReferenceWitness(child, "AXIS_joint1") }
        };
    }

    private static void NormalizeAssemblyRootPlanes(ModelDoc2 model)
    {
        Feature[] features = Features(model, true);
        var planes = new List<Feature>();
        try
        {
            foreach (Feature feature in features)
                if (feature.GetTypeName2() == "RefPlane") planes.Add(feature);
            Require(planes.Count == 3, "Assembly template must contain exactly three root planes");
            string[] names = { "ASM_ROOT_PLN_X", "ASM_ROOT_PLN_Y", "ASM_ROOT_PLN_Z" };
            bool[] used = new bool[3];
            foreach (Feature plane in planes)
            {
                double[] normal = PlaneLocalNormal(plane);
                int axis = 0;
                if (Math.Abs(normal[1]) > Math.Abs(normal[axis])) axis = 1;
                if (Math.Abs(normal[2]) > Math.Abs(normal[axis])) axis = 2;
                Require(Math.Abs(normal[axis]) >= 1.0 - ReferenceRotationTolerance && !used[axis], "Assembly root plane mapping failed");
                used[axis] = true;
                plane.Name = names[axis];
                Require(plane.Name == names[axis], "Assembly root plane rename failed: " + names[axis]);
            }
            Require(used.All(v => v), "Assembly root plane mapping is incomplete");
        }
        finally { foreach (Feature feature in features) ReleaseCom(feature); }
    }

    private static void PreloadPart(SldWorks app, string partPath, string expectedSha256, string role,
        int expectedDocumentCountBefore, List<Dictionary<string, object>> evidence,
        out ModelDoc2 part, out string partTitle)
    {
        int errors = 0, warnings = 0;
        part = null;
        partTitle = null;
        int documentCountBefore = app.GetDocumentCount();
        Require(documentCountBefore == expectedDocumentCountBefore,
            "Unexpected document count before preloading " + role + ": " + documentCountBefore);
        string hashBefore = Sha256(partPath);
        Require(hashBefore == expectedSha256, "Preload input hash mismatch before OpenDoc6: " + role);
        part = app.OpenDoc6(partPath, PartType, OpenSilent | OpenReadOnly, "", ref errors, ref warnings) as ModelDoc2;
        int documentCountAfter = app.GetDocumentCount();
        var record = new Dictionary<string, object>
        {
            { "role", role }, { "path", partPath }, { "bytes", new FileInfo(partPath).Length },
            { "sha256_before", hashBefore }, { "open_options", "SILENT_READ_ONLY" },
            { "model_returned", part != null }, { "open_errors", errors }, { "open_warnings", warnings },
            { "document_count_before", documentCountBefore }, { "document_count_after", documentCountAfter },
            { "held_loaded_until_add_component5", true }, { "standalone_title_closed", false }
        };
        evidence.Add(record);
        Require(part != null, "Part preload returned no model: " + partPath + ", errors=" + errors + ", warnings=" + warnings);
        partTitle = part.GetTitle();
        record["title"] = partTitle;
        record["opened_read_only"] = part.IsOpenedReadOnly();
        record["model_path"] = part.GetPathName();
        Require(errors == 0 && warnings == 0,
            "Part preload failed strict error/warning gate: " + partPath + ", errors=" + errors + ", warnings=" + warnings);
        Require(part.GetType() == PartType, "Preloaded document is not a part: " + role);
        Require(part.IsOpenedReadOnly(), "Preloaded part is not read-only: " + role);
        Require(Path.GetFullPath(part.GetPathName()).Equals(Path.GetFullPath(partPath), StringComparison.OrdinalIgnoreCase),
            "Preloaded part path mismatch: " + role);
        Require(documentCountAfter == expectedDocumentCountBefore + 1,
            "Preload did not increase document count exactly once: " + role + ", count=" + documentCountAfter);
        Require(Sha256(partPath) == hashBefore, "Part hash changed during preload: " + role);
        record["sha256_after_open"] = Sha256(partPath);
    }

    private static Component2 InsertPreloadedComponent(SldWorks app, ModelDoc2 assemblyModel, AssemblyDoc assembly,
        string partPath, double x, double y, double z, string role, ref ModelDoc2 part,
        ref string partTitle, Dictionary<string, object> preloadEvidence)
    {
        Require(part != null && !String.IsNullOrWhiteSpace(partTitle), "Preloaded part is unavailable: " + role);
        Require(part.IsOpenedReadOnly(), "Preloaded part lost read-only state: " + role);
        Require(Path.GetFullPath(part.GetPathName()).Equals(Path.GetFullPath(partPath), StringComparison.OrdinalIgnoreCase),
            "Preloaded part path changed before insertion: " + role);
        int activateError = 0;
        ModelDoc2 activated = app.ActivateDoc3(assemblyModel.GetTitle(), false, 0, ref activateError) as ModelDoc2;
        Require(activated != null && activateError == 0, "Assembly activation failed before component insertion");
        Require(SameComIdentity(activated, assemblyModel),
            "ActivateDoc3 returned a document other than the controlled assembly");
        // ActivateDoc3 returns the assembly's existing RCW. Final-releasing it here also
        // disconnects assemblyModel/IAssemblyDoc before AddComponent5.
        activated = null;
        Component2 component = assembly.AddComponent5(partPath, 0, "", false, "", x, y, z);
        Require(component != null, "AddComponent5 failed for preloaded part: " + role);
        assemblyModel.ClearSelection2(true);
        Require(component.Select4(false, null, false), "Component selection failed: " + role);
        if (component.IsFixed()) assembly.UnfixComponent();
        assemblyModel.ClearSelection2(true);
        Require(!component.IsFixed(), "Automatic Fix was not removed: " + role);
        Require(Path.GetFullPath(component.GetPathName()).Equals(Path.GetFullPath(partPath), StringComparison.OrdinalIgnoreCase),
            "Inserted component source mismatch: " + role);
        preloadEvidence["add_component5_succeeded"] = true;
        app.CloseDoc(partTitle);
        preloadEvidence["standalone_title_closed"] = true;
        preloadEvidence["document_count_after_standalone_close"] = app.GetDocumentCount();
        ReleaseCom(part);
        part = null;
        partTitle = null;
        return component;
    }

    private static bool IsExpectedSpecificType(object value, int expectedSelectionType)
    {
        if (expectedSelectionType == SelectDatumPlane) return value is RefPlane;
        if (expectedSelectionType == SelectDatumAxis) return value is RefAxis;
        return false;
    }

    private static string ExpectedSelectionToken(int expectedSelectionType)
    {
        if (expectedSelectionType == SelectDatumPlane) return "PLANE";
        if (expectedSelectionType == SelectDatumAxis) return "AXIS";
        throw new InvalidOperationException("Unsupported mate selection type: " + expectedSelectionType);
    }

    private static object ContextFeatureSpecific(Component2 component, string name, string type,
        int expectedSelectionType)
    {
        ModelDoc2 part = component.GetModelDoc2() as ModelDoc2;
        Require(part != null, "Component model unavailable: " + component.Name2);
        Feature source = FindFeature(part, name, type);
        Feature context = component.GetCorresponding(source) as Feature;
        Require(context != null, "Assembly-context Feature unavailable: " + name + "@" + component.Name2);
        Require(context.GetTypeName2() == type,
            "Assembly-context Feature type mismatch: " + name + "@" + component.Name2);
        object result = context.GetSpecificFeature2();
        Require(IsExpectedSpecificType(result, expectedSelectionType),
            "Assembly-context Feature did not yield the required specific interface: " + name + "@" + component.Name2);
        // The returned specific object can share COM identity with persisted mate RCWs.
        // Leave the borrowed source/context aliases to normal GC rather than invalidating that identity.
        return result;
    }

    private static Dictionary<string, object> BeginMateAttempt(string name, int mateType,
        string entityContract, List<Dictionary<string, object>> apiAttempts)
    {
        var selections = new List<Dictionary<string, object>>();
        var attempt = new Dictionary<string, object>
        {
            { "name", name }, { "mate_type", mateType }, { "entity_contract", entityContract },
            { "mate_alignment_requested", MateAlignAligned }, { "mate_alignment_name", "ALIGNED" },
            { "entity_selections", selections }
        };
        apiAttempts.Add(attempt);
        return attempt;
    }

    private static object SelectMateReference(ModelDoc2 model, Component2 component,
        Feature assemblyFeature, string sourceFeatureName, string sourceFeatureType,
        int expectedSelectionType, int mark, bool append, string role,
        Dictionary<string, object> receipt, Dictionary<string, object> attempt,
        List<Dictionary<string, object>> selectionLedger)
    {
        var record = new Dictionary<string, object>
        {
            { "mate_name", attempt["name"] }, { "role", role },
            { "expected_selection_type", expectedSelectionType },
            { "expected_selection_token", ExpectedSelectionToken(expectedSelectionType) },
            { "mark", mark }, { "append", append }, { "identity_gate_pass", false }
        };
        var attemptSelections = attempt["entity_selections"] as List<Dictionary<string, object>>;
        Require(attemptSelections != null, "Mate attempt selection ledger is unavailable: " + attempt["name"]);
        attemptSelections.Add(record);
        selectionLedger.Add(record);

        ModelDoc2 sourceModel = null;
        Feature sourceFeature = null, contextFeature = null, selectedFeature = null;
        object sourceSpecific = null, directSpecific = null, selectedRaw = null, selectedSpecific = null;
        Component2 selectedOwner = null;
        ModelDocExtension extension = null;
        SelectionMgr manager = null;
        try
        {
            if (component == null)
            {
                Require(assemblyFeature != null, "Assembly mate reference Feature is absent: " + role);
                sourceFeature = assemblyFeature;
                contextFeature = assemblyFeature;
                sourceSpecific = sourceFeature.GetSpecificFeature2();
                directSpecific = sourceSpecific;
                record["source_model_path"] = model.GetPathName();
                record["expected_owner_component"] = null;
                record["expected_owner_path"] = null;
            }
            else
            {
                Require(assemblyFeature == null, "Component mate reference must not supply an assembly Feature: " + role);
                sourceModel = component.GetModelDoc2() as ModelDoc2;
                Require(sourceModel != null, "Component source model is unavailable: " + role);
                sourceFeature = FindFeature(sourceModel, sourceFeatureName, sourceFeatureType);
                sourceSpecific = sourceFeature.GetSpecificFeature2();
                Require(IsExpectedSpecificType(sourceSpecific, expectedSelectionType),
                    "Source Feature specific-object type mismatch: " + role);
                try
                {
                    directSpecific = component.GetCorresponding(sourceSpecific);
                }
                catch (Exception diagnosticException)
                {
                    record["direct_corresponding_specific_exception_type"] = diagnosticException.GetType().FullName;
                    record["direct_corresponding_specific_exception"] = diagnosticException.Message;
                }
                contextFeature = component.GetCorresponding(sourceFeature) as Feature;
                Require(contextFeature != null, "Assembly-context selection Feature is unavailable: " + role);
                record["source_model_path"] = Path.GetFullPath(sourceModel.GetPathName());
                record["expected_owner_component"] = component.Name2;
                record["expected_owner_path"] = Path.GetFullPath(component.GetPathName());
            }

            Require(sourceFeature.GetTypeName2() == sourceFeatureType,
                "Source Feature type changed before selection: " + role);
            Require(IsExpectedSpecificType(sourceSpecific, expectedSelectionType),
                "Source specific object has the wrong runtime interface: " + role);
            bool directSpecificHasExpectedType = false;
            object directSpecificSummary = null;
            if (component == null)
            {
                directSpecificHasExpectedType = IsExpectedSpecificType(directSpecific, expectedSelectionType);
                Require(directSpecificHasExpectedType,
                    "Assembly root direct specific object has the wrong runtime interface: " + role);
                directSpecificSummary = EntitySummary(directSpecific);
            }
            else
            {
                try
                {
                    directSpecificHasExpectedType = IsExpectedSpecificType(directSpecific, expectedSelectionType);
                    directSpecificSummary = EntitySummary(directSpecific);
                }
                catch (Exception diagnosticException)
                {
                    directSpecificHasExpectedType = false;
                    directSpecificSummary = null;
                    record["direct_corresponding_specific_inspection_exception_type"] = diagnosticException.GetType().FullName;
                    record["direct_corresponding_specific_inspection_exception"] = diagnosticException.Message;
                }
            }

            record["source_feature"] = EntitySummary(sourceFeature);
            record["source_specific"] = EntitySummary(sourceSpecific);
            record["direct_corresponding_specific"] = directSpecificSummary;
            record["direct_corresponding_specific_has_expected_type"] = directSpecificHasExpectedType;
            record["direct_corresponding_specific_diagnostic_only"] = component != null;
            record["mate_entity_authority"] = "ISelectionMgr.GetSelectedObject6";
            record["assembly_context_feature"] = EntitySummary(contextFeature);

            string selectionTypeToken;
            string selectionName = contextFeature.GetNameForSelection(out selectionTypeToken);
            Require(!String.IsNullOrWhiteSpace(selectionName), "GetNameForSelection returned an empty name: " + role);
            Require(selectionTypeToken.Equals(ExpectedSelectionToken(expectedSelectionType),
                StringComparison.OrdinalIgnoreCase), "GetNameForSelection type mismatch: " + role + ", type=" + selectionTypeToken);
            record["assembly_context_selection_path"] = selectionName;
            record["selection_type_token"] = selectionTypeToken;
            record["semantic_feature_name"] = contextFeature.Name;
            record["semantic_feature_type"] = contextFeature.GetTypeName2();

            extension = model.Extension;
            manager = model.SelectionManager as SelectionMgr;
            Require(extension != null && manager != null, "Assembly selection API is unavailable: " + role);
            int totalBefore = manager.GetSelectedObjectCount2(-1);
            int markedBefore = manager.GetSelectedObjectCount2(mark);
            Require(append == (totalBefore != 0), "SelectByID2 append contract mismatch: " + role);
            record["selection_count_before"] = totalBefore;
            record["marked_selection_count_before"] = markedBefore;
            record["select_by_id2_call_index"] = IncrementCounter(receipt, "mate_preselection_call_count");
            bool selected = extension.SelectByID2(selectionName, selectionTypeToken, 0.0, 0.0, 0.0,
                append, mark, null, 0);
            record["select_by_id2_returned"] = selected;
            Require(selected, "SelectByID2 failed: " + role + ", path=" + selectionName);

            int totalAfter = manager.GetSelectedObjectCount2(-1);
            int markedAfter = manager.GetSelectedObjectCount2(mark);
            record["selection_count_after"] = totalAfter;
            record["marked_selection_count_after"] = markedAfter;
            Require(totalAfter == totalBefore + 1 && markedAfter == markedBefore + 1,
                "SelectByID2 selection-count transition mismatch: " + role);

            int markedIndex = markedAfter;
            selectedRaw = manager.GetSelectedObject6(markedIndex, mark);
            selectedFeature = selectedRaw as Feature;
            selectedSpecific = selectedFeature == null ? selectedRaw : selectedFeature.GetSpecificFeature2();
            int selectedType = manager.GetSelectedObjectType3(markedIndex, mark);
            int selectedMark = manager.GetSelectedObjectMark(totalAfter);
            selectedOwner = manager.GetSelectedObjectsComponent4(markedIndex, mark) as Component2;
            record["selected_object"] = EntitySummary(selectedRaw);
            record["selected_specific"] = EntitySummary(selectedSpecific);
            record["selected_object_global_index"] = totalAfter;
            record["selected_object_index_for_mark"] = markedIndex;
            record["selected_object_type"] = selectedType;
            record["selected_object_mark"] = selectedMark;
            record["selected_owner_component"] = selectedOwner == null ? null : selectedOwner.Name2;
            record["selected_owner_path"] = selectedOwner == null ? null : Path.GetFullPath(selectedOwner.GetPathName());

            Require(selectedType == expectedSelectionType,
                "Selected object type mismatch: " + role + ", type=" + selectedType);
            Require(selectedMark == mark, "Selected object mark mismatch: " + role + ", mark=" + selectedMark);
            Require(IsExpectedSpecificType(selectedSpecific, expectedSelectionType),
                "GetSelectedObject6 did not yield the required mate entity: " + role);
            if (selectedFeature != null)
                Require(SameComIdentity(selectedFeature, contextFeature),
                    "Selected assembly-context Feature identity mismatch: " + role);
            bool selectedMatchesDirect = false;
            if (component == null)
            {
                selectedMatchesDirect = directSpecificHasExpectedType &&
                    SameComIdentity(selectedSpecific, directSpecific);
                Require(selectedMatchesDirect,
                    "Assembly root selected specific entity differs from its direct specific object: " + role);
            }
            else if (directSpecificHasExpectedType)
            {
                try
                {
                    selectedMatchesDirect = SameComIdentity(selectedSpecific, directSpecific);
                }
                catch (Exception diagnosticException)
                {
                    selectedMatchesDirect = false;
                    record["direct_corresponding_specific_identity_exception_type"] = diagnosticException.GetType().FullName;
                    record["direct_corresponding_specific_identity_exception"] = diagnosticException.Message;
                }
            }
            if (component == null)
                Require(selectedOwner == null, "Assembly root plane unexpectedly has a component owner: " + role);
            else
            {
                Require(selectedOwner != null && SameComIdentity(selectedOwner, component),
                    "Selected entity owner component identity mismatch: " + role);
                Require(Path.GetFullPath(selectedOwner.GetPathName()).Equals(Path.GetFullPath(component.GetPathName()),
                    StringComparison.OrdinalIgnoreCase), "Selected entity owner path mismatch: " + role);
            }
            record["selected_feature_matches_context_feature"] = selectedFeature == null ? null : (object)true;
            record["selected_specific_matches_direct_corresponding_specific"] = selectedMatchesDirect;
            record["selected_owner_matches_expected_component"] = true;
            record["identity_gate_pass"] = true;
            return selectedSpecific;
        }
        catch (Exception ex)
        {
            record["failure_type"] = ex.GetType().FullName;
            record["failure"] = ex.Message;
            throw;
        }
        finally
        {
            // Do not FinalRelease source/direct/selected aliases or the borrowed owner here.
            // EntitiesToMate must retain the selected assembly-context RCW through CreateMate.
            manager = null;
            extension = null;
        }
    }

    private static Dictionary<string, object> CreatedMateEvidence(ModelDoc2 model, Feature feature,
        int expectedType, int createStatus, int preselectionCount, string name)
    {
        Mate2 mate = null;
        try
        {
            Require(feature != null, "CreateMate returned no Feature: " + name + ", ErrorStatus=" + createStatus);
            Require(createStatus == CreateMateSuccess,
                "CreateMate ErrorStatus mismatch: " + name + ", status=" + createStatus);
            feature.Name = name;
            Require(feature.Name == name, "Mate rename failed: " + name);
            Require(model.ForceRebuild3(false), "Rebuild failed after native mate creation: " + name);
            mate = feature.GetSpecificFeature2() as Mate2;
            Require(mate != null && mate.Type == expectedType, "Created mate type mismatch: " + name);
            bool isWarning = false;
            int featureError = feature.GetErrorCode2(out isWarning);
            Require(featureError == FeatureNoError && !isWarning,
                "Created mate Feature error: " + name + ", code=" + featureError + ", warning=" + isWarning);
            Require(SelectedObjectCount(model) == 0, "Post-CreateMate selection clear failed: " + name);
            return new Dictionary<string, object>
            {
                { "name", name }, { "mate_type", mate.Type }, { "feature_type_name", feature.GetTypeName2() },
                { "create_mate_error_status", createStatus }, { "feature_error_code", featureError },
                { "feature_error_is_warning", isWarning }, { "preselection_entity_count", preselectionCount },
                { "postcreation_selection_count", 0 }, { "mate_entity_count", mate.GetMateEntityCount() }
            };
        }
        finally { ReleaseCom(mate); }
    }

    private static Feature CreateCoincidentMate(ModelDoc2 model, AssemblyDoc assembly, RefPlane first,
        RefPlane second, string name, Dictionary<string, object> receipt,
        Dictionary<string, object> attempt, out Dictionary<string, object> evidence)
    {
        object rawData = null;
        CoincidentMateFeatureData data = null, readback = null;
        IMateFeatureData status = null;
        Feature feature = null;
        try
        {
            int preselectionCount = SelectedObjectCount(model);
            Require(preselectionCount == 2, "Coincident mate requires exactly two selected planes: " + name);
            attempt["preselection_count_before_create_mate_data"] = preselectionCount;
            attempt["create_mate_data_call_index"] = IncrementCounter(receipt, "create_mate_data_call_count");
            rawData = assembly.CreateMateData(MateCoincident);
            attempt["mate_data_returned"] = rawData != null;
            data = rawData as CoincidentMateFeatureData;
            status = rawData as IMateFeatureData;
            Require(data != null && status != null, "CreateMateData did not return coincident mate data: " + name);
            data.EntitiesToMate = new object[] { first, second };
            data.MateAlignment = MateAlignAligned;
            Require(SelectedObjectCount(model) == preselectionCount,
                "Coincident selection changed before CreateMate: " + name);
            attempt["create_mate_call_index"] = IncrementCounter(receipt, "create_mate_call_count");
            feature = assembly.CreateMate(rawData) as Feature;
            int createStatus = status.ErrorStatus;
            attempt["create_mate_error_status"] = createStatus;
            attempt["feature_returned"] = feature != null;
            int selectionCountAtReturn = SelectedObjectCount(model);
            attempt["selection_count_at_create_mate_return"] = selectionCountAtReturn;
            attempt["selection_count_at_create_mate_return_is_diagnostic_only"] = true;
            model.ClearSelection2(true);
            int selectionCountAfterClear = SelectedObjectCount(model);
            attempt["selection_count_after_post_create_clear"] = selectionCountAfterClear;
            Require(selectionCountAfterClear == 0,
                "Coincident selection clear failed after CreateMate: " + name);
            evidence = CreatedMateEvidence(model, feature, MateCoincident, createStatus, preselectionCount, name);

            readback = feature.GetDefinition() as CoincidentMateFeatureData;
            Require(readback != null, "Coincident GetDefinition readback failed: " + name);
            object[] entities = ObjectArray(readback.EntitiesToMate, name + " readback EntitiesToMate");
            List<Dictionary<string, object>> selectionLedger =
                MateSelectionLedger(attempt, 2, name);
            bool iunknownPairMatch = SameUnorderedComPair(entities, first, second);
            bool semanticPairMatch = MatchesUnorderedLedgerPair(entities,
                selectionLedger[0], selectionLedger[1]);
            attempt["definition_entity_count"] = entities.Length;
            attempt["definition_entities"] = entities.Select(EntitySummary).ToArray();
            attempt["definition_iunknown_pair_match_diagnostic_only"] = iunknownPairMatch;
            attempt["definition_semantic_pair_match"] = semanticPairMatch;
            attempt["definition_semantic_expected_selection_indices"] = new int[] { 0, 1 };
            attempt["definition_identity_authority"] = "SELECTMATE_REFERENCE_ASSEMBLY_CONTEXT_LEDGER_PATH_TOKEN_NAME_TYPE_OWNER";
            Require(semanticPairMatch, "Coincident semantic entity readback mismatch: " + name);
            Require(ValidMateAlignment(readback.MateAlignment), "Coincident alignment readback is invalid: " + name);
            evidence["definition_readback_pass"] = true;
            evidence["definition_entity_count"] = entities.Length;
            evidence["definition_entities"] = entities.Select(EntitySummary).ToArray();
            evidence["definition_iunknown_pair_match_diagnostic_only"] = iunknownPairMatch;
            evidence["definition_semantic_pair_match"] = true;
            evidence["definition_semantic_expected_selection_indices"] = new int[] { 0, 1 };
            evidence["definition_identity_authority"] = "SELECTMATE_REFERENCE_ASSEMBLY_CONTEXT_LEDGER_PATH_TOKEN_NAME_TYPE_OWNER";
            evidence["definition_alignment"] = readback.MateAlignment;
            return feature;
        }
        catch
        {
            ReleaseCom(feature);
            throw;
        }
        finally
        {
            try { if (SelectedObjectCount(model) != 0) model.ClearSelection2(true); } catch { }
            ReleaseCom(readback);
            ReleaseCom(rawData);
        }
    }

    private static Feature CreateHingeMate(ModelDoc2 model, AssemblyDoc assembly,
        RefAxis parentAxis, RefAxis childAxis, RefPlane parentSeat, RefPlane childSeat,
        string name, Dictionary<string, object> receipt,
        Dictionary<string, object> attempt, out Dictionary<string, object> evidence)
    {
        object rawData = null;
        HingeMateFeatureData data = null, readback = null;
        IMateFeatureData status = null;
        Feature feature = null;
        try
        {
            int preselectionCount = SelectedObjectCount(model);
            Require(preselectionCount == 4, "Hinge mate requires exactly four marked selections: " + name);
            attempt["preselection_count_before_create_mate_data"] = preselectionCount;
            attempt["create_mate_data_call_index"] = IncrementCounter(receipt, "create_mate_data_call_count");
            rawData = assembly.CreateMateData(MateHinge);
            attempt["mate_data_returned"] = rawData != null;
            data = rawData as HingeMateFeatureData;
            status = rawData as IMateFeatureData;
            Require(data != null && status != null, "CreateMateData did not return hinge mate data: " + name);
            data.EntitiesToMate[0] = new object[] { parentAxis, childAxis };
            data.EntitiesToMate[1] = new object[] { parentSeat, childSeat };
            data.AngleSelection = false;
            data.MateAlignment = MateAlignAligned;
            Require(SelectedObjectCount(model) == preselectionCount,
                "Hinge selection changed before CreateMate: " + name);
            attempt["create_mate_call_index"] = IncrementCounter(receipt, "create_mate_call_count");
            feature = assembly.CreateMate(rawData) as Feature;
            int createStatus = status.ErrorStatus;
            attempt["create_mate_error_status"] = createStatus;
            attempt["feature_returned"] = feature != null;
            int selectionCountAtReturn = SelectedObjectCount(model);
            attempt["selection_count_at_create_mate_return"] = selectionCountAtReturn;
            attempt["selection_count_at_create_mate_return_is_diagnostic_only"] = true;
            model.ClearSelection2(true);
            int selectionCountAfterClear = SelectedObjectCount(model);
            attempt["selection_count_after_post_create_clear"] = selectionCountAfterClear;
            Require(selectionCountAfterClear == 0,
                "Hinge selection clear failed after CreateMate: " + name);
            evidence = CreatedMateEvidence(model, feature, MateHinge, createStatus, preselectionCount, name);

            readback = feature.GetDefinition() as HingeMateFeatureData;
            Require(readback != null, "Hinge GetDefinition readback failed: " + name);
            object[] axes = ObjectArray(readback.EntitiesToMate[0], name + " readback axis entities");
            object[] seats = ObjectArray(readback.EntitiesToMate[1], name + " readback seat entities");
            List<Dictionary<string, object>> selectionLedger =
                MateSelectionLedger(attempt, 4, name);
            bool axisIunknownMatch = SameUnorderedComPair(axes, parentAxis, childAxis);
            bool seatIunknownMatch = SameUnorderedComPair(seats, parentSeat, childSeat);
            bool axisSemanticMatch = MatchesUnorderedLedgerPair(axes,
                selectionLedger[0], selectionLedger[1]);
            bool seatSemanticMatch = MatchesUnorderedLedgerPair(seats,
                selectionLedger[2], selectionLedger[3]);
            attempt["definition_axis_entities"] = axes.Select(EntitySummary).ToArray();
            attempt["definition_seat_entities"] = seats.Select(EntitySummary).ToArray();
            attempt["definition_axis_iunknown_pair_match_diagnostic_only"] = axisIunknownMatch;
            attempt["definition_seat_iunknown_pair_match_diagnostic_only"] = seatIunknownMatch;
            attempt["definition_axis_semantic_pair_match"] = axisSemanticMatch;
            attempt["definition_seat_semantic_pair_match"] = seatSemanticMatch;
            attempt["definition_axis_expected_selection_indices"] = new int[] { 0, 1 };
            attempt["definition_seat_expected_selection_indices"] = new int[] { 2, 3 };
            attempt["definition_identity_authority"] = "SELECTMATE_REFERENCE_ASSEMBLY_CONTEXT_LEDGER_PATH_TOKEN_NAME_TYPE_OWNER";
            Require(axisSemanticMatch, "Hinge semantic axis entity readback mismatch: " + name);
            Require(seatSemanticMatch, "Hinge semantic seat entity readback mismatch: " + name);
            Require(!readback.AngleSelection, "Hinge unexpectedly contains an angle constraint: " + name);
            Require(ValidMateAlignment(readback.MateAlignment), "Hinge alignment readback is invalid: " + name);
            evidence["definition_readback_pass"] = true;
            evidence["axis_entity_count"] = axes.Length;
            evidence["seat_entity_count"] = seats.Length;
            evidence["axis_entities"] = axes.Select(EntitySummary).ToArray();
            evidence["seat_entities"] = seats.Select(EntitySummary).ToArray();
            evidence["axis_iunknown_pair_match_diagnostic_only"] = axisIunknownMatch;
            evidence["seat_iunknown_pair_match_diagnostic_only"] = seatIunknownMatch;
            evidence["axis_semantic_pair_match"] = true;
            evidence["seat_semantic_pair_match"] = true;
            evidence["definition_axis_expected_selection_indices"] = new int[] { 0, 1 };
            evidence["definition_seat_expected_selection_indices"] = new int[] { 2, 3 };
            evidence["definition_identity_authority"] = "SELECTMATE_REFERENCE_ASSEMBLY_CONTEXT_LEDGER_PATH_TOKEN_NAME_TYPE_OWNER";
            evidence["angle_selection"] = readback.AngleSelection;
            evidence["definition_alignment"] = readback.MateAlignment;
            return feature;
        }
        catch
        {
            ReleaseCom(feature);
            throw;
        }
        finally
        {
            try { if (SelectedObjectCount(model) != 0) model.ClearSelection2(true); } catch { }
            ReleaseCom(readback);
            ReleaseCom(rawData);
        }
    }

    private static Feature CreateLimitAngleMate(ModelDoc2 model, AssemblyDoc assembly,
        RefPlane parentLimit, RefPlane childZero, RefAxis parentAxis, string name,
        Dictionary<string, object> receipt, Dictionary<string, object> attempt,
        out Dictionary<string, object> evidence)
    {
        object rawData = null;
        AngleMateFeatureData data = null, readback = null;
        IMateFeatureData status = null;
        Feature feature = null;
        object[] preCreateEntities = null;
        object preCreateReferenceEntity = null, readbackReferenceEntity = null;
        try
        {
            int acquiredSelectionCount = SelectedObjectCount(model);
            Require(acquiredSelectionCount == 3,
                "Limit angle entity acquisition requires exactly three marked selections: " + name);
            attempt["selection_count_before_direct_property_contract_clear"] = acquiredSelectionCount;
            attempt["angle_input_channel"] =
                "DIRECT_ENTITIES_TO_MATE_ONLY_WITH_REFERENCE_ENTITY_UNSET_AFTER_SELECTION_LEDGER_ACQUISITION";
            model.ClearSelection2(true);
            int preselectionCount = SelectedObjectCount(model);
            attempt["selection_count_after_direct_property_contract_clear"] = preselectionCount;
            Require(preselectionCount == 0,
                "Limit angle direct-property contract requires zero retained selections: " + name);
            attempt["preselection_count_before_create_mate_data"] = preselectionCount;
            attempt["create_mate_data_call_index"] = IncrementCounter(receipt, "create_mate_data_call_count");
            rawData = assembly.CreateMateData(MateAngle);
            attempt["mate_data_returned"] = rawData != null;
            data = rawData as AngleMateFeatureData;
            status = rawData as IMateFeatureData;
            Require(data != null && status != null, "CreateMateData did not return angle mate data: " + name);
            data.EntitiesToMate = new object[] { parentLimit, childZero };
            data.IsAdvancedMate = true;
            data.Angle = NativeQ0;
            data.MinimumAngle = NativeMinimum;
            data.MaximumAngle = NativeMaximum;
            data.MateAlignment = MateAlignAligned;
            data.FlipDimension = false;
            attempt["direct_property_entities_assigned"] = true;
            attempt["direct_property_reference_assigned"] = false;

            preCreateEntities = ObjectArray(data.EntitiesToMate,
                name + " pre-CreateMate EntitiesToMate getter");
            preCreateReferenceEntity = data.ReferenceEntity;
            int selectionCountBeforeCreate = SelectedObjectCount(model);
            attempt["precreate_entities_to_mate"] = preCreateEntities.Select(EntitySummary).ToArray();
            attempt["precreate_entities_to_mate_count"] = preCreateEntities.Length;
            attempt["precreate_reference_entity"] = EntitySummary(preCreateReferenceEntity);
            attempt["precreate_reference_entity_is_null"] = preCreateReferenceEntity == null;
            attempt["precreate_selection_count"] = selectionCountBeforeCreate;
            attempt["precreate_is_advanced_mate"] = data.IsAdvancedMate;
            attempt["precreate_angle_rad"] = data.Angle;
            attempt["precreate_minimum_angle_rad"] = data.MinimumAngle;
            attempt["precreate_maximum_angle_rad"] = data.MaximumAngle;
            attempt["precreate_mate_alignment"] = data.MateAlignment;
            attempt["precreate_flip_dimension"] = data.FlipDimension;
            Require(selectionCountBeforeCreate == preselectionCount,
                "Limit-angle selection changed before CreateMate: " + name);
            attempt["create_mate_call_index"] = IncrementCounter(receipt, "create_mate_call_count");
            feature = assembly.CreateMate(rawData) as Feature;
            int createStatus = status.ErrorStatus;
            attempt["create_mate_error_status"] = createStatus;
            attempt["feature_returned"] = feature != null;
            attempt["create_mate_return_object"] = EntitySummary(feature);
            int selectionCountAtReturn = SelectedObjectCount(model);
            attempt["selection_count_at_create_mate_return"] = selectionCountAtReturn;
            attempt["selection_count_at_create_mate_return_is_diagnostic_only"] = true;
            model.ClearSelection2(true);
            int selectionCountAfterClear = SelectedObjectCount(model);
            attempt["selection_count_after_post_create_clear"] = selectionCountAfterClear;
            Require(selectionCountAfterClear == 0,
                "Limit-angle selection clear failed after CreateMate: " + name);
            evidence = CreatedMateEvidence(model, feature, MateAngle, createStatus, preselectionCount, name);

            readback = feature.GetDefinition() as AngleMateFeatureData;
            Require(readback != null && readback.IsAdvancedMate, "Limit angle GetDefinition readback failed: " + name);
            object[] entities = ObjectArray(readback.EntitiesToMate, name + " readback EntitiesToMate");
            List<Dictionary<string, object>> selectionLedger =
                MateSelectionLedger(attempt, 3, name);
            bool entityIunknownMatch = SameUnorderedComPair(entities, parentLimit, childZero);
            bool entitySemanticMatch = MatchesUnorderedLedgerPair(entities,
                selectionLedger[0], selectionLedger[1]);
            readbackReferenceEntity = readback.ReferenceEntity;
            bool referenceIunknownMatch = SameComIdentity(readbackReferenceEntity, parentAxis);
            bool referenceSemanticMatch = MatchesSelectionLedger(readbackReferenceEntity,
                selectionLedger[2]);
            attempt["definition_entities"] = entities.Select(EntitySummary).ToArray();
            attempt["definition_reference_entity"] = EntitySummary(readbackReferenceEntity);
            attempt["definition_reference_entity_is_null"] = readbackReferenceEntity == null;
            attempt["definition_iunknown_pair_match_diagnostic_only"] = entityIunknownMatch;
            attempt["definition_reference_iunknown_match_diagnostic_only"] = referenceIunknownMatch;
            attempt["definition_semantic_pair_match"] = entitySemanticMatch;
            attempt["definition_reference_semantic_match_diagnostic_only"] = referenceSemanticMatch;
            attempt["definition_plane_expected_selection_indices"] = new int[] { 0, 1 };
            attempt["definition_reference_expected_selection_index"] = 2;
            attempt["definition_identity_authority"] = "SELECTMATE_REFERENCE_ASSEMBLY_CONTEXT_LEDGER_PATH_TOKEN_NAME_TYPE_OWNER";
            Require(entitySemanticMatch, "Limit angle semantic entity readback mismatch: " + name);
            Require(Math.Abs(readback.Angle - NativeQ0) <= JointTolerance,
                "Limit angle initial value readback mismatch: " + name);
            Require(Math.Abs(readback.MinimumAngle - NativeMinimum) <= LimitTolerance &&
                Math.Abs(readback.MaximumAngle - NativeMaximum) <= LimitTolerance,
                "Limit angle bounds readback mismatch: " + name);
            Require(ValidMateAlignment(readback.MateAlignment), "Limit angle alignment readback is invalid: " + name);
            Require(!readback.FlipDimension, "Limit angle flip-dimension readback mismatch: " + name);
            evidence["definition_readback_pass"] = true;
            evidence["definition_entity_count"] = entities.Length;
            evidence["definition_entities"] = entities.Select(EntitySummary).ToArray();
            evidence["reference_entity"] = EntitySummary(readbackReferenceEntity);
            evidence["reference_entity_is_null"] = readbackReferenceEntity == null;
            evidence["definition_iunknown_pair_match_diagnostic_only"] = entityIunknownMatch;
            evidence["reference_iunknown_match_diagnostic_only"] = referenceIunknownMatch;
            evidence["definition_semantic_pair_match"] = true;
            evidence["reference_semantic_match_diagnostic_only"] = referenceSemanticMatch;
            evidence["definition_plane_expected_selection_indices"] = new int[] { 0, 1 };
            evidence["definition_reference_expected_selection_index"] = 2;
            evidence["definition_identity_authority"] = "SELECTMATE_REFERENCE_ASSEMBLY_CONTEXT_LEDGER_PATH_TOKEN_NAME_TYPE_OWNER";
            evidence["angle_rad"] = readback.Angle;
            evidence["minimum_angle_rad"] = readback.MinimumAngle;
            evidence["maximum_angle_rad"] = readback.MaximumAngle;
            evidence["reference_entity_matches_parent_axis_diagnostic_only"] = referenceSemanticMatch;
            evidence["definition_alignment"] = readback.MateAlignment;
            evidence["flip_dimension"] = readback.FlipDimension;
            return feature;
        }
        catch
        {
            ReleaseCom(feature);
            throw;
        }
        finally
        {
            try { if (SelectedObjectCount(model) != 0) model.ClearSelection2(true); } catch { }
            if (readbackReferenceEntity != null &&
                !SameComIdentity(readbackReferenceEntity, parentAxis)) ReleaseCom(readbackReferenceEntity);
            if (preCreateReferenceEntity != null &&
                !SameComIdentity(preCreateReferenceEntity, parentAxis)) ReleaseCom(preCreateReferenceEntity);
            if (preCreateEntities != null)
            {
                foreach (object entity in preCreateEntities)
                    if (!SameComIdentity(entity, parentLimit) && !SameComIdentity(entity, childZero))
                        ReleaseCom(entity);
            }
            readbackReferenceEntity = null; preCreateReferenceEntity = null; preCreateEntities = null;
            ReleaseCom(readback);
            ReleaseCom(rawData);
        }
    }

    private static bool SameComponentBinding(Component2 actual, Component2 expected)
    {
        if (actual == null || expected == null) return false;
        string actualPath = actual.GetPathName();
        string expectedPath = expected.GetPathName();
        return !String.IsNullOrWhiteSpace(actual.Name2) &&
            actual.Name2.Equals(expected.Name2, StringComparison.Ordinal) &&
            !String.IsNullOrWhiteSpace(actualPath) && !String.IsNullOrWhiteSpace(expectedPath) &&
            Path.GetFullPath(actualPath).Equals(Path.GetFullPath(expectedPath),
                StringComparison.OrdinalIgnoreCase);
    }

    private static Dictionary<string, object> PersistedMateEntityBindingEvidence(Feature feature,
        int expectedType, Component2 parent, Component2 child)
    {
        Mate2 mate = null;
        var entities = new List<Dictionary<string, object>>();
        int assemblyRootCount = 0, parentComponentCount = 0, childComponentCount = 0;
        try
        {
            mate = feature.GetSpecificFeature2() as Mate2;
            Require(mate != null && mate.Type == expectedType, "Persisted mate type mismatch: " + feature.Name);
            int entityCount = mate.GetMateEntityCount();
            Require(expectedType == MateHinge ? entityCount >= 2 : entityCount == 2,
                "Persisted mate entity count mismatch: " + feature.Name);
            bool isRootMate = feature.Name.StartsWith("J00_ROOT_", StringComparison.Ordinal);
            for (int i = 0; i < entityCount; i++)
            {
                MateEntity2 entity = null;
                Component2 component = null;
                object reference = null;
                try
                {
                    entity = mate.MateEntity(i);
                    Require(entity != null, "Persisted mate entity is null: " + feature.Name);
                    component = entity.ReferenceComponent;
                    reference = entity.Reference;
                    bool matchesParent = SameComponentBinding(component, parent);
                    bool matchesChild = SameComponentBinding(component, child);
                    if (component == null) assemblyRootCount++;
                    if (matchesParent) parentComponentCount++;
                    if (matchesChild) childComponentCount++;
                    entities.Add(new Dictionary<string, object>
                    {
                        { "index", i }, { "reference_type", entity.ReferenceType },
                        { "reference_type2", entity.ReferenceType2 },
                        { "reference_present", reference != null },
                        { "reference_diagnostic_only", reference == null ? null : EntitySummary(reference) },
                        { "component", component == null ? null : component.Name2 },
                        { "component_path", component == null ? null : Path.GetFullPath(component.GetPathName()) },
                        { "component_matches_parent", matchesParent }, { "component_matches_child", matchesChild }
                    });
                }
                finally
                {
                    reference = null;
                    component = null;
                    ReleaseCom(entity);
                }
            }

            if (isRootMate)
                Require(assemblyRootCount == 1 && parentComponentCount == 1 && childComponentCount == 0,
                    "Persisted J00 root/base component binding mismatch: " + feature.Name);
            else if (expectedType == MateHinge)
                Require(assemblyRootCount == 0 && parentComponentCount >= 1 && childComponentCount >= 1 &&
                    parentComponentCount + childComponentCount == entityCount,
                    "Persisted J01 hinge component binding mismatch");
            else if (expectedType == MateAngle)
                Require(assemblyRootCount == 0 && parentComponentCount == 1 && childComponentCount == 1,
                    "Persisted J01 limit-angle component binding mismatch");

            return new Dictionary<string, object>
            {
                { "binding_authority", "IMate2.MateEntity ReferenceComponent instance name plus full component path" },
                { "role_specific_entity_authority", "MateFeatureData.GetDefinition EntitiesToMate selection path/token/name/type" },
                { "mate_entity_reference_used_as_authority", false },
                { "iunknown_identity_used_as_authority", false },
                { "documented_entity_count_gate", expectedType == MateHinge ? "AT_LEAST_TWO_ALL_BOUND_TO_PARENT_OR_CHILD" : "EXACTLY_TWO" },
                { "entity_count", entities.Count },
                { "assembly_root_entity_count", assemblyRootCount },
                { "parent_component_entity_count", parentComponentCount },
                { "child_component_entity_count", childComponentCount },
                { "component_binding_pass", true }, { "entities", entities }
            };
        }
        finally { ReleaseCom(mate); }
    }

    private static Dictionary<string, object> InspectMate(Feature feature, int expectedType)
    {
        Mate2 mate = null;
        var entities = new List<Dictionary<string, object>>();
        try
        {
            mate = feature.GetSpecificFeature2() as Mate2;
            Require(mate != null && mate.Type == expectedType, "Mate type mismatch: " + feature.Name);
            Require(mate.GetMateEntityCount() == 2, "Mate entity count mismatch: " + feature.Name);
            bool isWarning = false;
            int featureError = feature.GetErrorCode2(out isWarning);
            Require(featureError == FeatureNoError && !isWarning, "Mate feature has an error: " + feature.Name);
            for (int i = 0; i < mate.GetMateEntityCount(); i++)
            {
                MateEntity2 entity = null;
                Component2 component = null;
                try
                {
                    entity = mate.MateEntity(i);
                    Require(entity != null, "Mate entity is null: " + feature.Name);
                    component = entity.ReferenceComponent;
                    entities.Add(new Dictionary<string, object>
                    {
                        { "index", i },
                        { "reference_type", entity.ReferenceType },
                        { "reference_type2", entity.ReferenceType2 },
                        { "component", component == null ? null : component.Name2 },
                        { "component_path", component == null ? null : component.GetPathName() }
                    });
                }
                finally
                {
                    // ReferenceComponent is a borrowed assembly component alias.
                    component = null;
                    ReleaseCom(entity);
                }
            }
            return new Dictionary<string, object>
            {
                { "name", feature.Name }, { "type", mate.Type }, { "alignment", mate.Alignment },
                { "flipped", mate.Flipped }, { "entity_count", mate.GetMateEntityCount() }, { "entities", entities },
                { "feature_type_name", feature.GetTypeName2() }, { "feature_error_code", featureError },
                { "feature_error_is_warning", isWarning }
            };
        }
        finally { ReleaseCom(mate); }
    }

    private static Dictionary<string, object> InspectHingeMate(Feature feature)
    {
        Mate2 mate = null;
        HingeMateFeatureData data = null;
        object[] axes = null, seats = null;
        try
        {
            mate = feature.GetSpecificFeature2() as Mate2;
            Require(mate != null && mate.Type == MateHinge, "Hinge mate type mismatch: " + feature.Name);
            bool isWarning = false;
            int featureError = feature.GetErrorCode2(out isWarning);
            Require(featureError == FeatureNoError && !isWarning, "Hinge feature has an error: " + feature.Name);
            data = feature.GetDefinition() as HingeMateFeatureData;
            Require(data != null, "Hinge definition is unavailable: " + feature.Name);
            axes = ObjectArray(data.EntitiesToMate[0], feature.Name + " axis entities");
            seats = ObjectArray(data.EntitiesToMate[1], feature.Name + " seat entities");
            Require(axes.Length == 2 && seats.Length == 2, "Hinge definition does not contain two axis and two seat entities");
            Require(!data.AngleSelection, "Hinge persisted an unintended angle selection");
            Require(ValidMateAlignment(data.MateAlignment), "Hinge persisted an invalid alignment");
            return new Dictionary<string, object>
            {
                { "name", feature.Name }, { "type", mate.Type }, { "feature_type_name", feature.GetTypeName2() },
                { "feature_error_code", featureError }, { "feature_error_is_warning", isWarning },
                { "mate_entity_count", mate.GetMateEntityCount() }, { "mate_alignment", mate.Alignment },
                { "mate_flipped", mate.Flipped }, { "definition_alignment", data.MateAlignment },
                { "angle_selection", data.AngleSelection },
                { "axis_entities", axes.Select(EntitySummary).ToArray() },
                { "seat_entities", seats.Select(EntitySummary).ToArray() }
            };
        }
        finally
        {
            ReleaseComItems(seats); ReleaseComItems(axes);
            ReleaseCom(data); ReleaseCom(mate);
        }
    }

    private static Dictionary<string, object> InspectAngleMate(Feature feature)
    {
        Dictionary<string, object> result = InspectMate(feature, MateAngle);
        AngleMateFeatureData data = null;
        Mate2 mate = null;
        DisplayDimension display = null;
        Dimension dimension = null;
        object[] definitionEntities = null;
        object referenceEntity = null;
        try
        {
            data = feature.GetDefinition() as AngleMateFeatureData;
            Require(data != null && data.IsAdvancedMate, "J01 driver is not a native limit angle mate");
            Require(Math.Abs(data.MinimumAngle - NativeMinimum) <= LimitTolerance, "J01 minimum angle mismatch");
            Require(Math.Abs(data.MaximumAngle - NativeMaximum) <= LimitTolerance, "J01 maximum angle mismatch");
            Require(ValidMateAlignment(data.MateAlignment), "J01 driver alignment is invalid");
            definitionEntities = ObjectArray(data.EntitiesToMate, feature.Name + " definition entities");
            Require(definitionEntities.Length == 2, "J01 driver definition entity count mismatch");
            referenceEntity = data.ReferenceEntity;
            result["feature_data_angle_rad"] = data.Angle;
            result["minimum_angle_rad"] = data.MinimumAngle;
            result["maximum_angle_rad"] = data.MaximumAngle;
            result["is_advanced_mate"] = data.IsAdvancedMate;
            result["feature_data_alignment"] = data.MateAlignment;
            result["flip_dimension"] = data.FlipDimension;
            result["definition_entities"] = definitionEntities.Select(EntitySummary).ToArray();
            result["reference_entity"] = EntitySummary(referenceEntity);
            result["reference_entity_is_null"] = referenceEntity == null;
            result["reference_entity_diagnostic_only"] = true;
            mate = feature.GetSpecificFeature2() as Mate2;
            display = mate == null ? null : mate.DisplayDimension;
            dimension = display == null ? null : display.GetDimension2(0);
            result["display_dimension_system_value_rad"] = dimension == null ? (object)null : dimension.GetSystemValue2("");
            return result;
        }
        finally
        {
            ReleaseCom(referenceEntity); ReleaseComItems(definitionEntities);
            ReleaseCom(dimension); ReleaseCom(display); ReleaseCom(mate); ReleaseCom(data);
        }
    }

    private static Dictionary<string, object> NativeMateBindingWitness(ModelDoc2 model,
        Component2 parent, Component2 child)
    {
        Feature hinge = null, driver = null;
        HingeMateFeatureData hingeData = null;
        AngleMateFeatureData angleData = null;
        object[] hingeAxes = null, hingeSeats = null, angleEntities = null;
        object referenceEntity = null;
        try
        {
            FindFeaturePair(model, "J01_HINGE_NATIVE", "J01_LIMIT_ANGLE_DRIVER", out hinge, out driver);
            hingeData = hinge.GetDefinition() as HingeMateFeatureData;
            Require(hingeData != null && !hingeData.AngleSelection, "Native hinge definition binding is unavailable");
            hingeAxes = ObjectArray(hingeData.EntitiesToMate[0], "Native hinge axis bindings");
            hingeSeats = ObjectArray(hingeData.EntitiesToMate[1], "Native hinge seat bindings");
            Require(MatchesUnorderedContextPair(hingeAxes, model,
                "AXIS_joint1_PARENT_SIDE", "RefAxis", "AXIS", parent,
                "AXIS_joint1", "RefAxis", "AXIS", child),
                "Native hinge axis semantic binding mismatch");
            Require(MatchesUnorderedContextPair(hingeSeats, model,
                "PLANE_SEAT_joint1_PARENT_SIDE", "RefPlane", "PLANE", parent,
                "PLANE_SEAT_joint1_CHILD_SIDE", "RefPlane", "PLANE", child),
                "Native hinge seat semantic binding mismatch");

            angleData = driver.GetDefinition() as AngleMateFeatureData;
            Require(angleData != null && angleData.IsAdvancedMate, "Native limit-angle definition binding is unavailable");
            angleEntities = ObjectArray(angleData.EntitiesToMate, "Native limit-angle plane bindings");
            referenceEntity = angleData.ReferenceEntity;
            Require(MatchesUnorderedContextPair(angleEntities, model,
                "PLANE_LIMIT_REF_joint1_PARENT_SIDE", "RefPlane", "PLANE", parent,
                "PLANE_ZERO_joint1", "RefPlane", "PLANE", child),
                "Native limit-angle plane semantic binding mismatch");
            bool referenceSemanticMatch = referenceEntity != null && MatchesContextSelection(referenceEntity,
                "AXIS_joint1_PARENT_SIDE", "RefAxis", "AXIS", parent, model);
            Require(Math.Abs(angleData.Angle - NativeQ0) <= JointTolerance,
                "Native limit-angle final q0 binding witness has the wrong angle");
            Require(Math.Abs(angleData.MinimumAngle - NativeMinimum) <= LimitTolerance &&
                Math.Abs(angleData.MaximumAngle - NativeMaximum) <= LimitTolerance,
                "Native limit-angle binding witness has the wrong bounds");
            Require(ValidMateAlignment(angleData.MateAlignment), "Native limit-angle binding alignment is invalid");
            Require(!angleData.FlipDimension, "Native limit-angle binding flip-dimension changed");

            return new Dictionary<string, object>
            {
                { "binding_authority", "Persisted hinge axis/seat and limit-angle plane semantics plus bounds, branch, and full-sweep evidence" },
                { "direct_corresponding_specific_used_as_authority", false },
                { "iunknown_identity_used_as_authority", false },
                { "parent_component", parent.Name2 }, { "parent_component_path", Path.GetFullPath(parent.GetPathName()) },
                { "child_component", child.Name2 }, { "child_component_path", Path.GetFullPath(child.GetPathName()) },
                { "hinge_exact_axis_bindings", true }, { "hinge_exact_seat_bindings", true },
                { "hinge_angle_selection", hingeData.AngleSelection },
                { "hinge_axis_entities", hingeAxes.Select(EntitySummary).ToArray() },
                { "hinge_seat_entities", hingeSeats.Select(EntitySummary).ToArray() },
                { "limit_angle_exact_plane_bindings", true },
                { "limit_angle_reference_axis_binding_diagnostic_only", referenceSemanticMatch },
                { "limit_angle_entities", angleEntities.Select(EntitySummary).ToArray() },
                { "limit_angle_reference_entity", EntitySummary(referenceEntity) },
                { "limit_angle_reference_entity_is_null", referenceEntity == null },
                { "limit_angle_rad", angleData.Angle }, { "minimum_angle_rad", angleData.MinimumAngle },
                { "maximum_angle_rad", angleData.MaximumAngle }, { "alignment", angleData.MateAlignment },
                { "flip_dimension", angleData.FlipDimension }
            };
        }
        finally
        {
            // Persisted mate entities and context-specific references can share one RCW identity.
            // They are borrowed aliases; leave them to normal GC instead of invalidating the live model aliases.
            referenceEntity = null; angleEntities = null; hingeSeats = null; hingeAxes = null;
            ReleaseCom(angleData); ReleaseCom(hingeData);
            ReleaseCom(driver); ReleaseCom(hinge);
        }
    }

    private static Dictionary<string, object> RemainingDofs(Component2 component)
    {
        int rp1Status = 0, rd1Status = 0, rp2Status = 0, rd2Status = 0, td1Status = 0, td2Status = 0;
        MathPoint rp1 = null, rp2 = null;
        MathVector rd1 = null, rd2 = null, td1 = null, td2 = null;
        try
        {
            int status = component.GetRemainingDOFs(out rp1Status, out rp1, out rd1Status, out rd1,
                out rp2Status, out rp2, out rd2Status, out rd2,
                out td1Status, out td1, out td2Status, out td2);
            double[] direction = rd1 == null ? null : ToArray(rd1.ArrayData, 3);
            double[] point = rp1 == null ? null : ToArray(rp1.ArrayData, 3);
            Require(status == RemainingDofsRestricted, "GetRemainingDOFs did not return Restricted");
            Require(rp1Status == 1 && rp1 != null && rd1Status == 1 && rd1 != null, "Primary rotational DOF is absent");
            Require(rp2Status == 0 && rp2 == null && rd2Status == 0 && rd2 == null,
                "Unexpected secondary rotational DOF");
            Require(td1Status == 0 && td1 == null && td2Status == 0 && td2 == null,
                "Unexpected translational DOF");
            Require(Math.Abs(Dot(Normalize(direction), new[] { 0.0, 0.0, 1.0 })) >= 1.0 - ReferenceRotationTolerance,
                "Remaining rotational DOF is not aligned with J1 Z");
            double radial = Math.Sqrt(Math.Pow(point[0] - JointX, 2) + Math.Pow(point[1] - JointY, 2));
            Require(radial <= ReferenceTranslationTolerance, "Remaining rotational DOF point is off the J1 axis");
            return new Dictionary<string, object>
            {
                { "return_status", status }, { "rpoint1_status", rp1Status }, { "rpoint1", point },
                { "rdirection1_status", rd1Status }, { "rdirection1", direction },
                { "rpoint2_status", rp2Status }, { "rdirection2_status", rd2Status },
                { "tdirection1_status", td1Status }, { "tdirection2_status", td2Status }
            };
        }
        finally
        {
            ReleaseCom(td2); ReleaseCom(td1); ReleaseCom(rd2); ReleaseCom(rd1);
            ReleaseCom(rp2); ReleaseCom(rp1);
        }
    }

    private static int UnwrapTheta(double wrapped, double commanded, out double unwrapped)
    {
        int bestK = 0;
        double best = Double.PositiveInfinity;
        double bestValue = Double.NaN;
        for (int k = -2; k <= 2; k++)
        {
            double value = wrapped + 2.0 * Math.PI * k;
            if (value < NativeMinimum - JointTolerance || value > NativeMaximum + JointTolerance) continue;
            double error = Math.Abs(value - commanded);
            if (error < best)
            {
                best = error;
                bestK = k;
                bestValue = value;
            }
        }
        Require(!Double.IsNaN(bestValue), "No bounded native angle branch exists");
        unwrapped = bestValue;
        return bestK;
    }

    private static double FkRotationError(double[] transform, double q)
    {
        double c = Math.Cos(q), s = Math.Sin(q);
        double[] expected = { c, s, 0.0, -s, c, 0.0, 0.0, 0.0, 1.0 };
        double trace = 0.0;
        for (int row = 0; row < 3; row++)
            for (int col = 0; col < 3; col++)
                trace += expected[row * 3 + col] * transform[row * 3 + col];
        return Math.Acos(Clamp((trace - 1.0) / 2.0, -1.0, 1.0));
    }

    private static Dictionary<string, object> ReadState(Component2 parent, Component2 child,
        Feature driverFeature, double commandedQ, string sampleId)
    {
        double commandedTheta = commandedQ - Lower;
        double[] parentZero = WorldPlaneNormal(parent, "PLANE_ZERO_joint1_PARENT_SIDE");
        double[] limitReference = WorldPlaneNormal(parent, "PLANE_LIMIT_REF_joint1_PARENT_SIDE");
        double[] childZero = WorldPlaneNormal(child, "PLANE_ZERO_joint1");
        double[][] parentAxisEndpoints = WorldAxisEndpoints(parent, "AXIS_joint1_PARENT_SIDE");
        double[][] childAxisEndpoints = WorldAxisEndpoints(child, "AXIS_joint1");
        double[] parentAxisRaw = Normalize(new[]
        {
            parentAxisEndpoints[1][0] - parentAxisEndpoints[0][0],
            parentAxisEndpoints[1][1] - parentAxisEndpoints[0][1],
            parentAxisEndpoints[1][2] - parentAxisEndpoints[0][2]
        });
        double[] childAxisRaw = Normalize(new[]
        {
            childAxisEndpoints[1][0] - childAxisEndpoints[0][0],
            childAxisEndpoints[1][1] - childAxisEndpoints[0][1],
            childAxisEndpoints[1][2] - childAxisEndpoints[0][2]
        });
        double[] axis = { 0.0, 0.0, 1.0 };
        double parentAxisEndpointSign = Dot(parentAxisRaw, axis) >= 0.0 ? 1.0 : -1.0;
        double[] parentAxisOriented =
        {
            parentAxisEndpointSign * parentAxisRaw[0],
            parentAxisEndpointSign * parentAxisRaw[1],
            parentAxisEndpointSign * parentAxisRaw[2]
        };
        Require(Dot(parentAxisOriented, axis) >= 1.0 - ReferenceRotationTolerance,
            "J01 parent RefAxis is not aligned with frozen world +Z");
        Require(Dot(parentZero, new[] { 0.0, -1.0, 0.0 }) >= 1.0 - ReferenceRotationTolerance,
            "J01 parent zero-plane raw normal changed from frozen world -Y");
        double parentZeroOrientationSign = -1.0;
        double[] parentZeroOriented =
        {
            parentZeroOrientationSign * parentZero[0],
            parentZeroOrientationSign * parentZero[1],
            parentZeroOrientationSign * parentZero[2]
        };
        double qWrapped = Math.Atan2(Dot(axis, Cross(parentZeroOriented, childZero)),
            Dot(parentZeroOriented, childZero));
        double thetaWrapped = Math.Atan2(Dot(axis, Cross(limitReference, childZero)), Dot(limitReference, childZero));
        double thetaUnwrapped;
        int branch = UnwrapTheta(thetaWrapped, commandedTheta, out thetaUnwrapped);
        double reconstructedQ = thetaUnwrapped + Lower;
        double[] transform = ComponentTransform(child);
        double translationError = Math.Sqrt(Math.Pow(transform[9] - JointX, 2) +
            Math.Pow(transform[10] - JointY, 2) + Math.Pow(transform[11] - JointZ, 2));
        double rotationError = FkRotationError(transform, commandedQ);
        double axisDot = Math.Abs(Dot(parentAxisRaw, childAxisRaw));
        double[] parentSeatOrigin = WorldPlaneOrigin(parent, "PLANE_SEAT_joint1_PARENT_SIDE");
        double[] childSeatOrigin = WorldPlaneOrigin(child, "PLANE_SEAT_joint1_CHILD_SIDE");
        double seatResidual = Math.Abs(Dot(axis, new[]
        {
            childSeatOrigin[0] - parentSeatOrigin[0],
            childSeatOrigin[1] - parentSeatOrigin[1],
            childSeatOrigin[2] - parentSeatOrigin[2]
        }));
        Dictionary<string, object> angle = InspectAngleMate(driverFeature);
        double featureAngle = Convert.ToDouble(angle["feature_data_angle_rad"]);

        Require(Math.Abs(reconstructedQ - commandedQ) <= JointTolerance,
            "J01 reconstructed q mismatch at " + sampleId + ": " + reconstructedQ + " != " + commandedQ);
        Require(Math.Abs(qWrapped - commandedQ) <= JointTolerance,
            "J01 zero-plane q mismatch at " + sampleId + ": " + qWrapped + " != " + commandedQ);
        Require(Math.Abs(featureAngle - commandedTheta) <= JointTolerance,
            "J01 feature-data angle mismatch at " + sampleId);
        Require(translationError <= FkTranslationTolerance, "J01 FK translation mismatch at " + sampleId);
        Require(rotationError <= FkRotationTolerance, "J01 FK rotation mismatch at " + sampleId);
        Require(axisDot >= 1.0 - ReferenceRotationTolerance, "J01 axis drift at " + sampleId);
        Require(seatResidual <= ReferenceTranslationTolerance, "J01 seat drift at " + sampleId);

        return new Dictionary<string, object>
        {
            { "sample_id", sampleId }, { "commanded_q_rad", commandedQ },
            { "commanded_native_theta_rad", commandedTheta }, { "feature_data", angle },
            { "q_zero_plane_wrapped_rad", qWrapped }, { "native_theta_wrapped_rad", thetaWrapped },
            { "unwrapped_branch_index", branch }, { "native_theta_unwrapped_rad", thetaUnwrapped },
            { "reconstructed_q_rad", reconstructedQ }, { "joint_error_rad", Math.Abs(reconstructedQ - commandedQ) },
            { "axis_absolute_dot", axisDot }, { "zero_plane_dot", Dot(parentZero, childZero) },
            { "parent_zero_plane_normal_world_raw", parentZero },
            { "parent_zero_plane_orientation_sign_for_q", parentZeroOrientationSign },
            { "parent_zero_plane_normal_world_oriented_for_q", parentZeroOriented },
            { "parent_limit_plane_normal_world_raw", limitReference },
            { "child_zero_plane_normal_world_raw", childZero },
            { "parent_axis_endpoints_world_raw_m", parentAxisEndpoints },
            { "child_axis_endpoints_world_raw_m", childAxisEndpoints },
            { "parent_axis_endpoint_direction_raw", parentAxisRaw },
            { "child_axis_endpoint_direction_raw", childAxisRaw },
            { "parent_axis_endpoint_orientation_sign_to_world_plus_z", parentAxisEndpointSign },
            { "signed_angle_axis_world", axis },
            { "seat_axial_residual_m", seatResidual }, { "component_transform", transform },
            { "fk_translation_error_m", translationError }, { "fk_rotation_error_rad", rotationError }
        };
    }

    private static void Drive(ModelDoc2 model, Feature driverFeature, double q)
    {
        double theta = q - Lower;
        Require(theta >= NativeMinimum - JointTolerance && theta <= NativeMaximum + JointTolerance,
            "Requested J01 q is outside the native limit");
        AngleMateFeatureData data = null;
        try
        {
            data = driverFeature.GetDefinition() as AngleMateFeatureData;
            Require(data != null && data.IsAdvancedMate, "J01 driver definition is unavailable");
            Require(Math.Abs(data.MinimumAngle - NativeMinimum) <= LimitTolerance &&
                Math.Abs(data.MaximumAngle - NativeMaximum) <= LimitTolerance, "J01 limits changed before drive");
            data.Angle = theta;
            Require(driverFeature.ModifyDefinition(data, model, null), "J01 driver ModifyDefinition failed");
        }
        finally { ReleaseCom(data); }
        Require(model.ForceRebuild3(false), "J01 rebuild failed after native angle drive");
    }

    private static List<Dictionary<string, object>> DriveAndSample(ModelDoc2 model, Component2 parent,
        Component2 child, Feature driverFeature, double q, string label)
    {
        Drive(model, driverFeature, q);
        var samples = new List<Dictionary<string, object>>();
        for (int i = 0; i < 10; i++)
        {
            Require(model.ForceRebuild3(false), "J01 repeatability rebuild failed: " + label + "/" + i);
            samples.Add(ReadState(parent, child, driverFeature, q, label + "_R" + i.ToString("D2")));
        }
        return samples;
    }

    private static void SaveAs(ModelDoc2 model, string path, Dictionary<string, object> receipt)
    {
        Require(!File.Exists(path), "Controlled assembly output exists: " + path);
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        int errors = 0, warnings = 0;
        IncrementCounter(receipt, "save_as_call_count");
        Require(model.Extension.SaveAs(path, 0, SaveSilent, null, ref errors, ref warnings), "Assembly SaveAs failed: " + path);
        Require(errors == 0 && warnings == 0, "Assembly SaveAs errors/warnings: " + errors + "/" + warnings);
        Require(File.Exists(path), "Assembly SaveAs output is absent: " + path);
    }

    private static Dictionary<string, object> ComponentRecord(Component2 component)
    {
        return new Dictionary<string, object>
        {
            { "name", component.Name2 }, { "path", component.GetPathName() },
            { "fixed", component.IsFixed() }, { "constrained_status", component.GetConstrainedStatus() },
            { "transform", ComponentTransform(component) }
        };
    }

    private static List<Dictionary<string, object>> MateRecords(ModelDoc2 model,
        Component2 parent, Component2 child)
    {
        string[] names =
        {
            "J00_ROOT_X_COINCIDENT", "J00_ROOT_Y_COINCIDENT", "J00_ROOT_Z_COINCIDENT",
            "J01_HINGE_NATIVE", "J01_LIMIT_ANGLE_DRIVER"
        };
        int[] types = { MateCoincident, MateCoincident, MateCoincident, MateHinge, MateAngle };
        var result = new List<Dictionary<string, object>>();
        for (int i = 0; i < names.Length; i++)
        {
            Feature feature = null;
            try
            {
                feature = FindFeature(model, names[i], null);
                Dictionary<string, object> record;
                if (types[i] == MateAngle) record = InspectAngleMate(feature);
                else if (types[i] == MateHinge) record = InspectHingeMate(feature);
                else record = InspectMate(feature, types[i]);
                record["persisted_mate_entity_binding"] =
                    PersistedMateEntityBindingEvidence(feature, types[i], parent, child);
                result.Add(record);
            }
            finally { ReleaseCom(feature); }
        }
        return result;
    }

    private static void ResolveComponentsByIdentity(AssemblyDoc assembly,
        string parentExpectedPath, long parentExpectedBytes, string parentExpectedSha256,
        string childExpectedPath, long childExpectedBytes, string childExpectedSha256,
        out Component2 parent, out Component2 child,
        List<Dictionary<string, object>> resolutionLedger, Dictionary<string, object> receipt)
    {
        parent = null;
        child = null;
        Require(resolutionLedger != null && resolutionLedger.Count == 0,
            "ColdVerify component-resolution ledger must start empty");
        string parentCanonical = Path.GetFullPath(parentExpectedPath);
        string childCanonical = Path.GetFullPath(childExpectedPath);
        Require(!parentCanonical.Equals(childCanonical, StringComparison.OrdinalIgnoreCase),
            "ColdVerify parent and child expected paths are identical");
        Require(File.Exists(parentCanonical) && new FileInfo(parentCanonical).Length == parentExpectedBytes &&
            Sha256(parentCanonical) == parentExpectedSha256,
            "ColdVerify parent expected identity is not frozen");
        Require(File.Exists(childCanonical) && new FileInfo(childCanonical).Length == childExpectedBytes &&
            Sha256(childCanonical) == childExpectedSha256,
            "ColdVerify child expected identity is not frozen");

        IncrementCounter(receipt, "get_components_call_count");
        Array raw = assembly.GetComponents(true) as Array;
        Require(raw != null, "Assembly has no top-level components");
        int parentCount = 0, childCount = 0;
        foreach (object value in raw)
        {
            Component2 component = value as Component2;
            if (component == null) continue;
            string rawPath = component.GetPathName();
            string canonicalPath = String.IsNullOrWhiteSpace(rawPath) ? null : Path.GetFullPath(rawPath);
            bool exists = canonicalPath != null && File.Exists(canonicalPath);
            long bytes = exists ? new FileInfo(canonicalPath).Length : -1;
            string sha256 = exists ? Sha256(canonicalPath) : null;
            bool parentMatch = canonicalPath != null &&
                canonicalPath.Equals(parentCanonical, StringComparison.OrdinalIgnoreCase) &&
                bytes == parentExpectedBytes && sha256 == parentExpectedSha256;
            bool childMatch = canonicalPath != null &&
                canonicalPath.Equals(childCanonical, StringComparison.OrdinalIgnoreCase) &&
                bytes == childExpectedBytes && sha256 == childExpectedSha256;
            var record = new Dictionary<string, object>
            {
                { "component_name", component.Name2 }, { "raw_path", rawPath },
                { "canonical_path", canonicalPath }, { "file_exists", exists },
                { "bytes", bytes }, { "sha256", sha256 },
                { "matches_parent_identity", parentMatch }, { "matches_child_identity", childMatch }
            };
            resolutionLedger.Add(record);
            Require(!(parentMatch && childMatch), "One component matched both frozen identities");
            if (parentMatch)
            {
                parentCount++;
                if (parent == null) parent = component;
            }
            if (childMatch)
            {
                childCount++;
                if (child == null) child = component;
            }
            // Never FinalRelease a component RCW that matched either target identity.
            if (!parentMatch && !childMatch) ReleaseCom(component);
        }
        Require(parentCount == 1 && childCount == 1 && parent != null && child != null,
            "ColdVerify component identity lookup is not unique: parent=" + parentCount + ", child=" + childCount);
        Require(!SameComIdentity(parent, child), "ColdVerify parent and child resolved to one COM identity");
    }

    [STAThread]
    public static int Create(int expectedProcessId, string assemblyTemplatePath,
        string baseCarrierPath, string link1CarrierPath, string j00AssemblyPath,
        string outputAssemblyPath, string j00CheckpointPath, string receiptPath, string progressPath)
    {
        var preloadOperations = new List<Dictionary<string, object>>();
        var mateApiAttempts = new List<Dictionary<string, object>>();
        var matePreselectionAttempts = new List<Dictionary<string, object>>();
        var receipt = new Dictionary<string, object>
        {
            { "schema", "B51R1_S05R2_J01_R14_NATIVE_PILOT_CREATE_V1" },
            { "status", "FAIL_CLOSED_NOT_STARTED" }, { "generated_at_utc", DateTime.UtcNow.ToString("o") },
            { "expected_process_id", expectedProcessId }, { "save_as_call_count", 0 }, { "save3_call_count", 0 },
            { "create_mate_data_call_count", 0 }, { "create_mate_call_count", 0 }, { "add_mate5_call_count", 0 },
            { "mate_preselection_call_count", 0 }, { "transform2_call_count", 0 },
            { "set_transform_and_solve_call_count", 0 }, { "move_component_call_count", 0 },
            { "preload_operations", preloadOperations }, { "mate_api_attempts", mateApiAttempts },
            { "mate_preselection_attempts", matePreselectionAttempts }
        };
        SldWorks app = null;
        Process process = null;
        ModelDoc2 model = null;
        ModelDoc2 preloadedBase = null, preloadedLink = null;
        string preloadedBaseTitle = null, preloadedLinkTitle = null;
        AssemblyDoc assembly = null;
        Component2 parent = null, child = null;
        Feature driver = null;
        var nativeMateCreations = new List<Dictionary<string, object>>();
        var j00MateCreations = new List<Dictionary<string, object>>();
        string baseBefore = null, linkBefore = null;
        try
        {
            foreach (string path in new[] { j00AssemblyPath, outputAssemblyPath, j00CheckpointPath, receiptPath, progressPath })
                Require(!File.Exists(path), "Append-only Pilot output exists: " + path);
            Require(File.Exists(assemblyTemplatePath), "Assembly template is absent");
            Require(File.Exists(baseCarrierPath) && File.Exists(link1CarrierPath), "MR2 Pilot Carrier input is absent");
            baseBefore = Sha256(baseCarrierPath);
            linkBefore = Sha256(link1CarrierPath);
            app = Attach(expectedProcessId);
            process = Process.GetProcessById(expectedProcessId);
            ProgressCreateNew(progressPath, "J01_R14_CREATE_START " + DateTime.UtcNow.ToString("o"));

            PreloadPart(app, baseCarrierPath, baseBefore, "BASE_MR2", 0, preloadOperations,
                out preloadedBase, out preloadedBaseTitle);
            PreloadPart(app, link1CarrierPath, linkBefore, "LINK1_MR2", 1, preloadOperations,
                out preloadedLink, out preloadedLinkTitle);
            receipt["document_count_before_new_assembly"] = app.GetDocumentCount();
            Require(app.GetDocumentCount() == 2, "Both MR2 parts were not held preloaded before NewDocument");

            model = app.NewDocument(assemblyTemplatePath, 0, 0.0, 0.0) as ModelDoc2;
            Require(model != null && model.GetType() == AssemblyType, "Assembly NewDocument failed");
            receipt["document_count_after_new_assembly"] = app.GetDocumentCount();
            Require(app.GetDocumentCount() == 3, "New assembly did not join the two preloaded documents exactly once");
            assembly = model as AssemblyDoc;
            Require(assembly != null, "IAssemblyDoc cast failed");
            NormalizeAssemblyRootPlanes(model);

            parent = InsertPreloadedComponent(app, model, assembly, baseCarrierPath, 0.0, 0.0, 0.0,
                "BASE_MR2", ref preloadedBase, ref preloadedBaseTitle, preloadOperations[0]);
            string[] axes = { "X", "Y", "Z" };
            for (int i = 0; i < axes.Length; i++)
            {
                string mateName = "J00_ROOT_" + axes[i] + "_COINCIDENT";
                Feature assemblyPlaneFeature = null, rootMate = null;
                RefPlane assemblyPlane = null, componentPlane = null;
                try
                {
                    model.ClearSelection2(true);
                    Require(SelectedObjectCount(model) == 0, "Root-mate selection set is not empty: " + mateName);
                    Dictionary<string, object> attempt = BeginMateAttempt(mateName, MateCoincident,
                        "IRefPlane/IRefPlane", mateApiAttempts);
                    assemblyPlaneFeature = FindFeature(model, "ASM_ROOT_PLN_" + axes[i], "RefPlane");
                    assemblyPlane = SelectMateReference(model, null, assemblyPlaneFeature,
                        "ASM_ROOT_PLN_" + axes[i], "RefPlane", SelectDatumPlane, MateEntityMark,
                        false, mateName + "_ASSEMBLY_PLANE", receipt, attempt, matePreselectionAttempts) as RefPlane;
                    componentPlane = SelectMateReference(model, parent, null,
                        "ROOT_PLN_" + axes[i], "RefPlane", SelectDatumPlane, MateEntityMark,
                        true, mateName + "_BASE_PLANE", receipt, attempt, matePreselectionAttempts) as RefPlane;
                    Dictionary<string, object> creation;
                    rootMate = CreateCoincidentMate(model, assembly, assemblyPlane, componentPlane,
                        mateName, receipt, attempt, out creation);
                    j00MateCreations.Add(creation);
                    nativeMateCreations.Add(creation);
                }
                finally
                {
                    try { model.ClearSelection2(true); } catch { }
                    ReleaseCom(rootMate);
                    componentPlane = null; assemblyPlane = null; assemblyPlaneFeature = null;
                }
            }
            Require(!parent.IsFixed() && parent.GetConstrainedStatus() == FullyConstrained,
                "J00 base must be mate-grounded and not fixed");
            SaveAs(model, j00AssemblyPath, receipt);
            var j00Data = new Dictionary<string, object>
            {
                { "schema", "B51R1_S05R2_J01_R14_J00_ROOT_CHECKPOINT_V1" },
                { "status", "S05R2_J01_R14_J00_ROOT_BASELINE_PASS" },
                { "generated_at_utc", DateTime.UtcNow.ToString("o") }, { "assembly_path", j00AssemblyPath },
                { "base_component", ComponentRecord(parent) }, { "base_carrier_sha256", baseBefore },
                { "automatic_fix_removed", true }, { "native_mate_creation", j00MateCreations },
                { "transform2_call_count", 0 },
                { "hash_persisted_after_normal_application_exit", true }
            };

            child = InsertPreloadedComponent(app, model, assembly, link1CarrierPath, JointX, JointY, JointZ,
                "LINK1_MR2", ref preloadedLink, ref preloadedLinkTitle, preloadOperations[1]);
            Feature hinge = null;
            RefAxis parentAxis = null, childAxis = null, angleReferenceAxis = null;
            RefPlane parentSeat = null, childSeat = null, parentLimit = null, childZero = null;
            try
            {
                model.ClearSelection2(true);
                Require(SelectedObjectCount(model) == 0, "Hinge selection set is not empty");
                Dictionary<string, object> hingeAttempt = BeginMateAttempt("J01_HINGE_NATIVE", MateHinge,
                    "IRefAxis/IRefAxis+IRefPlane/IRefPlane", mateApiAttempts);
                parentAxis = SelectMateReference(model, parent, null, "AXIS_joint1_PARENT_SIDE", "RefAxis",
                    SelectDatumAxis, MateEntityMark, false, "J01_HINGE_PARENT_AXIS", receipt,
                    hingeAttempt, matePreselectionAttempts) as RefAxis;
                childAxis = SelectMateReference(model, child, null, "AXIS_joint1", "RefAxis",
                    SelectDatumAxis, MateEntityMark, true, "J01_HINGE_CHILD_AXIS", receipt,
                    hingeAttempt, matePreselectionAttempts) as RefAxis;
                parentSeat = SelectMateReference(model, parent, null, "PLANE_SEAT_joint1_PARENT_SIDE", "RefPlane",
                    SelectDatumPlane, HingeSeatMark, true, "J01_HINGE_PARENT_SEAT", receipt,
                    hingeAttempt, matePreselectionAttempts) as RefPlane;
                childSeat = SelectMateReference(model, child, null, "PLANE_SEAT_joint1_CHILD_SIDE", "RefPlane",
                    SelectDatumPlane, HingeSeatMark, true, "J01_HINGE_CHILD_SEAT", receipt,
                    hingeAttempt, matePreselectionAttempts) as RefPlane;
                Dictionary<string, object> hingeCreation;
                hinge = CreateHingeMate(model, assembly, parentAxis, childAxis, parentSeat, childSeat,
                    "J01_HINGE_NATIVE", receipt, hingeAttempt, out hingeCreation);
                nativeMateCreations.Add(hingeCreation);
                ReleaseCom(hinge); hinge = null;
                parentAxis = null; childAxis = null; parentSeat = null; childSeat = null;

                model.ClearSelection2(true);
                Require(SelectedObjectCount(model) == 0, "Limit-angle selection set is not empty");
                Dictionary<string, object> angleAttempt = BeginMateAttempt("J01_LIMIT_ANGLE_DRIVER", MateAngle,
                    "IRefPlane/IRefPlane+IRefAxis_REFERENCE", mateApiAttempts);
                parentLimit = SelectMateReference(model, parent, null, "PLANE_LIMIT_REF_joint1_PARENT_SIDE", "RefPlane",
                    SelectDatumPlane, MateEntityMark, false, "J01_LIMIT_PARENT_PLANE", receipt,
                    angleAttempt, matePreselectionAttempts) as RefPlane;
                childZero = SelectMateReference(model, child, null, "PLANE_ZERO_joint1", "RefPlane",
                    SelectDatumPlane, MateEntityMark, true, "J01_LIMIT_CHILD_ZERO_PLANE", receipt,
                    angleAttempt, matePreselectionAttempts) as RefPlane;
                angleReferenceAxis = SelectMateReference(model, parent, null, "AXIS_joint1_PARENT_SIDE", "RefAxis",
                    SelectDatumAxis, AngleReferenceMark, true, "J01_LIMIT_REFERENCE_AXIS", receipt,
                    angleAttempt, matePreselectionAttempts) as RefAxis;
                Dictionary<string, object> driverCreation;
                driver = CreateLimitAngleMate(model, assembly, parentLimit, childZero, angleReferenceAxis,
                    "J01_LIMIT_ANGLE_DRIVER", receipt, angleAttempt, out driverCreation);
                nativeMateCreations.Add(driverCreation);
            }
            finally
            {
                try { model.ClearSelection2(true); } catch { }
                ReleaseCom(hinge);
                childZero = null; parentLimit = null; angleReferenceAxis = null;
                childSeat = null; parentSeat = null; childAxis = null; parentAxis = null;
            }

            Require(!parent.IsFixed() && !child.IsFixed(), "Pilot contains a fixed component");
            Require(parent.GetConstrainedStatus() == FullyConstrained, "J00 base constraint state changed");
            Require(child.GetConstrainedStatus() == UnderConstrained, "J01 child is not under-constrained");
            Dictionary<string, object> remaining = RemainingDofs(child);

            var canonical = new List<Dictionary<string, object>>();
            double[] canonicalQ = { 0.0, OneDegree, 0.0, -OneDegree, 0.0 };
            string[] canonicalNames = { "QPROBE_0", "QPROBE_PLUS_1DEG", "QPROBE_RETURN_1", "QPROBE_MINUS_1DEG", "QPROBE_Q0" };
            for (int i = 0; i < canonicalQ.Length; i++)
                canonical.Add(new Dictionary<string, object>
                {
                    { "state", canonicalNames[i] }, { "samples", DriveAndSample(model, parent, child, driver, canonicalQ[i], canonicalNames[i]) }
                });

            var sweep = new List<Dictionary<string, object>>();
            double[] sweepQ = { -2.8, -2.78, -1.40, 0.0, 1.40, 2.78, 2.8, 0.0 };
            for (int i = 0; i < sweepQ.Length; i++)
            {
                string label = "SWEEP_" + i.ToString("D2");
                sweep.Add(new Dictionary<string, object>
                {
                    { "state", label }, { "samples", DriveAndSample(model, parent, child, driver, sweepQ[i], label) }
                });
            }

            var resets = new List<Dictionary<string, object>>();
            for (int i = 0; i < 10; i++)
            {
                double nonzero = i % 2 == 0 ? OneDegree : -OneDegree;
                Drive(model, driver, nonzero);
                Dictionary<string, object> nonzeroState = ReadState(parent, child, driver, nonzero, "RESET_" + i.ToString("D2") + "_NONZERO");
                Drive(model, driver, 0.0);
                Dictionary<string, object> q0State = ReadState(parent, child, driver, 0.0, "RESET_" + i.ToString("D2") + "_Q0");
                resets.Add(new Dictionary<string, object> { { "cycle", i }, { "nonzero", nonzeroState }, { "q0", q0State } });
            }
            Drive(model, driver, 0.0);
            Dictionary<string, object> finalQ0 = ReadState(parent, child, driver, 0.0, "FINAL_Q0");
            Dictionary<string, object> referenceGeometryFinalQ0 = ReferenceGeometryWitness(parent, child);
            Dictionary<string, object> nativeMateBindingsFinalQ0 = NativeMateBindingWitness(model, parent, child);

            SaveAs(model, outputAssemblyPath, receipt);
            Require(nativeMateCreations.Count == 5, "Native mate creation evidence count is not five");
            Require(Convert.ToInt32(receipt["create_mate_data_call_count"]) == nativeMateCreations.Count &&
                Convert.ToInt32(receipt["create_mate_call_count"]) == nativeMateCreations.Count &&
                mateApiAttempts.Count == nativeMateCreations.Count,
                "Native mate API call ledger does not match successful mate evidence");
            Require(Convert.ToInt32(receipt["mate_preselection_call_count"]) == 13 &&
                matePreselectionAttempts.Count == 13,
                "Native mate preselection ledger does not contain the required 13 SelectByID2 calls");
            receipt["status"] = "S05R2_J01_R14_NATIVE_1R_PILOT_CREATE_PASS";
            receipt["gate_pass"] = true;
            receipt["assembly_template"] = new Dictionary<string, object>
            {
                { "path", assemblyTemplatePath }, { "bytes", new FileInfo(assemblyTemplatePath).Length }, { "sha256", Sha256(assemblyTemplatePath) }
            };
            receipt["input_carriers"] = new object[]
            {
                new Dictionary<string, object> { { "path", baseCarrierPath }, { "sha256_before_after", baseBefore } },
                new Dictionary<string, object> { { "path", link1CarrierPath }, { "sha256_before_after", linkBefore } }
            };
            receipt["components"] = new object[] { ComponentRecord(parent), ComponentRecord(child) };
            receipt["native_mate_creation"] = nativeMateCreations;
            receipt["mates"] = MateRecords(model, parent, child);
            receipt["remaining_dofs"] = remaining;
            receipt["canonical_sign_probe"] = canonical;
            receipt["enhanced_branch_and_limit_sweep"] = sweep;
            receipt["ten_nonzero_to_q0_cycles"] = resets;
            receipt["final_q0"] = finalQ0;
            receipt["reference_geometry_final_q0"] = referenceGeometryFinalQ0;
            receipt["native_mate_bindings_final_q0"] = nativeMateBindingsFinalQ0;
            receipt["j00_checkpoint"] = new Dictionary<string, object>
            {
                { "assembly_path", j00AssemblyPath }, { "hash_pending_until_normal_application_exit", true },
                { "receipt_path", j00CheckpointPath }
            };
            receipt["output"] = new Dictionary<string, object>
            {
                { "path", outputAssemblyPath }, { "bytes", new FileInfo(outputAssemblyPath).Length },
                { "hash_pending_until_normal_application_exit", true }
            };
            receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");

            Require(Sha256(baseCarrierPath) == baseBefore && Sha256(link1CarrierPath) == linkBefore,
                "MR2 Carrier hash changed during Pilot creation");
            string title = model.GetTitle();
            ReleaseCom(driver); driver = null;
            ReleaseCom(child); child = null;
            ReleaseCom(parent); parent = null;
            GC.Collect(); GC.WaitForPendingFinalizers();
            app.CloseDoc(title);
            ReleaseCom(assembly); assembly = null;
            ReleaseCom(model); model = null;
            app.ExitApp();
            ReleaseCom(app); app = null;
            Require(process.WaitForExit(120000), "SOLIDWORKS did not exit normally");
            j00Data["assembly_bytes"] = new FileInfo(j00AssemblyPath).Length;
            j00Data["assembly_sha256"] = Sha256(j00AssemblyPath);
            WriteJsonCreateNew(j00CheckpointPath, j00Data);
            Progress(progressPath, "J00_PASS " + j00Data["assembly_sha256"]);
            var j00Evidence = (Dictionary<string, object>)receipt["j00_checkpoint"];
            j00Evidence["assembly_sha256"] = j00Data["assembly_sha256"];
            j00Evidence["receipt_sha256"] = Sha256(j00CheckpointPath);
            j00Evidence.Remove("hash_pending_until_normal_application_exit");
            var outputEvidence = (Dictionary<string, object>)receipt["output"];
            outputEvidence["sha256"] = Sha256(outputAssemblyPath);
            outputEvidence.Remove("hash_pending_until_normal_application_exit");
            receipt["normal_document_close"] = true;
            receipt["normal_application_exit"] = true;
            WriteJsonCreateNew(receiptPath, receipt);
            Progress(progressPath, "J01_R14_CREATE_PASS " + outputEvidence["sha256"]);
            process.Dispose();
            return 0;
        }
        catch (Exception ex)
        {
            receipt["status"] = "S05R2_J01_R14_NATIVE_1R_PILOT_CREATE_FAIL_CLOSED";
            receipt["gate_pass"] = false;
            receipt["exception_type"] = ex.GetType().FullName;
            receipt["exception"] = ex.ToString();
            try { if (baseBefore != null && File.Exists(baseCarrierPath)) receipt["base_hash_after_failure"] = Sha256(baseCarrierPath); } catch { }
            try { if (linkBefore != null && File.Exists(link1CarrierPath)) receipt["link1_hash_after_failure"] = Sha256(link1CarrierPath); } catch { }
            ReleaseCom(driver); driver = null;
            ReleaseCom(child); child = null;
            ReleaseCom(parent); parent = null;
            GC.Collect(); GC.WaitForPendingFinalizers();
            try { if (app != null && model != null) app.CloseDoc(model.GetTitle()); } catch { }
            try { if (app != null && preloadedBaseTitle != null) app.CloseDoc(preloadedBaseTitle); } catch { }
            try { if (app != null && preloadedLinkTitle != null) app.CloseDoc(preloadedLinkTitle); } catch { }
            ReleaseCom(preloadedBase); preloadedBase = null; preloadedBaseTitle = null;
            ReleaseCom(preloadedLink); preloadedLink = null; preloadedLinkTitle = null;
            try { if (app != null && app.GetDocumentCount() == 0) app.ExitApp(); } catch { }
            try { if (!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath, receipt); } catch { }
            try { if (File.Exists(progressPath)) Progress(progressPath, "J01_R14_CREATE_FAIL " + ex.Message); } catch { }
            return 1;
        }
        finally
        {
            ReleaseCom(driver); ReleaseCom(child); ReleaseCom(parent); ReleaseCom(assembly); ReleaseCom(model);
            ReleaseCom(preloadedBase); ReleaseCom(preloadedLink); ReleaseCom(app);
            if (process != null) process.Dispose();
            GC.Collect(); GC.WaitForPendingFinalizers();
        }
    }

    [STAThread]
    public static int ColdVerify(int expectedProcessId, string assemblyPath,
        string baseCarrierPath, long baseCarrierBytes, string baseCarrierSha256,
        string link1CarrierPath, long link1CarrierBytes, string link1CarrierSha256,
        string receiptPath, string progressPath)
    {
        var componentResolution = new List<Dictionary<string, object>>();
        var receipt = new Dictionary<string, object>
        {
            { "schema", "B51R1_S05R2_J01_R14_NATIVE_PILOT_COLD_REOPEN_V1" },
            { "status", "FAIL_CLOSED_NOT_STARTED" }, { "generated_at_utc", DateTime.UtcNow.ToString("o") },
            { "expected_process_id", expectedProcessId }, { "save_as_call_count", 0 }, { "save3_call_count", 0 },
            { "create_mate_data_call_count", 0 }, { "create_mate_call_count", 0 }, { "add_mate5_call_count", 0 },
            { "mate_preselection_call_count", 0 }, { "transform2_call_count", 0 },
            { "set_transform_and_solve_call_count", 0 }, { "move_component_call_count", 0 },
            { "component_resolution", componentResolution }, { "get_components_call_count", 0 }
        };
        SldWorks app = null;
        Process process = null;
        ModelDoc2 model = null;
        AssemblyDoc assembly = null;
        Component2 parent = null, child = null;
        Feature driver = null;
        try
        {
            Require(!File.Exists(receiptPath) && !File.Exists(progressPath), "Append-only cold-reopen evidence exists");
            Require(File.Exists(assemblyPath), "Pilot assembly is absent");
            string before = Sha256(assemblyPath);
            app = Attach(expectedProcessId);
            process = Process.GetProcessById(expectedProcessId);
            ProgressCreateNew(progressPath, "J01_R14_COLD_REOPEN_START " + DateTime.UtcNow.ToString("o"));
            int errors = 0, warnings = 0;
            model = app.OpenDoc6(assemblyPath, AssemblyType, OpenSilent | OpenReadOnly, "", ref errors, ref warnings) as ModelDoc2;
            receipt["open_errors"] = errors;
            receipt["open_warnings"] = warnings;
            receipt["open_options"] = "SILENT_READ_ONLY";
            Require(model != null && errors == 0 && warnings == 0,
                "Pilot cold reopen failed, errors/warnings=" + errors + "/" + warnings);
            bool openedReadOnly = model.IsOpenedReadOnly();
            receipt["opened_read_only"] = openedReadOnly;
            Require(openedReadOnly, "Pilot cold reopen did not honor the read-only option");
            assembly = model as AssemblyDoc;
            Require(assembly != null, "IAssemblyDoc cast failed on cold reopen");
            receipt["expected_component_identities"] = new object[]
            {
                new Dictionary<string, object>
                {
                    { "role", "parent" }, { "canonical_path", Path.GetFullPath(baseCarrierPath) },
                    { "bytes", baseCarrierBytes }, { "sha256", baseCarrierSha256 }
                },
                new Dictionary<string, object>
                {
                    { "role", "child" }, { "canonical_path", Path.GetFullPath(link1CarrierPath) },
                    { "bytes", link1CarrierBytes }, { "sha256", link1CarrierSha256 }
                }
            };
            ResolveComponentsByIdentity(assembly,
                baseCarrierPath, baseCarrierBytes, baseCarrierSha256,
                link1CarrierPath, link1CarrierBytes, link1CarrierSha256,
                out parent, out child, componentResolution, receipt);
            driver = FindFeature(model, "J01_LIMIT_ANGLE_DRIVER", null);

            Require(!parent.IsFixed() && !child.IsFixed(), "Cold-reopened Pilot contains a fixed component");
            Require(parent.GetConstrainedStatus() == FullyConstrained, "Cold-reopened base is not mate-grounded");
            Require(child.GetConstrainedStatus() == UnderConstrained, "Cold-reopened link1 is not under-constrained");
            Dictionary<string, object> remaining = RemainingDofs(child);
            Dictionary<string, object> initialReferenceGeometry = ReferenceGeometryWitness(parent, child);
            List<Dictionary<string, object>> samples = new List<Dictionary<string, object>>();
            for (int i = 0; i < 10; i++)
            {
                Require(model.ForceRebuild3(false), "Cold-reopen rebuild failed at sample " + i);
                samples.Add(ReadState(parent, child, driver, 0.0, "COLD_Q0_R" + i.ToString("D2")));
            }

            var canonical = new List<Dictionary<string, object>>();
            double[] canonicalQ = { OneDegree, 0.0, -OneDegree, 0.0 };
            string[] canonicalNames = { "COLD_PLUS_1DEG", "COLD_RETURN_1", "COLD_MINUS_1DEG", "COLD_RETURN_2" };
            for (int i = 0; i < canonicalQ.Length; i++)
                canonical.Add(new Dictionary<string, object>
                {
                    { "state", canonicalNames[i] },
                    { "samples", DriveAndSample(model, parent, child, driver, canonicalQ[i], canonicalNames[i]) }
                });

            double branchBoundaryQ = Math.PI - NativeQ0;
            var branchWitnesses = new List<Dictionary<string, object>>();
            double[] branchQ = { -1.4, branchBoundaryQ - 0.01, branchBoundaryQ + 0.01, 1.4, 2.78, 0.0 };
            string[] branchNames =
            {
                "COLD_BRANCH_BELOW_PI_FAR", "COLD_BRANCH_BELOW_PI_NEAR", "COLD_BRANCH_ABOVE_PI_NEAR",
                "COLD_BRANCH_ABOVE_PI_FAR", "COLD_BRANCH_UPPER_NEAR", "COLD_BRANCH_RETURN_Q0"
            };
            for (int i = 0; i < branchQ.Length; i++)
                branchWitnesses.Add(new Dictionary<string, object>
                {
                    { "state", branchNames[i] },
                    { "samples", DriveAndSample(model, parent, child, driver, branchQ[i], branchNames[i]) }
                });

            Drive(model, driver, 0.0);
            Dictionary<string, object> finalQ0 = ReadState(parent, child, driver, 0.0, "COLD_FINAL_Q0");
            Dictionary<string, object> finalRemaining = RemainingDofs(child);
            Dictionary<string, object> finalReferenceGeometry = ReferenceGeometryWitness(parent, child);
            Dictionary<string, object> finalNativeMateBindings = NativeMateBindingWitness(model, parent, child);
            receipt["status"] = "S05R2_J01_R14_NATIVE_1R_PILOT_COLD_REOPEN_PASS";
            receipt["gate_pass"] = true;
            receipt["assembly"] = new Dictionary<string, object>
            {
                { "path", assemblyPath }, { "bytes", new FileInfo(assemblyPath).Length }, { "sha256_before_after", before }
            };
            receipt["components"] = new object[] { ComponentRecord(parent), ComponentRecord(child) };
            receipt["mates"] = MateRecords(model, parent, child);
            receipt["remaining_dofs"] = remaining;
            receipt["q0_samples"] = samples;
            receipt["cold_canonical_sign_probe"] = canonical;
            receipt["cold_branch_witnesses"] = branchWitnesses;
            receipt["branch_boundary_q_rad"] = branchBoundaryQ;
            receipt["final_q0"] = finalQ0;
            receipt["final_remaining_dofs"] = finalRemaining;
            receipt["reference_geometry_initial_q0"] = initialReferenceGeometry;
            receipt["reference_geometry_final_q0"] = finalReferenceGeometry;
            receipt["native_mate_bindings_final_q0"] = finalNativeMateBindings;
            receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");

            string title = model.GetTitle();
            ReleaseCom(driver); driver = null;
            child = null;
            parent = null;
            GC.Collect(); GC.WaitForPendingFinalizers();
            app.CloseDoc(title);
            ReleaseCom(assembly); assembly = null;
            ReleaseCom(model); model = null;
            Require(Sha256(assemblyPath) == before, "Pilot assembly hash changed during read-only cold reopen");
            app.ExitApp();
            ReleaseCom(app); app = null;
            Require(process.WaitForExit(120000), "SOLIDWORKS did not exit normally after cold reopen");
            receipt["normal_document_close"] = true;
            receipt["normal_application_exit"] = true;
            WriteJsonCreateNew(receiptPath, receipt);
            Progress(progressPath, "J01_R14_COLD_REOPEN_PASS " + before);
            process.Dispose();
            return 0;
        }
        catch (Exception ex)
        {
            receipt["status"] = "S05R2_J01_R14_NATIVE_1R_PILOT_COLD_REOPEN_FAIL_CLOSED";
            receipt["gate_pass"] = false;
            receipt["exception_type"] = ex.GetType().FullName;
            receipt["exception"] = ex.ToString();
            ReleaseCom(driver); driver = null;
            child = null;
            parent = null;
            GC.Collect(); GC.WaitForPendingFinalizers();
            try { if (app != null && model != null) app.CloseDoc(model.GetTitle()); } catch { }
            try { if (app != null && app.GetDocumentCount() == 0) app.ExitApp(); } catch { }
            try { if (!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath, receipt); } catch { }
            try { if (File.Exists(progressPath)) Progress(progressPath, "J01_R14_COLD_REOPEN_FAIL " + ex.Message); } catch { }
            return 1;
        }
        finally
        {
            ReleaseCom(driver);
            child = null; parent = null;
            ReleaseCom(assembly); ReleaseCom(model); ReleaseCom(app);
            if (process != null) process.Dispose();
            GC.Collect(); GC.WaitForPendingFinalizers();
        }
    }
}
