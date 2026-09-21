using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static class B51R1S01CR02LegacyConfigPropertyProbe
{
    private const int DocumentTypePart = 1;
    private const int OpenSilent = 1;
    private const int OpenReadOnly = 2;
    private const int ExitTimeoutMilliseconds = 30000;

    private static readonly string[] RequiredConfigurations =
    {
        "COMMON_CANONICAL",
        "MODE_A_EVALUATION",
        "MODE_B_EVALUATION"
    };

    private static readonly string[] RepairPropertyNames =
    {
        "G1B_RECEIPT_SHA256",
        "FINAL_INPUT_LOCK_SHA256",
        "PANEL_PRIMARY_LOAD_CREDIT",
        "PANEL_ATTACHMENT_CREDIT",
        "PANEL_PHYSICAL_CONTACT_CREDIT"
    };

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static string Sha256(string path)
    {
        using (FileStream stream = File.OpenRead(path))
        using (SHA256 digest = SHA256.Create())
            return BitConverter.ToString(digest.ComputeHash(stream)).Replace("-", "");
    }

    private static void Progress(string path, string stage)
    {
        File.AppendAllText(
            path,
            DateTime.UtcNow.ToString("o") + "|" + stage + System.Environment.NewLine,
            new UTF8Encoding(false));
    }

    private static void WriteJsonCreateNew(string path, Dictionary<string, object> data)
    {
        using (FileStream stream = new FileStream(
            path, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
        using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false)))
        {
            writer.Write(new JavaScriptSerializer { MaxJsonLength = Int32.MaxValue }
                .Serialize(data));
            writer.WriteLine();
        }
    }

    private static void ReleaseCom(object value)
    {
        if (value == null || !Marshal.IsComObject(value)) return;
        try { Marshal.FinalReleaseComObject(value); }
        catch { }
    }

    private static SldWorks Attach(int expectedProcessId)
    {
        DateTime deadline = DateTime.UtcNow.AddSeconds(30);
        Exception last = null;
        while (DateTime.UtcNow < deadline)
        {
            try
            {
                SldWorks app = (SldWorks)Marshal.GetActiveObject("SldWorks.Application");
                if (app != null && app.GetProcessID() == expectedProcessId &&
                    app.Visible && app.StartupProcessCompleted)
                    return app;
                ReleaseCom(app);
            }
            catch (Exception ex) { last = ex; }
            Thread.Sleep(500);
        }
        throw new InvalidOperationException("Could not attach expected SolidWorks process", last);
    }

    [STAThread]
    public static int Run(
        string targetPath,
        string receiptPath,
        string progressPath,
        int expectedProcessId,
        string expectedTargetSha256)
    {
        var receipt = new Dictionary<string, object>
        {
            {"schema", "B51R1_S01_CR02_LEGACY_CONFIG_PROPERTY_PROBE_V1"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"status", "FAIL_CLOSED_NOT_STARTED"},
            {"target_path", targetPath},
            {"expected_process_id", expectedProcessId},
            {"open_mode", "SILENT_READ_ONLY"},
            {"save_api_call_count", 0},
            {"enumeration_api", "IModelDoc2.GetCustomInfoNames2"}
        };
        SldWorks app = null;
        ModelDoc2 model = null;
        Process process = null;
        string stage = "PRECONDITIONS";
        try
        {
            Require(!File.Exists(receiptPath), "Receipt already exists");
            Require(!File.Exists(progressPath), "Progress log already exists");
            Require(File.Exists(targetPath), "Probe target is absent");
            Require(String.Equals(
                Sha256(targetPath), expectedTargetSha256, StringComparison.OrdinalIgnoreCase),
                "Probe target hash mismatch");
            Progress(progressPath, stage);

            Process[] processes = Process.GetProcessesByName("SLDWORKS");
            try
            {
                Require(processes.Length == 1, "Expected exactly one SLDWORKS process");
                processes[0].Refresh();
                Require(processes[0].Id == expectedProcessId && processes[0].Responding &&
                    processes[0].MainWindowHandle != IntPtr.Zero,
                    "Expected process is not sole visible and responsive");
                process = Process.GetProcessById(expectedProcessId);
            }
            finally
            {
                foreach (Process item in processes) item.Dispose();
            }

            stage = "ATTACH";
            Progress(progressPath, stage);
            app = Attach(expectedProcessId);
            Require(app.GetDocumentCount() == 0 && app.ActiveDoc == null,
                "SolidWorks is not document-empty");

            stage = "OPEN_READ_ONLY";
            Progress(progressPath, stage);
            int errors = 0;
            int warnings = 0;
            model = app.OpenDoc6(
                targetPath, DocumentTypePart, OpenSilent | OpenReadOnly, "",
                ref errors, ref warnings);
            Require(model != null && errors == 0 && warnings == 0,
                "Read-only OpenDoc6 failed");
            Require(model.IsOpenedReadOnly(), "Probe target is not read-only");

            var configurationEvidence = new List<Dictionary<string, object>>();
            foreach (string configuration in RequiredConfigurations)
            {
                stage = "LEGACY_CONFIG_ENUM_" + configuration;
                Progress(progressPath, stage);
                Array rawNames = model.GetCustomInfoNames2(configuration) as Array;
                var names = new List<string>();
                if (rawNames != null)
                {
                    foreach (object rawName in rawNames)
                        names.Add(Convert.ToString(rawName));
                }
                string[] duplicates = names.Where(name =>
                    RepairPropertyNames.Contains(name, StringComparer.Ordinal)).ToArray();
                Require(duplicates.Length == 0,
                    "Repair property exists at configuration level " + configuration +
                    ": " + String.Join(",", duplicates));
                configurationEvidence.Add(new Dictionary<string, object>
                {
                    {"configuration", configuration},
                    {"legacy_count2", model.GetCustomInfoCount2(configuration)},
                    {"enumerated_names", names},
                    {"repair_property_duplicate_count", duplicates.Length}
                });
            }

            stage = "LEGACY_DOCUMENT_ENUM";
            Progress(progressPath, stage);
            Array rawDocumentNames = model.GetCustomInfoNames2("") as Array;
            var documentNames = new List<string>();
            if (rawDocumentNames != null)
            {
                foreach (object rawName in rawDocumentNames)
                    documentNames.Add(Convert.ToString(rawName));
            }
            var repairProperties = new List<Dictionary<string, object>>();
            foreach (string name in RepairPropertyNames)
            {
                repairProperties.Add(new Dictionary<string, object>
                {
                    {"name", name},
                    {"present", documentNames.Contains(name, StringComparer.Ordinal)},
                    {"type", model.GetCustomInfoType3("", name)},
                    {"value", model.get_CustomInfo2("", name)}
                });
            }

            stage = "CLOSE_WITHOUT_SAVE";
            Progress(progressPath, stage);
            app.CloseDoc(model.GetTitle());
            ReleaseCom(model);
            model = null;
            Require(app.GetDocumentCount() == 0 && app.ActiveDoc == null,
                "SolidWorks is not document-empty after CloseDoc");
            Require(String.Equals(
                Sha256(targetPath), expectedTargetSha256, StringComparison.OrdinalIgnoreCase),
                "Probe target changed during read-only inspection");

            stage = "NORMAL_EXIT";
            Progress(progressPath, stage);
            app.ExitApp();
            ReleaseCom(app);
            app = null;
            GC.Collect();
            GC.WaitForPendingFinalizers();
            Require(process.WaitForExit(ExitTimeoutMilliseconds),
                "SolidWorks did not exit normally within 30 seconds");
            Require(Process.GetProcessesByName("SLDWORKS").Length == 0,
                "SolidWorks process remains after normal exit");

            receipt["status"] = "PASS_LEGACY_CONFIG_PROPERTY_SCOPE_READ_ONLY";
            receipt["configuration_evidence"] = configurationEvidence;
            receipt["document_property_count"] = documentNames.Count;
            receipt["document_property_names"] = documentNames;
            receipt["repair_properties"] = repairProperties;
            receipt["target_sha256_after"] = Sha256(targetPath);
            receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");
            Progress(progressPath, "PASS");
            WriteJsonCreateNew(receiptPath, receipt);
            process.Dispose();
            return 0;
        }
        catch (Exception ex)
        {
            receipt["status"] = "FAIL_CLOSED";
            receipt["failed_stage"] = stage;
            receipt["error_type"] = ex.GetType().FullName;
            receipt["error_message"] = ex.Message;
            try { Progress(progressPath, "FAIL_" + stage); } catch { }
            try
            {
                if (app != null && model != null) app.CloseDoc(model.GetTitle());
            }
            catch { }
            ReleaseCom(model);
            try
            {
                if (app != null && app.GetDocumentCount() == 0) app.ExitApp();
            }
            catch { }
            ReleaseCom(app);
            try
            {
                if (process != null)
                {
                    receipt["normal_exit_if_available"] =
                        process.WaitForExit(ExitTimeoutMilliseconds);
                    process.Dispose();
                }
            }
            catch { }
            if (!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath, receipt);
            return 1;
        }
    }
}
