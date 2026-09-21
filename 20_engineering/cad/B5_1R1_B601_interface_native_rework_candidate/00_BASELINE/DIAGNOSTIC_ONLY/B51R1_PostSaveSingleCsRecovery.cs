using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;

internal static class B51R1PostSaveSingleCsRecovery
{
    private const string AuthorizationToken =
        "--authorized-attach-pid-3308-postsave-recovery";
    private const int AuthorizedProcessId = 3308;
    private const int ExitWaitMilliseconds = 30000;
    private const string CoordinateSystemName = "CS_DIAGNOSTIC_ONLY";
    private const string ExpectedStageAHash =
        "5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B";

    private static string progressPath;

    private static void Require(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }

    private static string FullPath(string path)
    {
        return Path.GetFullPath(path);
    }

    private static bool SamePath(string left, string right)
    {
        return String.Equals(
            FullPath(left),
            FullPath(right),
            StringComparison.OrdinalIgnoreCase);
    }

    private static string OneLine(string value)
    {
        return (value ?? "").Replace("\r", " ").Replace("\n", " ");
    }

    private static void CreateProgress(string path)
    {
        using (FileStream stream = new FileStream(
            path,
            FileMode.CreateNew,
            FileAccess.Write,
            FileShare.Read))
        using (StreamWriter writer = new StreamWriter(
            stream,
            new UTF8Encoding(false)))
        {
            writer.WriteLine(
                DateTime.UtcNow.ToString("o") +
                " | BEGIN | ATTACH_ONLY_POSTSAVE_RECOVERY_PID_3308");
        }
    }

    private static void Trace(string message)
    {
        File.AppendAllText(
            progressPath,
            DateTime.UtcNow.ToString("o") + " | " + message +
            Environment.NewLine,
            new UTF8Encoding(false));
    }

    private static void SafeTrace(string message)
    {
        try
        {
            Trace(message);
        }
        catch
        {
        }
    }

    private static T Step<T>(string name, Func<T> action)
    {
        Trace("BEGIN | " + name);
        try
        {
            T result = action();
            Trace("END | " + name);
            return result;
        }
        catch (Exception ex)
        {
            SafeTrace(
                "FAIL | " + name + " | " + ex.GetType().FullName +
                " | " + OneLine(ex.Message));
            throw;
        }
    }

