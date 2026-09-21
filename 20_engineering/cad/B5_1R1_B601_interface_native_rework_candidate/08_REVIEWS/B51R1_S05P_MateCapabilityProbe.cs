using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static class B51R1S05PMateCapabilityProbe
{
    private const int PartType = 1;
    private const int OpenSilent = 1;
    private const int OpenReadOnly = 2;

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
        object raw = model.FeatureManager.GetFeatures(true);
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

    private static Dictionary<string, object> InspectPart(
        SldWorks app, string path, string[] requiredPresent, string[] requiredAbsent)
    {
        int errors = 0, warnings = 0;
        ModelDoc2 model = null;
        try
        {
            model = app.OpenDoc6(path, PartType, OpenSilent | OpenReadOnly, "", ref errors, ref warnings) as ModelDoc2;
            Require(model != null && errors == 0, "Read-only open failed: " + path + ", errors=" + errors);
            Require(model.GetType() == PartType, "Unexpected document type: " + path);

            var inventory = new List<Dictionary<string, object>>();
            var byName = new Dictionary<string, string>(StringComparer.Ordinal);
            Feature[] features = TopLevelFeatures(model);
            try
            {
                foreach (Feature feature in features)
                {
                    string name = feature.Name;
                    string type = feature.GetTypeName2();
                    inventory.Add(new Dictionary<string, object> { { "name", name }, { "type", type } });
                    if (!byName.ContainsKey(name)) byName.Add(name, type);
                }
            }
            finally { foreach (Feature feature in features) ReleaseCom(feature); }

            foreach (string name in requiredPresent)
                Require(byName.ContainsKey(name), "Expected feature is absent: " + name);
            foreach (string name in requiredAbsent)
                Require(!byName.ContainsKey(name), "Expected architecture gap is no longer present: " + name);

            Array bodies = ((PartDoc)model).GetBodies2(-1, false) as Array;
            int bodyCount = bodies == null ? 0 : bodies.Length;
            if (bodies != null) foreach (object body in bodies) ReleaseCom(body);
            Require(bodyCount == 0, "Capability probe requires zero-body Carrier");

            return new Dictionary<string, object>
            {
                { "path", Path.GetFullPath(path) },
                { "open_errors", errors }, { "open_warnings", warnings },
                { "feature_count", inventory.Count }, { "body_count", bodyCount },
                { "required_present", requiredPresent },
                { "required_absent_confirmed", requiredAbsent },
                { "feature_inventory", inventory }
            };
        }
        finally
        {
            if (model != null)
            {
                string title = model.GetTitle();
                app.CloseDoc(title);
                ReleaseCom(model);
            }
        }
    }

    [STAThread]
    public static int Run(int expectedProcessId, string baseCarrierPath,
        string link1CarrierPath, string receiptPath)
    {
        var receipt = new Dictionary<string, object>
        {
            { "schema", "B51R1_S05P_MATE_CAPABILITY_PROBE_V1" },
            { "status", "FAIL_CLOSED_NOT_STARTED" },
            { "generated_at_utc", DateTime.UtcNow.ToString("o") },
            { "expected_process_id", expectedProcessId },
            { "save3_call_count", 0 }, { "save_as_call_count", 0 }
        };
        SldWorks app = null;
        Process process = null;
        string baseBefore = null, link1Before = null;
        try
        {
            Require(!File.Exists(receiptPath), "Append-only receipt already exists");
            baseBefore = Sha256(baseCarrierPath);
            link1Before = Sha256(link1CarrierPath);
            app = Attach(expectedProcessId);

            Dictionary<string, object> parent = InspectPart(app, baseCarrierPath,
                new[] { "CS_JOINT_joint1_PARENT_SIDE" },
                new[] { "AXIS_joint1_PARENT_SIDE", "PLANE_SEAT_joint1_PARENT_SIDE", "PLANE_ZERO_joint1_PARENT_SIDE" });
            Dictionary<string, object> child = InspectPart(app, link1CarrierPath,
                new[] { "CS_JOINT_joint1_CHILD_SIDE", "AXIS_joint1", "PLANE_ZERO_joint1" },
                new[] { "PLANE_SEAT_joint1_CHILD_SIDE" });

            string baseAfter = Sha256(baseCarrierPath);
            string link1After = Sha256(link1CarrierPath);
            Require(baseAfter == baseBefore && link1After == link1Before,
                "Protected Carrier hash changed during read-only probe");

            receipt["status"] = "S05P_ARCHITECTURE_HOLD_CONFIRMED";
            receipt["gate_pass"] = false;
            receipt["native_1r_constructible_from_current_features"] = false;
            receipt["parent_carrier"] = parent;
            receipt["child_carrier"] = child;
            receipt["required_native_1r_entity_pairs"] = new object[]
            {
                new Dictionary<string, object> { { "mate", "CONCENTRIC_ROTATION_UNLOCKED" }, { "parent", "AXIS_joint1_PARENT_SIDE" }, { "child", "AXIS_joint1" }, { "missing", new[] { "AXIS_joint1_PARENT_SIDE" } } },
                new Dictionary<string, object> { { "mate", "AXIAL_COINCIDENT" }, { "parent", "PLANE_SEAT_joint1_PARENT_SIDE" }, { "child", "PLANE_SEAT_joint1_CHILD_SIDE" }, { "missing", new[] { "PLANE_SEAT_joint1_PARENT_SIDE", "PLANE_SEAT_joint1_CHILD_SIDE" } } },
                new Dictionary<string, object> { { "mate", "NATIVE_LIMIT_ANGLE_UNIQUE_DRIVER" }, { "parent", "PLANE_ZERO_joint1_PARENT_SIDE" }, { "child", "PLANE_ZERO_joint1" }, { "missing", new[] { "PLANE_ZERO_joint1_PARENT_SIDE" } } }
            };
            receipt["coordinate_system_fallback"] = "PROHIBITED_FULLY_CONSTRAINS_ORIENTATION_NOT_1R";
            receipt["required_recovery"] = "VERSIONED_MATE_READY_CARRIERS_THEN_COLD_REOPEN_GATE";
            receipt["protected_hashes_before_after"] = new object[]
            {
                new Dictionary<string, object> { { "path", Path.GetFullPath(baseCarrierPath) }, { "before", baseBefore }, { "after", baseAfter } },
                new Dictionary<string, object> { { "path", Path.GetFullPath(link1CarrierPath) }, { "before", link1Before }, { "after", link1After } }
            };
            receipt["normal_document_close"] = true;
            receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");
            WriteJsonCreateNew(receiptPath, receipt);

            process = Process.GetProcessById(expectedProcessId);
            app.ExitApp();
            Require(process.WaitForExit(120000), "SOLIDWORKS did not exit normally");
            return 0;
        }
        catch (Exception ex)
        {
            receipt["status"] = "S05P_PROBE_EXCEPTION";
            receipt["exception_type"] = ex.GetType().FullName;
            receipt["exception"] = ex.ToString();
            if (baseBefore != null && File.Exists(baseCarrierPath))
                receipt["base_hash_after_exception"] = Sha256(baseCarrierPath);
            if (link1Before != null && File.Exists(link1CarrierPath))
                receipt["link1_hash_after_exception"] = Sha256(link1CarrierPath);
            try { if (!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath, receipt); } catch { }
            try { if (app != null) app.ExitApp(); } catch { }
            return 1;
        }
        finally
        {
            ReleaseCom(app);
            if (process != null) process.Dispose();
            GC.Collect(); GC.WaitForPendingFinalizers();
        }
    }
}
