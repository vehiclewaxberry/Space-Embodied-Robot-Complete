using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static class B51R1S02R5StrongTypedWaitingReadinessProbe
{
    private static void WriteJsonCreateNew(string path, Dictionary<string, object> data)
    {
        string directory = Path.GetDirectoryName(path);
        if (!String.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);
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

    [STAThread]
    public static int Run(int expectedProcessId, string receiptPath, int timeoutMilliseconds)
    {
        var receipt = new Dictionary<string, object>
        {
            {"schema", "B51R1_S02_R5_STRONG_TYPED_WAITING_READINESS_PROBE_V1"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"status", "S02_R5_FAIL_CLOSED_NOT_STARTED"},
            {"expected_process_id", expectedProcessId},
            {"attachment_route", "STRONG_TYPED_CSHARP_MARSHAL_GETACTIVEOBJECT_WITH_INTERNAL_RETRY"},
            {"retry_interval_ms", 500},
            {"timeout_ms", timeoutMilliseconds},
            {"read_only_preflight", true},
            {"document_open_call_count", 0},
            {"save_api_call_count", 0}
        };
        DateTime started = DateTime.UtcNow;
        DateTime deadline = started.AddMilliseconds(timeoutMilliseconds);
        int attempts = 0;
        Exception lastException = null;
        int observedProcessId = 0;
        bool visible = false;
        bool startupComplete = false;
        int documentCount = -1;
        bool activeDocumentPresent = true;
        string revision = null;
        try
        {
            if (File.Exists(receiptPath))
                throw new InvalidOperationException("Readiness receipt already exists");
            if (timeoutMilliseconds < 1000 || timeoutMilliseconds > 300000)
                throw new ArgumentOutOfRangeException("timeoutMilliseconds");

            while (DateTime.UtcNow < deadline)
            {
                attempts++;
                SldWorks app = null;
                try
                {
                    Process[] processes = Process.GetProcessesByName("SLDWORKS");
                    try
                    {
                        if (processes.Length != 1 || processes[0].Id != expectedProcessId)
                            throw new InvalidOperationException(
                                "Expected exactly one matching SLDWORKS process");
                        processes[0].Refresh();
                        if (!processes[0].Responding ||
                            processes[0].MainWindowHandle == IntPtr.Zero)
                            throw new InvalidOperationException(
                                "Expected SLDWORKS process is not visible and responsive");
                    }
                    finally
                    {
                        foreach (Process process in processes) process.Dispose();
                    }

                    app = (SldWorks)Marshal.GetActiveObject("SldWorks.Application");
                    observedProcessId = app.GetProcessID();
                    visible = app.Visible;
                    startupComplete = app.StartupProcessCompleted;
                    documentCount = app.GetDocumentCount();
                    activeDocumentPresent = app.ActiveDoc != null;
                    revision = app.RevisionNumber();
                    if (observedProcessId == expectedProcessId && visible && startupComplete &&
                        documentCount == 0 && !activeDocumentPresent)
                    {
                        receipt["status"] =
                            "PASS_STRONG_TYPED_VISIBLE_RESPONSIVE_STARTUP_COMPLETE_DOCUMENT_EMPTY";
                        receipt["observed_process_id"] = observedProcessId;
                        receipt["visible"] = visible;
                        receipt["startup_process_completed"] = startupComplete;
                        receipt["document_count"] = documentCount;
                        receipt["active_document_present"] = activeDocumentPresent;
                        receipt["solidworks_revision"] = revision;
                        receipt["attempt_count"] = attempts;
                        receipt["elapsed_ms"] =
                            (DateTime.UtcNow - started).TotalMilliseconds;
                        receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");
                        ReleaseCom(app);
                        app = null;
                        WriteJsonCreateNew(receiptPath, receipt);
                        return 0;
                    }
                }
                catch (Exception ex)
                {
                    lastException = ex;
                }
                finally
                {
                    ReleaseCom(app);
                }
                Thread.Sleep(500);
            }

            throw new TimeoutException(
                "SolidWorks did not reach visible startup-complete document-empty state");
        }
        catch (Exception ex)
        {
            receipt["status"] = "S02_R5_FAIL_CLOSED";
            receipt["observed_process_id_if_available"] = observedProcessId;
            receipt["visible_if_available"] = visible;
            receipt["startup_process_completed_if_available"] = startupComplete;
            receipt["document_count_if_available"] = documentCount;
            receipt["active_document_present_if_available"] = activeDocumentPresent;
            receipt["solidworks_revision_if_available"] = revision;
            receipt["attempt_count"] = attempts;
            receipt["elapsed_ms"] = (DateTime.UtcNow - started).TotalMilliseconds;
            receipt["error_type"] = ex.GetType().FullName;
            receipt["error_message"] = ex.Message;
            receipt["error_hresult"] = "0x" + ex.HResult.ToString("X8");
            if (lastException != null)
            {
                receipt["last_retry_error_type"] = lastException.GetType().FullName;
                receipt["last_retry_error_message"] = lastException.Message;
                receipt["last_retry_error_hresult"] =
                    "0x" + lastException.HResult.ToString("X8");
            }
            if (!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath, receipt);
            return 1;
        }
    }
}
