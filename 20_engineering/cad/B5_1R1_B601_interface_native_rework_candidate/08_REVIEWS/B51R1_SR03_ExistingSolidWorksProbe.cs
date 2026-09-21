using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static class B51R1SR03ExistingSolidWorksProbe
{
    private static void WriteJson(string path, Dictionary<string, object> data)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(
            path,
            new JavaScriptSerializer().Serialize(data),
            new UTF8Encoding(false));
    }

    [STAThread]
    public static int Run(int expectedProcessId, string receiptPath)
    {
        var receipt = new Dictionary<string, object>
        {
            {"schema", "B51R1_SR03_EXISTING_SOLIDWORKS_PROBE_V1"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"status", "FAIL_CLOSED_NOT_STARTED"},
            {"expected_process_id", expectedProcessId},
            {"attachment_route", "CSHARP_MARSHAL_GETACTIVEOBJECT_EXISTING_USER_OPENED_PROCESS"},
            {"read_only_preflight", true}
        };
        SldWorks app = null;
        try
        {
            if (File.Exists(receiptPath))
            {
                throw new InvalidOperationException(
                    "Probe receipt already exists; refusing overwrite");
            }
            app = (SldWorks)Marshal.GetActiveObject("SldWorks.Application");
            int processId = app.GetProcessID();
            bool visible = app.Visible;
            bool startupComplete = app.StartupProcessCompleted;
            int documentCount = app.GetDocumentCount();
            bool activeDocumentPresent = app.ActiveDoc != null;

            receipt["observed_process_id"] = processId;
            receipt["visible"] = visible;
            receipt["startup_process_completed"] = startupComplete;
            receipt["document_count"] = documentCount;
            receipt["active_document_present"] = activeDocumentPresent;
            receipt["solidworks_revision"] = app.RevisionNumber();

            if (processId != expectedProcessId)
                throw new InvalidOperationException("ROT process ID mismatch");
            if (!visible)
                throw new InvalidOperationException("SolidWorks session is not visible");
            if (!startupComplete)
                throw new InvalidOperationException("SolidWorks startup is not complete");
            if (documentCount != 0 || activeDocumentPresent)
                throw new InvalidOperationException("SolidWorks session is not document-empty");

            receipt["status"] = "PASS_EXISTING_SINGLE_VISIBLE_RESPONSIVE_DOCUMENT_EMPTY_SESSION";
            WriteJson(receiptPath, receipt);
            Marshal.FinalReleaseComObject(app);
            return 0;
        }
        catch (Exception ex)
        {
            receipt["status"] = "FAIL_CLOSED";
            receipt["error_type"] = ex.GetType().FullName;
            receipt["error_message"] = ex.Message;
            receipt["error_hresult"] = "0x" + ex.HResult.ToString("X8");
            if (!File.Exists(receiptPath))
            {
                WriteJson(receiptPath, receipt);
            }
            if (app != null)
            {
                try { Marshal.FinalReleaseComObject(app); } catch { }
            }
            return 1;
        }
    }
}