    private static string Sha256(string path)
    {
        using (FileStream stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read))
        using (SHA256 sha = SHA256.Create())
        {
            return BitConverter.ToString(sha.ComputeHash(stream))
                .Replace("-", "");
        }
    }

    private static void WriteJsonCreateNew(
        string path,
        Dictionary<string, object> value)
    {
        string json = new JavaScriptSerializer().Serialize(value);
        using (FileStream stream = new FileStream(
            path,
            FileMode.CreateNew,
            FileAccess.Write,
            FileShare.Read))
        using (StreamWriter writer = new StreamWriter(
            stream,
            new UTF8Encoding(false)))
        {
            writer.Write(json);
            writer.WriteLine();
        }
    }

    private static void ReleaseCom(object value)
    {
        if (value == null || !Marshal.IsComObject(value))
        {
            return;
        }
        try
        {
            Marshal.FinalReleaseComObject(value);
        }
        catch
        {
        }
    }

    private static double[] ToDoubleArray(object raw)
    {
        Array array = raw as Array;
        Require(array != null, "Transform ArrayData is not an array");
        double[] result = new double[array.Length];
        int index = 0;
        foreach (object item in array)
        {
            result[index++] = Convert.ToDouble(item);
        }
        return result;
    }

    private static Dictionary<string, object> ReadTransformAndFeatureCounts(
        dynamic model)
    {
        dynamic cursor = null;
        dynamic coordinateFeature = null;
        int exactNameCount = 0;
        int totalCoordinateSystemCount = 0;
        string exactFeatureType = null;

        try
        {
            cursor = model.FirstFeature();
            while (cursor != null)
            {
                dynamic next = null;
                bool retainCurrent = false;
                try
                {
                    next = cursor.GetNextFeature();
                    string name = Convert.ToString(cursor.Name);
                    string type = Convert.ToString(cursor.GetTypeName2());
                    if (String.Equals(
                        type,
                        "CoordSys",
                        StringComparison.Ordinal))
                    {
                        totalCoordinateSystemCount++;
                    }
                    if (String.Equals(
                        name,
                        CoordinateSystemName,
                        StringComparison.Ordinal))
                    {
                        exactNameCount++;
                        exactFeatureType = type;
                        if (coordinateFeature == null)
                        {
                            coordinateFeature = cursor;
                            retainCurrent = true;
                        }
                    }
                }
                finally
                {
                    if (!retainCurrent)
                    {
                        ReleaseCom(cursor);
                    }
                    cursor = next;
                }
            }
        }
        finally
        {
            ReleaseCom(cursor);
        }

        Require(
            exactNameCount == 1,
            "Expected exactly one feature named " +
            CoordinateSystemName + "; observed " + exactNameCount);
        Require(
            String.Equals(
                exactFeatureType,
                "CoordSys",
                StringComparison.Ordinal),
            "The uniquely named feature is not a CoordSys");
        Require(
            totalCoordinateSystemCount == 1,
            "Expected exactly one CoordSys feature in the document; observed " +
            totalCoordinateSystemCount);
        Require(
            coordinateFeature != null,
            "The uniquely named CoordSys feature is unavailable");

        dynamic featureData = null;
        dynamic transform = null;
        bool selectionAccess = false;
        try
        {
            featureData = coordinateFeature.GetDefinition();
            Require(
                featureData != null,
                "Coordinate-system feature data is unavailable");
            selectionAccess = Convert.ToBoolean(
                featureData.AccessSelections(model, null));
            Require(
                selectionAccess,
                "Coordinate-system feature selection access failed");
            transform = featureData.Transform;
            Require(
                transform != null,
                "Coordinate-system transform is unavailable");
            double[] values = ToDoubleArray(transform.ArrayData);
            Require(
                values.Length == 16,
                "Expected 16 transform values; observed " + values.Length);

            double[] expected = new double[]
            {
                1, 0, 0,
                0, 1, 0,
                0, 0, 1,
                0, 0, 0,
                1, 0, 0, 0
            };
            const double tolerance = 1.0e-12;
            double maximumAbsoluteError = 0.0;
            for (int index = 0; index < expected.Length; index++)
            {
                maximumAbsoluteError = Math.Max(
                    maximumAbsoluteError,
                    Math.Abs(values[index] - expected[index]));
            }
            Require(
                maximumAbsoluteError <= tolerance,
                "Transform is not the expected SolidWorks identity transform");

            return new Dictionary<string, object>
            {
                {"api_readback",
                    "ICoordinateSystemFeatureData.Transform / IMathTransform.ArrayData"},
                {"coordinate_system_name", CoordinateSystemName},
                {"exact_name_count", exactNameCount},
                {"exact_name_feature_type", exactFeatureType},
                {"total_coordinate_system_feature_count",
                    totalCoordinateSystemCount},
                {"array_length", values.Length},
                {"transform_array", values},
                {"rotation_3x3_row_major", new double[]
                    {
                        values[0], values[1], values[2],
                        values[3], values[4], values[5],
                        values[6], values[7], values[8]
                    }},
                {"translation_m", new double[]
                    {
                        values[9], values[10], values[11]
                    }},
                {"scale", values[12]},
                {"reserved_tail", new double[]
                    {
                        values[13], values[14], values[15]
                    }},
                {"identity_tolerance", tolerance},
                {"maximum_absolute_identity_error", maximumAbsoluteError},
                {"rotation_is_identity", true},
                {"translation_is_zero", true},
                {"scale_is_one", true},
                {"reserved_tail_is_zero", true}
            };
        }
        finally
        {
            if (featureData != null && selectionAccess)
            {
                try
                {
                    featureData.ReleaseSelectionAccess();
                }
                catch
                {
                }
            }
            ReleaseCom(transform);
            ReleaseCom(featureData);
            ReleaseCom(coordinateFeature);
        }
    }

    [STAThread]
    private static int Main(string[] args)
    {
        if (args.Length != 1 ||
            !String.Equals(
                args[0],
                AuthorizationToken,
                StringComparison.Ordinal))
        {
            Console.Error.WriteLine(
                "NOT RUN. Exact post-save recovery authorization token required.");
            Console.Error.WriteLine(
                Path.GetFileName(
                    Process.GetCurrentProcess().MainModule.FileName) +
                " " + AuthorizationToken);
            return 64;
        }

        string diagnosticDirectory = FullPath(
            AppDomain.CurrentDomain.BaseDirectory);
        string candidateRoot = FullPath(
            Path.Combine(diagnosticDirectory, "..", ".."));
        string targetPath = FullPath(
            Path.Combine(
                diagnosticDirectory,
                "B51R1_SINGLE_CS_DIAGNOSTIC_COPY.SLDPRT"));
        string stageAPath = FullPath(
            Path.Combine(
                candidateRoot,
                "02_MASTER_SKELETON",
                "B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT"));
        string oldFailReceiptPath = FullPath(
            Path.Combine(
                candidateRoot,
                "07_VERIFICATION",
                "B51R1_SINGLE_CS_DIAGNOSTIC_FIRST_LAUNCH_RECEIPT.json"));
        string transformPath = FullPath(
            Path.Combine(
                candidateRoot,
                "07_VERIFICATION",
                "B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM_FIRST_LAUNCH.json"));
        string recoveryReceiptPath = FullPath(
            Path.Combine(
                candidateRoot,
                "07_VERIFICATION",
                "B51R1_SINGLE_CS_DIAGNOSTIC_POSTSAVE_RECOVERY_RECEIPT.json"));
        string failureReceiptPath = FullPath(
            Path.Combine(
                candidateRoot,
                "07_VERIFICATION",
                "B51R1_SINGLE_CS_DIAGNOSTIC_POSTSAVE_RECOVERY_FAIL_CLOSED.json"));
        progressPath = FullPath(
            Path.Combine(
                candidateRoot,
                "08_REVIEWS",
                "B51R1_SINGLE_CS_DIAGNOSTIC_POSTSAVE_RECOVERY_PROGRESS.log"));

        dynamic swApp = null;
        dynamic model = null;
        Process solidWorksProcess = null;
        string oldFailReceiptHashBefore = null;
        string stageAHashBefore = null;
        Dictionary<string, object> transformReadback = null;

        try
        {
            Require(
                Directory.Exists(diagnosticDirectory) &&
                Directory.Exists(Path.GetDirectoryName(transformPath)) &&
                Directory.Exists(Path.GetDirectoryName(progressPath)),
                "Required candidate directories are missing");
            Require(
                File.Exists(targetPath),
                "Fixed diagnostic target is missing");
            Require(
                File.Exists(stageAPath),
                "Protected Stage A file is missing");
            Require(
                File.Exists(oldFailReceiptPath),
                "Original immutable FAIL_CLOSED receipt is missing");
            Require(
                !File.Exists(transformPath) &&
                !File.Exists(recoveryReceiptPath) &&
                !File.Exists(failureReceiptPath) &&
                !File.Exists(progressPath),
                "A fixed recovery output already exists; overwrite refused");

            CreateProgress(progressPath);
            Trace("CONTRACT | NO_DOCUMENT_CREATION_SAVE_OPEN_COPY_OR_PROCESS_TERMINATION");

            oldFailReceiptHashBefore = Step(
                "HASH_OLD_FAIL_CLOSED_RECEIPT_BEFORE",
                delegate { return Sha256(oldFailReceiptPath); });
            var oldFailReceipt = Step(
                "READ_OLD_FAIL_CLOSED_RECEIPT",
                delegate
                {
                    return new JavaScriptSerializer()
                        .Deserialize<Dictionary<string, object>>(
                            File.ReadAllText(
                                oldFailReceiptPath,
                                Encoding.UTF8));
                });
            Require(
                oldFailReceipt.ContainsKey("status") &&
                String.Equals(
                    Convert.ToString(oldFailReceipt["status"]),
                    "FAIL_CLOSED_FIRST_LAUNCH",
                    StringComparison.Ordinal),
                "Original receipt does not retain FAIL_CLOSED_FIRST_LAUNCH status");

            stageAHashBefore = Step(
                "HASH_PROTECTED_STAGE_A_BEFORE_READ_ONLY",
                delegate { return Sha256(stageAPath); });
            Require(
                String.Equals(
                    stageAHashBefore,
                    ExpectedStageAHash,
                    StringComparison.Ordinal),
                "Protected Stage A hash does not match the frozen value");

            Process[] processes = Step(
                "VERIFY_SOLE_SLDWORKS_PROCESS_IS_AUTHORIZED_PID",
                delegate { return Process.GetProcessesByName("SLDWORKS"); });
            Require(
                processes.Length == 1,
                "Expected exactly one SLDWORKS process; observed " +
                processes.Length);
            solidWorksProcess = processes[0];
            Require(
                solidWorksProcess.Id == AuthorizedProcessId,
                "The sole SLDWORKS process is not authorized PID " +
                AuthorizedProcessId);
            solidWorksProcess.Refresh();
            Require(
                !solidWorksProcess.HasExited &&
                solidWorksProcess.Responding &&
                solidWorksProcess.MainWindowHandle != IntPtr.Zero,
                "Authorized SolidWorks process is not responsive and visible");

            swApp = Step(
                "ATTACH_TO_ACTIVE_SOLIDWORKS_WITHOUT_STARTING_A_PROCESS",
                delegate
                {
                    return Marshal.GetActiveObject("SldWorks.Application");
                });
            Require(swApp != null, "Active SolidWorks automation object is absent");
            Require(
                Convert.ToInt32(swApp.GetProcessID()) == AuthorizedProcessId,
                "Attached automation object does not belong to PID 3308");
            Require(
                Convert.ToBoolean(swApp.Visible),
                "Attached SolidWorks session is not visible");
            Require(
                Convert.ToBoolean(swApp.StartupProcessCompleted),
                "SolidWorks startup is not complete");
            Require(
                Convert.ToInt32(swApp.GetDocumentCount()) == 1,
                "Expected exactly one open document");

            model = swApp.ActiveDoc;
            Require(model != null, "Active document is unavailable");
            string activePath = Convert.ToString(model.GetPathName());
            Require(
                !String.IsNullOrWhiteSpace(activePath) &&
                SamePath(activePath, targetPath),
                "Active document is not the fixed diagnostic target");

            transformReadback = Step(
                "READ_AND_VALIDATE_UNIQUE_NAMED_COORDINATE_SYSTEM",
                delegate
                {
                    return ReadTransformAndFeatureCounts(model);
                });

            int externalReferenceCount = Step(
                "VERIFY_ZERO_EXTERNAL_FILE_REFERENCES",
                delegate
                {
                    dynamic extension = null;
                    try
                    {
                        extension = model.Extension;
                        Require(
                            extension != null,
                            "Model extension is unavailable");
                        return Convert.ToInt32(
                            extension.ListExternalFileReferencesCount());
                    }
                    finally
                    {
                        ReleaseCom(extension);
                    }
                });
            Require(
                externalReferenceCount == 0,
                "Diagnostic target has external file references: " +
                externalReferenceCount);

            string currentTitle = Convert.ToString(model.GetTitle());
            Require(
                !String.IsNullOrWhiteSpace(currentTitle),
                "Current active document title is unavailable");
            Step(
                "CLOSE_FIXED_TARGET_USING_CURRENT_MODEL_TITLE",
                delegate
                {
                    swApp.CloseDoc(currentTitle);
                    return true;
                });
            ReleaseCom(model);
            model = null;

            Require(
                Convert.ToInt32(swApp.GetDocumentCount()) == 0,
                "SolidWorks session is not empty after current-title close");
            object activeAfterClose = swApp.ActiveDoc;
            try
            {
                Require(
                    activeAfterClose == null,
                    "An active document remains after current-title close");
            }
            finally
            {
                ReleaseCom(activeAfterClose);
            }

            long targetBytesAfterClose = Step(
                "READ_TARGET_BYTES_AFTER_CLOSE",
                delegate { return new FileInfo(targetPath).Length; });
            string targetHashAfterClose = Step(
                "HASH_TARGET_AFTER_CLOSE",
                delegate { return Sha256(targetPath); });
            string stageAHashAfter = Step(
                "HASH_PROTECTED_STAGE_A_AFTER_READ_ONLY",
                delegate { return Sha256(stageAPath); });
            Require(
                String.Equals(
                    stageAHashBefore,
                    stageAHashAfter,
                    StringComparison.Ordinal),
                "Protected Stage A hash changed");
            string oldFailReceiptHashAfter = Step(
                "HASH_OLD_FAIL_CLOSED_RECEIPT_AFTER",
                delegate { return Sha256(oldFailReceiptPath); });
            Require(
                String.Equals(
                    oldFailReceiptHashBefore,
                    oldFailReceiptHashAfter,
                    StringComparison.Ordinal),
                "Original FAIL_CLOSED receipt changed");

            transformReadback["schema"] =
                "SER_B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM_FIRST_LAUNCH_V1";
            transformReadback["generated_at_utc"] =
                DateTime.UtcNow.ToString("o");
            transformReadback["status"] =
                "TRANSFORM_IDENTITY_CONFIRMED_DURING_POSTSAVE_RECOVERY_COLD_REOPEN_PENDING";
            transformReadback["evidence_stage"] =
                "SAME_VISIBLE_PROCESS_POSTSAVE_RECOVERY";
            transformReadback["solidworks_process_id"] =
                AuthorizedProcessId;
            transformReadback["target_part"] = targetPath;
            transformReadback["target_part_bytes"] =
                targetBytesAfterClose;
            transformReadback["target_part_sha256"] =
                targetHashAfterClose;
            transformReadback["external_file_reference_count"] =
                externalReferenceCount;
            transformReadback["protected_stage_a"] = stageAPath;
            transformReadback["protected_stage_a_sha256_before"] =
                stageAHashBefore;
            transformReadback["protected_stage_a_sha256_after"] =
                stageAHashAfter;
            transformReadback["protected_stage_a_unchanged"] = true;
            transformReadback["original_fail_closed_receipt"] =
                oldFailReceiptPath;
            transformReadback["original_fail_closed_receipt_sha256_before"] =
                oldFailReceiptHashBefore;
            transformReadback["original_fail_closed_receipt_sha256_after"] =
                oldFailReceiptHashAfter;
            transformReadback["original_fail_closed_receipt_unchanged"] =
                true;
            transformReadback["document_close_method"] =
                "CloseDoc(model.GetTitle())";
            transformReadback["document_count_after_close"] = 0;
            transformReadback["cold_process_reopen_status"] =
                "NOT_RUN_REQUIRES_SEPARATE_VISIBLE_LAUNCH_AUTHORIZATION";
            transformReadback["claim_limit"] =
                "POSTSAVE_TRANSFORM_AND_CLOSE_RECOVERY_ONLY; FULL_SINGLE_CS_DIAGNOSTIC_PASS_NOT_CLAIMED; COLD_REOPEN_NOT_RUN; NO_MASTER_SKELETON_CARRIER_H10_T005_CONTROL_RELEASE_MANUFACTURING_OR_FLIGHT_CREDIT";
            Step(
                "WRITE_IMMUTABLE_TRANSFORM_EVIDENCE",
                delegate
                {
                    WriteJsonCreateNew(transformPath, transformReadback);
                    return true;
                });
            string transformEvidenceHash = Sha256(transformPath);

            DateTime exitRequestedAt = DateTime.UtcNow;
            Step(
                "REQUEST_NORMAL_EXIT_FROM_EMPTY_SESSION",
                delegate
                {
                    Require(
                        Convert.ToInt32(swApp.GetDocumentCount()) == 0 &&
                        swApp.ActiveDoc == null,
                        "Session is no longer empty before normal exit");
                    swApp.ExitApp();
                    return true;
                });
            ReleaseCom(swApp);
            swApp = null;

            bool exited = Step(
                "WAIT_FOR_AUTHORIZED_PROCESS_NORMAL_EXIT",
                delegate
                {
                    return solidWorksProcess.WaitForExit(
                        ExitWaitMilliseconds);
                });
            Require(
                exited,
                "SolidWorks did not exit within " +
                ExitWaitMilliseconds + " ms");
            int exitCode = solidWorksProcess.ExitCode;
            Require(
                exitCode == 0,
                "SolidWorks returned nonzero exit code " + exitCode);

            var recoveryReceipt = new Dictionary<string, object>
            {
                {"schema",
                    "SER_B51R1_SINGLE_CS_DIAGNOSTIC_POSTSAVE_RECOVERY_V1"},
                {"generated_at_utc", DateTime.UtcNow.ToString("o")},
                {"status",
                    "RECOVERED_CLOSE_AND_NORMAL_EXIT_COLD_REOPEN_PENDING"},
                {"recovery_reason",
                    "Initial immutable receipt failed after save because the pre-save title was used for document close"},
                {"solidworks_process_id", AuthorizedProcessId},
                {"solidworks_process_responding_before_attach", true},
                {"solidworks_visible_before_attach", true},
                {"active_document_count_before", 1},
                {"active_document_path_before", targetPath},
                {"coordinate_system_name", CoordinateSystemName},
                {"coordinate_system_count", 1},
                {"coordinate_system_transform_identity", true},
                {"external_file_reference_count", externalReferenceCount},
                {"close_title_used", currentTitle},
                {"document_count_after_close", 0},
                {"target_part_bytes_after_close", targetBytesAfterClose},
                {"target_part_sha256_after_close", targetHashAfterClose},
                {"transform_evidence", transformPath},
                {"transform_evidence_sha256", transformEvidenceHash},
                {"protected_stage_a", stageAPath},
                {"protected_stage_a_sha256_before", stageAHashBefore},
                {"protected_stage_a_sha256_after", stageAHashAfter},
                {"protected_stage_a_unchanged", true},
                {"original_fail_closed_receipt", oldFailReceiptPath},
                {"original_fail_closed_receipt_sha256_before",
                    oldFailReceiptHashBefore},
                {"original_fail_closed_receipt_sha256_after",
                    oldFailReceiptHashAfter},
                {"original_fail_closed_receipt_unchanged", true},
                {"normal_exit_requested_at_utc",
                    exitRequestedAt.ToString("o")},
                {"solidworks_process_exited", true},
                {"solidworks_process_exit_code", exitCode},
                {"cold_process_reopen_status",
                    "NOT_RUN_REQUIRES_SEPARATE_VISIBLE_LAUNCH_AUTHORIZATION"},
                {"progress_log", progressPath},
                {"claim_limit",
                    "RECOVERED_CLOSE_AND_NORMAL_EXIT_ONLY; FULL_SINGLE_CS_DIAGNOSTIC_PASS_NOT_CLAIMED; COLD_REOPEN_NOT_RUN; NO_MASTER_SKELETON_CARRIER_H10_T005_CONTROL_RELEASE_MANUFACTURING_OR_FLIGHT_CREDIT"}
            };
            Step(
                "WRITE_IMMUTABLE_RECOVERY_RECEIPT",
                delegate
                {
                    WriteJsonCreateNew(
                        recoveryReceiptPath,
                        recoveryReceipt);
                    return true;
                });
            Trace(
                "COMPLETE | RECOVERED_CLOSE_AND_NORMAL_EXIT_COLD_REOPEN_PENDING");
            Console.WriteLine(
                "RECOVERED_CLOSE_AND_NORMAL_EXIT_COLD_REOPEN_PENDING");
            Console.WriteLine("Transform: " + transformPath);
            Console.WriteLine("Receipt: " + recoveryReceiptPath);
            Console.WriteLine("Progress: " + progressPath);
            return 0;
        }
        catch (Exception ex)
        {
            SafeTrace(
                "FAIL_CLOSED | " + ex.GetType().FullName +
                " | " + OneLine(ex.Message));
            try
            {
                if (!File.Exists(failureReceiptPath))
                {
                    WriteJsonCreateNew(
                        failureReceiptPath,
                        new Dictionary<string, object>
                        {
                            {"schema",
                                "SER_B51R1_SINGLE_CS_DIAGNOSTIC_POSTSAVE_RECOVERY_FAIL_CLOSED_V1"},
                            {"generated_at_utc",
                                DateTime.UtcNow.ToString("o")},
                            {"status", "FAIL_CLOSED_POSTSAVE_RECOVERY"},
                            {"solidworks_process_id",
                                AuthorizedProcessId},
                            {"error_type", ex.GetType().FullName},
                            {"error_message", OneLine(ex.Message)},
                            {"error_hresult",
                                "0x" + ex.HResult.ToString("X8")},
                            {"progress_log", progressPath},
                            {"solidworks_process_termination_permitted",
                                false},
                            {"claim_limit",
                                "NO_SINGLE_CS_DIAGNOSTIC_PASS_CREDIT"}
                        });
                }
            }
            catch
            {
            }
            Console.Error.WriteLine(
                "FAIL_CLOSED_POSTSAVE_RECOVERY | " +
                ex.GetType().FullName + " | " + OneLine(ex.Message));
            return 2;
        }
        finally
        {
            ReleaseCom(model);
            ReleaseCom(swApp);
            if (solidWorksProcess != null)
            {
                solidWorksProcess.Dispose();
            }
            GC.Collect();
            GC.WaitForPendingFinalizers();
            GC.Collect();
        }
    }
}
