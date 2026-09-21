using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static class B51R1S02R2ConfigurationActivationProbe
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

    private static string ActiveConfigurationName(ModelDoc2 model)
    {
        ConfigurationManager manager = null;
        Configuration configuration = null;
        try
        {
            manager = model.ConfigurationManager;
            Require(manager != null, "ConfigurationManager is unavailable");
            configuration = manager.ActiveConfiguration;
            Require(configuration != null, "ActiveConfiguration is unavailable");
            return configuration.Name;
        }
        finally
        {
            ReleaseCom(configuration);
            ReleaseCom(manager);
        }
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
            {"schema", "B51R1_S02_R2_CONFIGURATION_ACTIVATION_PROBE_V1"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"status", "S02_R2_FAIL_CLOSED_NOT_STARTED"},
            {"target_path", targetPath},
            {"expected_process_id", expectedProcessId},
            {"open_mode", "SILENT_READ_ONLY"},
            {"save_api_call_count", 0},
            {"activation_policy", "SKIP_SHOW_CONFIGURATION_IF_ALREADY_ACTIVE"}
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
            Require(String.Equals(Sha256(targetPath), expectedTargetSha256,
                StringComparison.OrdinalIgnoreCase), "Probe target hash mismatch");
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

            stage = "READ_INITIAL_ACTIVE_CONFIGURATION";
            Progress(progressPath, stage);
            string initialConfiguration = ActiveConfigurationName(model);
            receipt["initial_active_configuration"] = initialConfiguration;
            var transitions = new List<Dictionary<string, object>>();

            foreach (string targetConfiguration in RequiredConfigurations)
            {
                string before = ActiveConfigurationName(model);
                bool showCalled = !String.Equals(
                    before, targetConfiguration, StringComparison.Ordinal);
                stage = "ACTIVATE_" + targetConfiguration;
                if (showCalled)
                {
                    Progress(progressPath, "BEFORE_SHOW_" + before + "_TO_" +
                        targetConfiguration);
                    Require(model.ShowConfiguration2(targetConfiguration),
                        "ShowConfiguration2 failed for " + targetConfiguration);
                    Progress(progressPath, "AFTER_SHOW_" + targetConfiguration);
                }
                else
                {
                    Progress(progressPath, "SKIP_SHOW_ALREADY_ACTIVE_" + targetConfiguration);
                }
                string after = ActiveConfigurationName(model);
                Require(String.Equals(after, targetConfiguration, StringComparison.Ordinal),
                    "Active configuration mismatch after activation policy");

                Progress(progressPath, "BEFORE_REBUILD_" + targetConfiguration);
                Require(model.ForceRebuild3(false),
                    "ForceRebuild3 failed for " + targetConfiguration);
                Progress(progressPath, "AFTER_REBUILD_" + targetConfiguration);
                Require(model.IsOpenedReadOnly(), "Document lost read-only state");
                transitions.Add(new Dictionary<string, object>
                {
                    {"before", before},
                    {"target", targetConfiguration},
                    {"show_configuration_called", showCalled},
                    {"after", after},
                    {"force_rebuild_pass", true}
                });
            }

            string beforeRestore = ActiveConfigurationName(model);
            bool restoreCalled = !String.Equals(
                beforeRestore, initialConfiguration, StringComparison.Ordinal);
            stage = "RESTORE_INITIAL_CONFIGURATION";
            if (restoreCalled)
            {
                Progress(progressPath, "BEFORE_RESTORE_" + beforeRestore + "_TO_" +
                    initialConfiguration);
                Require(model.ShowConfiguration2(initialConfiguration),
                    "Could not restore initial configuration");
                Progress(progressPath, "AFTER_RESTORE_" + initialConfiguration);
            }
            Require(String.Equals(ActiveConfigurationName(model), initialConfiguration,
                StringComparison.Ordinal), "Initial configuration was not restored");

            stage = "CLOSE_WITHOUT_SAVE";
            Progress(progressPath, stage);
            app.CloseDoc(model.GetTitle());
            ReleaseCom(model);
            model = null;
            Require(app.GetDocumentCount() == 0 && app.ActiveDoc == null,
                "SolidWorks is not document-empty after CloseDoc");
            Require(String.Equals(Sha256(targetPath), expectedTargetSha256,
                StringComparison.OrdinalIgnoreCase),
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

            receipt["status"] = "PASS_CONFIGURATION_SWITCH_AND_REBUILD_READ_ONLY";
            receipt["transitions"] = transitions;
            receipt["initial_configuration_restored"] = true;
            receipt["target_sha256_after"] = Sha256(targetPath);
            receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");
            Progress(progressPath, "PASS");
            WriteJsonCreateNew(receiptPath, receipt);
            process.Dispose();
            return 0;
        }
        catch (Exception ex)
        {
            receipt["status"] = "S02_R2_FAIL_CLOSED";
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
