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

public static class B51R1A03PropertyWriterQualification
{
    private const int DocumentTypePart = 1;
    private const int OpenSilent = 1;
    private const int OpenReadOnly = 2;

    private static readonly string[,] Properties =
    {
        {"MODEL_ROLE", "KINEMATIC_CARRIER"},
        {"DYNAMIC_AUTHORITY", "ACCEPTED_URDF"},
        {"CAD_MASS_CONTRIBUTION", "ZERO"},
        {"BOM_EXCLUDE", "TRUE"}
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
        Require(app.GetProcessID() == expectedProcessId, "ROT process ID mismatch");
        Require(app.Visible && app.StartupProcessCompleted, "SOLIDWORKS is not ready");
        Require(app.GetDocumentCount() == 0 && app.ActiveDoc == null, "Session is not document-empty");
        return app;
    }

    private static int FeatureCount(ModelDoc2 model)
    {
        int count = 0;
        Feature cursor = null;
        try
        {
            cursor = model.FirstFeature() as Feature;
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
        object raw = ((PartDoc)model).GetBodies2(-1, false);
        Array bodies = raw as Array;
        if (bodies == null) return 0;
        try { return bodies.Length; }
        finally { foreach (object body in bodies) ReleaseCom(body); }
    }

    private static List<Dictionary<string, object>> RunWriter(ModelDoc2 model, string expectedAction)
    {
        var results = new List<Dictionary<string, object>>();
        for (int index = 0; index < Properties.GetLength(0); index++)
        {
            B51R1DocumentTextPropertyResult result =
                B51R1NativeDocumentTextPropertyWriter.EnsureDocumentTextProperty(
                    model, Properties[index, 0], Properties[index, 1]);
            Require(String.Equals(result.Action, expectedAction, StringComparison.Ordinal),
                result.Name + " action=" + result.Action + "; expected=" + expectedAction);
            Require(result.FieldType == 30 && result.ConfigurationDuplicateCount == 0,
                result.Name + " type or configuration scope mismatch");
            results.Add(new Dictionary<string, object>
            {
                {"name", result.Name}, {"value", result.Value}, {"action", result.Action},
                {"field_type", result.FieldType}, {"get6_result", result.Get6Result},
                {"add3_result", result.Add3Result},
                {"configuration_duplicate_count", result.ConfigurationDuplicateCount}
            });
        }
        return results;
    }

    [STAThread]
    public static int CreateFirstPass(
        int expectedProcessId, string templatePath, string outputPartPath, string receiptPath)
    {
        var receipt = new Dictionary<string, object>
        {
            {"schema", "B51R1_A03_PROPERTY_WRITER_FIRST_PASS_RECEIPT_V1"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"status", "FAIL_CLOSED_NOT_STARTED"},
            {"expected_process_id", expectedProcessId},
            {"set2_call_count", 0}
        };
        SldWorks app = null;
        ModelDoc2 model = null;
        Process process = null;
        try
        {
            Require(!File.Exists(outputPartPath) && !File.Exists(receiptPath), "Append-only output exists");
            Require(File.Exists(templatePath), "Part template is absent");
            app = Attach(expectedProcessId);
            process = Process.GetProcessById(expectedProcessId);
            model = app.NewDocument(templatePath, 0, 0, 0) as ModelDoc2;
            Require(model != null && model.GetType() == DocumentTypePart, "Blank part creation failed");
            int featuresBefore = FeatureCount(model);
            int bodiesBefore = BodyCount(model);
            int referencesBefore = model.ListExternalFileReferencesCount2();
            receipt["writer_results"] = RunWriter(model, "ADDED_ONLY_IF_NEW");
            Require(FeatureCount(model) == featuresBefore && BodyCount(model) == bodiesBefore,
                "Property write changed geometry inventory");
            Require(model.ListExternalFileReferencesCount2() == referencesBefore,
                "Property write changed external references");
            int errors = 0, warnings = 0;
            Require(model.Extension.SaveAs(outputPartPath, 0, 1, null, ref errors, ref warnings),
                "SaveAs failed");
            Require(errors == 0 && warnings == 0 && File.Exists(outputPartPath),
                "SaveAs returned errors or warnings");
            receipt["feature_count"] = featuresBefore;
            receipt["body_count"] = bodiesBefore;
            receipt["external_reference_count"] = referencesBefore;
            receipt["save_as_call_count"] = 1;
            receipt["part_bytes"] = new FileInfo(outputPartPath).Length;
            receipt["part_sha256"] = Sha256(outputPartPath);
            app.CloseDoc(model.GetTitle());
            ReleaseCom(model); model = null;
            Require(app.GetDocumentCount() == 0, "Session is not empty after CloseDoc");
            app.ExitApp(); ReleaseCom(app); app = null;
            Require(process.WaitForExit(30000), "Normal ExitApp timed out");
            receipt["normal_document_close"] = true;
            receipt["normal_application_exit"] = true;
            receipt["status"] = "PASS_FIRST_EXECUTION_FOUR_ADDS_SAVED_AND_EXITED";
            receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");
            WriteJsonCreateNew(receiptPath, receipt);
            process.Dispose();
            return 0;
        }
        catch (Exception ex)
        {
            receipt["status"] = "FAIL_CLOSED";
            receipt["error_type"] = ex.GetType().FullName;
            receipt["error_message"] = ex.Message;
            try { if (app != null && model != null) app.CloseDoc(model.GetTitle()); } catch { }
            ReleaseCom(model);
            try { if (app != null && app.GetDocumentCount() == 0) app.ExitApp(); } catch { }
            ReleaseCom(app);
            if (process != null) try { process.WaitForExit(30000); process.Dispose(); } catch { }
            try { if (!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath, receipt); } catch { }
            return 1;
        }
    }

    [STAThread]
    public static int ColdReopenSecondPass(
        int expectedProcessId, string partPath, string expectedSha256, int expectedFeatureCount,
        string receiptPath)
    {
        var receipt = new Dictionary<string, object>
        {
            {"schema", "B51R1_A03_PROPERTY_WRITER_SECOND_PASS_RECEIPT_V1"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"status", "FAIL_CLOSED_NOT_STARTED"},
            {"expected_process_id", expectedProcessId},
            {"set2_call_count", 0}, {"save_api_call_count", 0}
        };
        SldWorks app = null;
        ModelDoc2 model = null;
        Process process = null;
        try
        {
            Require(!File.Exists(receiptPath), "Append-only receipt exists");
            Require(Sha256(partPath) == expectedSha256, "Qualification part hash mismatch before reopen");
            app = Attach(expectedProcessId);
            process = Process.GetProcessById(expectedProcessId);
            int errors = 0, warnings = 0;
            model = app.OpenDoc6(partPath, DocumentTypePart, OpenSilent | OpenReadOnly, "", ref errors, ref warnings);
            Require(model != null && errors == 0 && warnings == 0 && model.IsOpenedReadOnly(),
                "Read-only cold reopen failed");
            Require(FeatureCount(model) == expectedFeatureCount && BodyCount(model) == 0,
                "Cold-reopen feature or body inventory mismatch");
            Require(model.ListExternalFileReferencesCount2() == 0,
                "Cold-reopen external reference count is nonzero");
            receipt["writer_results"] = RunWriter(model, "NO_OP_EXACT_MATCH");
            Require(FeatureCount(model) == expectedFeatureCount && BodyCount(model) == 0,
                "Second execution changed geometry inventory");
            app.CloseDoc(model.GetTitle());
            ReleaseCom(model); model = null;
            Require(Sha256(partPath) == expectedSha256, "Qualification part changed during second execution");
            app.ExitApp(); ReleaseCom(app); app = null;
            Require(process.WaitForExit(30000), "Normal ExitApp timed out");
            receipt["feature_count"] = expectedFeatureCount;
            receipt["body_count"] = 0;
            receipt["external_reference_count"] = 0;
            receipt["part_sha256_before_and_after"] = expectedSha256;
            receipt["normal_document_close"] = true;
            receipt["normal_application_exit"] = true;
            receipt["status"] = "PASS_COLD_REOPEN_SECOND_EXECUTION_FOUR_NO_OPS_HASH_STABLE";
            receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");
            WriteJsonCreateNew(receiptPath, receipt);
            process.Dispose();
            return 0;
        }
        catch (Exception ex)
        {
            receipt["status"] = "FAIL_CLOSED";
            receipt["error_type"] = ex.GetType().FullName;
            receipt["error_message"] = ex.Message;
            try { if (app != null && model != null) app.CloseDoc(model.GetTitle()); } catch { }
            ReleaseCom(model);
            try { if (app != null && app.GetDocumentCount() == 0) app.ExitApp(); } catch { }
            ReleaseCom(app);
            if (process != null) try { process.WaitForExit(30000); process.Dispose(); } catch { }
            try { if (!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath, receipt); } catch { }
            return 1;
        }
    }
}
