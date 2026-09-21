using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static class B51R1S03PPilotCarrierBuilder
{
    private const int PartType = 1;
    private const int OpenSilent = 1;
    private const int OpenReadOnly = 2;
    private const double Tolerance = 1.0e-9;
    private const string UrdfSha = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164";

    private static readonly string[,] Properties =
    {
        {"MODEL_ROLE", "KINEMATIC_CARRIER"},
        {"DYNAMIC_AUTHORITY", "ACCEPTED_URDF"},
        {"CAD_MASS_CONTRIBUTION", "ZERO"},
        {"BOM_EXCLUDE", "TRUE"},
        {"SOURCE_URDF_SHA256", UrdfSha}
    };

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

    private static Feature AddCoordinateSystem(ModelDoc2 model, string name,
        double x, double y, double z, double rx, double ry, double rz)
    {
        bool rotate = Math.Abs(rx) + Math.Abs(ry) + Math.Abs(rz) > 1.0e-15;
        Feature feature = model.FeatureManager.CreateCoordinateSystemUsingNumericalValues(
            true, x, y, z, rotate, rx, ry, rz);
        Require(feature != null, "Coordinate-system creation failed: " + name);
        feature.Name = name;
        return feature;
    }

    private static int FeatureCount(ModelDoc2 model)
    {
        int count = 0;
        Feature cursor = model.FirstFeature() as Feature;
        try
        {
            while (cursor != null)
            {
                count++;
                Feature next = cursor.GetNextFeature() as Feature;
                ReleaseCom(cursor);
                cursor = next;
            }
            return count;
        }
        finally { ReleaseCom(cursor); }
    }

    private static int BodyCount(ModelDoc2 model)
    {
        Array bodies = ((PartDoc)model).GetBodies2(-1, false) as Array;
        if (bodies == null) return 0;
        try { return bodies.Length; }
        finally { foreach (object body in bodies) ReleaseCom(body); }
    }

    private static List<Dictionary<string, object>> RunProperties(ModelDoc2 model, string expectedAction)
    {
        var results = new List<Dictionary<string, object>>();
        for (int i = 0; i < Properties.GetLength(0); i++)
        {
            B51R1DocumentTextPropertyResult result =
                B51R1NativeDocumentTextPropertyWriter.EnsureDocumentTextProperty(
                    model, Properties[i, 0], Properties[i, 1]);
            Require(result.Action == expectedAction, result.Name + " action mismatch");
            results.Add(new Dictionary<string, object>
            {
                {"name", result.Name}, {"value", result.Value}, {"action", result.Action},
                {"field_type", result.FieldType},
                {"configuration_duplicate_count", result.ConfigurationDuplicateCount}
            });
        }
        return results;
    }

    private static double[] ToArray(object raw)
    {
        Array input = raw as Array;
        Require(input != null && input.Length == 16, "Expected 16 transform values");
        double[] output = new double[16];
        int index = 0;
        foreach (object value in input) output[index++] = Convert.ToDouble(value);
        return output;
    }

    private static Dictionary<string, object> ReadCoordinateSystem(
        ModelDoc2 model, string name, double[] expected)
    {
        Feature cursor = model.FirstFeature() as Feature;
        Feature match = null;
        int count = 0;
        try
        {
            while (cursor != null)
            {
                Feature next = cursor.GetNextFeature() as Feature;
                if (cursor.Name == name && cursor.GetTypeName2() == "CoordSys")
                {
                    count++;
                    if (match == null) { match = cursor; cursor = null; }
                }
                ReleaseCom(cursor);
                cursor = next;
            }
            Require(count == 1 && match != null, "Expected one coordinate system: " + name);
            ModelDocExtension extension = model.Extension;
            MathTransform transform = null;
            try
            {
                transform = extension.GetCoordinateSystemTransformByName(name);
                Require(transform != null, "Named transform unavailable: " + name);
                double[] values = ToArray(transform.ArrayData);
                double error = 0.0;
                for (int i = 0; i < 16; i++) error = Math.Max(error, Math.Abs(values[i] - expected[i]));
                Require(error <= Tolerance, name + " transform error=" + error);
                return new Dictionary<string, object>
                {
                    {"name", name}, {"raw_local_to_model_transform", values},
                    {"maximum_absolute_error", error}
                };
            }
            finally { ReleaseCom(transform); ReleaseCom(extension); }
        }
        finally { ReleaseCom(match); ReleaseCom(cursor); }
    }

    [STAThread]
    public static int Create(int expectedProcessId, string templatePath, string outputPath, string receiptPath)
    {
        var receipt = new Dictionary<string, object>
        {
            {"schema", "B51R1_S03P_PILOT_CARRIER_CREATE_RECEIPT_V1"},
            {"status", "FAIL_CLOSED_NOT_STARTED"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"expected_process_id", expectedProcessId}, {"save_as_call_count", 0}
        };
        SldWorks app = null; ModelDoc2 model = null; Process process = null;
        try
        {
            Require(!File.Exists(outputPath) && !File.Exists(receiptPath), "Append-only output exists");
            app = Attach(expectedProcessId); process = Process.GetProcessById(expectedProcessId);
            model = app.NewDocument(templatePath, 0, 0, 0) as ModelDoc2;
            Require(model != null && model.GetType() == PartType, "New part failed");
            int initialFeatureCount = FeatureCount(model);
            Feature a = AddCoordinateSystem(model, "CS_LINK_base_link", 0, 0, 0, 0, 0, 0);
            Feature b = AddCoordinateSystem(model, "CS_JOINT_joint1_PARENT_SIDE", -8.416e-5, 0, 0.08465, 0, 0, 0);
            Feature c = AddCoordinateSystem(model, "CS_VISUAL_MOUNT_base_link", 0, 0, 0, 0, 0, 0);
            ReleaseCom(a); ReleaseCom(b); ReleaseCom(c);
            receipt["property_results"] = RunProperties(model, "ADDED_ONLY_IF_NEW");
            Require(BodyCount(model) == 0 && model.ListExternalFileReferencesCount2() == 0,
                "Pilot is not zero-body and reference-free");
            Require(FeatureCount(model) == initialFeatureCount + 3,
                "Pilot feature count did not increase by exactly three");
            int errors = 0, warnings = 0;
            Require(model.Extension.SaveAs(outputPath, 0, 1, null, ref errors, ref warnings), "SaveAs failed");
            Require(errors == 0 && warnings == 0, "SaveAs errors or warnings");
            receipt["save_as_call_count"] = 1;
            receipt["feature_count"] = FeatureCount(model);
            receipt["body_count"] = 0;
            receipt["external_reference_count"] = 0;
            app.CloseDoc(model.GetTitle()); ReleaseCom(model); model = null;
            app.ExitApp(); ReleaseCom(app); app = null;
            Require(process.WaitForExit(30000), "Normal ExitApp timed out");
            receipt["part_bytes"] = new FileInfo(outputPath).Length;
            receipt["part_sha256"] = Sha256(outputPath);
            receipt["normal_document_close"] = true;
            receipt["normal_application_exit"] = true;
            receipt["status"] = "S03P_BASE_LINK_PILOT_CREATED";
            receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");
            WriteJsonCreateNew(receiptPath, receipt); process.Dispose(); return 0;
        }
        catch (Exception ex)
        {
            receipt["status"] = "FAIL_CLOSED"; receipt["error_type"] = ex.GetType().FullName;
            receipt["error_message"] = ex.Message;
            try { if (app != null && model != null) app.CloseDoc(model.GetTitle()); } catch { }
            ReleaseCom(model); try { if (app != null && app.GetDocumentCount() == 0) app.ExitApp(); } catch { }
            ReleaseCom(app); if (process != null) try { process.WaitForExit(30000); process.Dispose(); } catch { }
            try { if (!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath, receipt); } catch { }
            return 1;
        }
    }

    [STAThread]
    public static int Verify(int expectedProcessId, string partPath, string expectedSha,
        int expectedFeatureCount, string receiptPath)
    {
        var receipt = new Dictionary<string, object>
        {
            {"schema", "B51R1_S04P_PILOT_CARRIER_COLD_REOPEN_RECEIPT_V1"},
            {"status", "FAIL_CLOSED_NOT_STARTED"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"expected_process_id", expectedProcessId}, {"save_api_call_count", 0}
        };
        SldWorks app = null; ModelDoc2 model = null; Process process = null;
        try
        {
            Require(!File.Exists(receiptPath) && Sha256(partPath) == expectedSha, "Precondition failed");
            app = Attach(expectedProcessId); process = Process.GetProcessById(expectedProcessId);
            int errors = 0, warnings = 0;
            model = app.OpenDoc6(partPath, PartType, OpenSilent | OpenReadOnly, "", ref errors, ref warnings);
            Require(model != null && errors == 0 && warnings == 0 && model.IsOpenedReadOnly(),
                "Read-only cold reopen failed");
            Require(FeatureCount(model) == expectedFeatureCount && BodyCount(model) == 0,
                "Pilot inventory mismatch");
            Require(model.ListExternalFileReferencesCount2() == 0, "External reference count is nonzero");
            receipt["property_results"] = RunProperties(model, "NO_OP_EXACT_MATCH");
            double[] identity = {1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0};
            double[] joint = {1,0,0,0,1,0,0,0,1,-8.416e-5,0,0.08465,1,0,0,0};
            receipt["coordinate_systems"] = new object[]
            {
                ReadCoordinateSystem(model, "CS_LINK_base_link", identity),
                ReadCoordinateSystem(model, "CS_JOINT_joint1_PARENT_SIDE", joint),
                ReadCoordinateSystem(model, "CS_VISUAL_MOUNT_base_link", identity)
            };
            app.CloseDoc(model.GetTitle()); ReleaseCom(model); model = null;
            Require(Sha256(partPath) == expectedSha, "Pilot changed during read-only verification");
            app.ExitApp(); ReleaseCom(app); app = null;
            Require(process.WaitForExit(30000), "Normal ExitApp timed out");
            receipt["feature_count"] = expectedFeatureCount;
            receipt["body_count"] = 0;
            receipt["external_reference_count"] = 0;
            receipt["part_sha256_before_and_after"] = expectedSha;
            receipt["normal_document_close"] = true;
            receipt["normal_application_exit"] = true;
            receipt["status"] = "S04P_BASE_LINK_PILOT_COLD_REOPEN_PASS";
            receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");
            WriteJsonCreateNew(receiptPath, receipt); process.Dispose(); return 0;
        }
        catch (Exception ex)
        {
            receipt["status"] = "FAIL_CLOSED"; receipt["error_type"] = ex.GetType().FullName;
            receipt["error_message"] = ex.Message;
            try { if (app != null && model != null) app.CloseDoc(model.GetTitle()); } catch { }
            ReleaseCom(model); try { if (app != null && app.GetDocumentCount() == 0) app.ExitApp(); } catch { }
            ReleaseCom(app); if (process != null) try { process.WaitForExit(30000); process.Dispose(); } catch { }
            try { if (!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath, receipt); } catch { }
            return 1;
        }
    }
}
