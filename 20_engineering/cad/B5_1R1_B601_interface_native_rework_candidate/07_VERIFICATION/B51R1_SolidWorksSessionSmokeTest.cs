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

public static class B51R1SolidWorksSessionSmokeTest
{
    private static string ProgressPath;

    private static void Trace(string message)
    {
        try
        {
            File.AppendAllText(
                ProgressPath,
                DateTime.UtcNow.ToString("o") + " | " + message +
                System.Environment.NewLine,
                new UTF8Encoding(false));
        }
        catch
        {
        }
    }

    private static string Sha256(string path)
    {
        using (var stream = File.OpenRead(path))
        using (var sha = SHA256.Create())
        {
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "");
        }
    }

    private static void WriteReceipt(
        string receiptPath,
        Dictionary<string, object> receipt)
    {
        string json = new JavaScriptSerializer().Serialize(receipt);
        File.WriteAllText(receiptPath, json, new UTF8Encoding(false));
    }

    private static List<Dictionary<string, object>> ProcessInventory()
    {
        return Process.GetProcessesByName("SLDWORKS")
            .Select(process => new Dictionary<string, object>
            {
                {"pid", process.Id},
                {"responding", process.Responding},
                {"main_window_handle", process.MainWindowHandle.ToInt64()},
                {"main_window_title", process.MainWindowTitle},
                {"start_time", process.StartTime.ToUniversalTime().ToString("o")}
            })
            .ToList();
    }

    [STAThread]
    public static int Run(string smokePath, string receiptPath)
    {
        ProgressPath = Path.Combine(
            Path.GetDirectoryName(receiptPath),
            Path.GetFileNameWithoutExtension(receiptPath) + "_PROGRESS.log");
        File.WriteAllText(
            ProgressPath,
            DateTime.UtcNow.ToString("o") +
            " | START | B51R1_SOLIDWORKS_VISIBLE_SESSION_SMOKE_V1" +
            System.Environment.NewLine,
            new UTF8Encoding(false));

        var receipt = new Dictionary<string, object>
        {
            {"schema", "SER_B51R1_SOLIDWORKS_VISIBLE_SESSION_RECOVERY_V1"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"status", "FAIL_NOT_STARTED"},
            {"smoke_part", smokePath},
            {"progress_log", ProgressPath},
            {"recovery_dialog", "NOT_PRESENT_ON_VISIBLE_START"},
            {"frozen_asset_recovery_actions", 0}
        };

        SldWorks swApp = null;
        ModelDoc2 model = null;
        try
        {
            bool smokePreexisting = File.Exists(smokePath);
            receipt["smoke_preexisting"] = smokePreexisting;
            if (File.Exists(receiptPath))
            {
                throw new InvalidOperationException(
                    "Receipt already exists; refusing overwrite: " + receiptPath);
            }

            string template =
                @"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2024\templates\gb_part.prtdot";
            if (!File.Exists(template))
            {
                throw new FileNotFoundException("Part template not found", template);
            }

            Trace("BEGIN | ATTACH_ACTIVE_VISIBLE_INSTANCE");
            swApp = (SldWorks)Marshal.GetActiveObject("SldWorks.Application");
            Trace("END | ATTACH_ACTIVE_VISIBLE_INSTANCE");

            var processes = ProcessInventory();
            receipt["solidworks_processes"] = processes;
            if (processes.Count != 1)
            {
                throw new InvalidOperationException(
                    "Expected exactly one SLDWORKS process; found " + processes.Count);
            }
            if (!swApp.Visible)
            {
                throw new InvalidOperationException("Active SolidWorks instance is not visible");
            }
            receipt["solidworks_revision"] = swApp.RevisionNumber();
            receipt["visible"] = swApp.Visible;
            receipt["document_count_before"] = swApp.GetDocumentCount();
            receipt["active_document_before"] =
                swApp.ActiveDoc == null ? null : ((ModelDoc2)swApp.ActiveDoc).GetTitle();
            if (swApp.GetDocumentCount() != 0 || swApp.ActiveDoc != null)
            {
                throw new InvalidOperationException(
                    "Visible session is not empty before smoke test");
            }

            if (!smokePreexisting)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(smokePath));
                Trace("BEGIN | CREATE_BLANK_TEST_PART");
                model = (ModelDoc2)swApp.NewDocument(template, 0, 0, 0);
                Trace("END | CREATE_BLANK_TEST_PART");
                if (model == null)
                {
                    throw new InvalidOperationException("NewDocument returned null");
                }
                receipt["new_document_title"] = model.GetTitle();

                int saveErrors = 0;
                int saveWarnings = 0;
                Trace("BEGIN | SAVE_BLANK_TEST_PART");
                bool saved = model.Extension.SaveAs(
                    smokePath, 0, 1, null, ref saveErrors, ref saveWarnings);
                Trace("END | SAVE_BLANK_TEST_PART");
                if (!saved || saveErrors != 0 || !File.Exists(smokePath))
                {
                    throw new InvalidOperationException(
                        "Smoke SaveAs failed saved=" + saved + " errors=" + saveErrors +
                        " warnings=" + saveWarnings);
                }
                receipt["save_errors"] = saveErrors;
                receipt["save_warnings"] = saveWarnings;

                Trace("BEGIN | CLOSE_SAVED_TEST_PART");
                swApp.CloseDoc(model.GetTitle());
                model = null;
                Trace("END | CLOSE_SAVED_TEST_PART");
            }
            else
            {
                receipt["resume_reason"] =
                    "PRIOR_ATTEMPT_SAVED_THEN_FAILED_WHILE_HASHING_OPEN_FILE";
                Trace("RESUME | EXISTING_SAVED_TEST_PART");
            }

            receipt["document_count_after_close"] = swApp.GetDocumentCount();
            if (swApp.GetDocumentCount() != 0)
            {
                throw new InvalidOperationException(
                    "Document count is not zero after closing smoke part");
            }
            receipt["saved_bytes"] = new FileInfo(smokePath).Length;
            receipt["saved_sha256"] = Sha256(smokePath);

            int openErrors = 0;
            int openWarnings = 0;
            Trace("BEGIN | REOPEN_SAVED_TEST_PART");
            model = (ModelDoc2)swApp.OpenDoc6(
                smokePath, 1, 1, "", ref openErrors, ref openWarnings);
            Trace("END | REOPEN_SAVED_TEST_PART");
            if (model == null || openErrors != 0)
            {
                throw new InvalidOperationException(
                    "Smoke reopen failed errors=" + openErrors +
                    " warnings=" + openWarnings);
            }
            receipt["open_errors"] = openErrors;
            receipt["open_warnings"] = openWarnings;
            receipt["reopened_path"] = model.GetPathName();
            receipt["reopened_title"] = model.GetTitle();
            receipt["external_file_reference_count"] =
                model.ListExternalFileReferencesCount2();
            if (!String.Equals(
                    Path.GetFullPath(model.GetPathName()),
                    Path.GetFullPath(smokePath),
                    StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("Reopened path does not match smoke target");
            }
            if (model.ListExternalFileReferencesCount2() != 0)
            {
                throw new InvalidOperationException(
                    "Blank smoke part unexpectedly has external file references");
            }

            Trace("BEGIN | CLOSE_REOPENED_TEST_PART");
            swApp.CloseDoc(model.GetTitle());
            model = null;
            Trace("END | CLOSE_REOPENED_TEST_PART");
            receipt["document_count_final"] = swApp.GetDocumentCount();
            receipt["active_document_final"] =
                swApp.ActiveDoc == null ? null : ((ModelDoc2)swApp.ActiveDoc).GetTitle();
            if (swApp.GetDocumentCount() != 0 || swApp.ActiveDoc != null)
            {
                throw new InvalidOperationException(
                    "Visible session is not empty after smoke test");
            }

            receipt["status"] =
                "PASS_VISIBLE_SINGLE_INSTANCE_SAVE_CLOSE_REOPEN_COM_BIND";
            receipt["claim_limit"] =
                "SESSION_RECOVERY_ONLY_NO_NATIVE_MASTER_SKELETON_OR_ARTICULATION_CREDIT";
            WriteReceipt(receiptPath, receipt);
            Trace("PASS | PASS_VISIBLE_SINGLE_INSTANCE_SAVE_CLOSE_REOPEN_COM_BIND");
            Marshal.FinalReleaseComObject(swApp);
            return 0;
        }
        catch (Exception ex)
        {
            Trace(
                "FAIL_CLOSED | " + ex.GetType().FullName + " | " +
                ex.Message.Replace("\r", " ").Replace("\n", " "));
            receipt["status"] = "FAIL_CLOSED";
            receipt["error_type"] = ex.GetType().FullName;
            receipt["error_message"] = ex.Message;
            receipt["error_hresult"] = "0x" + ex.HResult.ToString("X8");
            try
            {
                if (swApp != null && model != null)
                {
                    swApp.CloseDoc(model.GetTitle());
                }
            }
            catch
            {
            }
            WriteReceipt(receiptPath, receipt);
            if (swApp != null)
            {
                try { Marshal.FinalReleaseComObject(swApp); } catch { }
            }
            return 1;
        }
    }
}
