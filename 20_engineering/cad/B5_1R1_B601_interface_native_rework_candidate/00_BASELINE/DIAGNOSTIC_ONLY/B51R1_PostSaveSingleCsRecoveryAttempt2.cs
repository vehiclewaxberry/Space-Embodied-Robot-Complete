using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

namespace B51R1.NativeCadDiagnostics
{
    public static class PostSaveSingleCsRecoveryAttempt2
    {
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

        private static string Canonical(string path)
        {
            return Path.GetFullPath(path);
        }

        private static bool SamePath(string left, string right)
        {
            return String.Equals(
                Canonical(left),
                Canonical(right),
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
                    " | BEGIN | STRONG_TYPED_POSTSAVE_RECOVERY_ATTEMPT_002");
            }
        }

        private static void Trace(string message)
        {
            File.AppendAllText(
                progressPath,
                DateTime.UtcNow.ToString("o") + " | " + message +
                System.Environment.NewLine,
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
                    "FAIL | " + name + " | " +
                    ex.GetType().FullName + " | " + OneLine(ex.Message));
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
            double[] values = new double[array.Length];
            int index = 0;
            foreach (object item in array)
            {
                values[index++] = Convert.ToDouble(item);
            }
            return values;
        }

        private static Dictionary<string, object>
            ReadAndValidateCoordinateSystem(ModelDoc2 model)
        {
            Feature cursor = null;
            Feature coordinateFeature = null;
            int exactNameCount = 0;
            int coordinateSystemCount = 0;
            string exactFeatureType = null;

            try
            {
                cursor = (Feature)model.FirstFeature();
                while (cursor != null)
                {
                    Feature next = null;
                    bool retain = false;
                    try
                    {
                        next = (Feature)cursor.GetNextFeature();
                        string name = cursor.Name;
                        string type = cursor.GetTypeName2();
                        if (String.Equals(
                            type,
                            "CoordSys",
                            StringComparison.Ordinal))
                        {
                            coordinateSystemCount++;
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
                                retain = true;
                            }
                        }
                    }
                    finally
                    {
                        if (!retain)
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
                coordinateSystemCount == 1,
                "Expected exactly one CoordSys in the document; observed " +
                coordinateSystemCount);
            Require(
                coordinateFeature != null,
                "The uniquely named CoordSys is unavailable");

            CoordinateSystemFeatureData featureData = null;
            MathTransform transform = null;
            bool selectionAccess = false;
            try
            {
                featureData =
                    coordinateFeature.GetDefinition()
                    as CoordinateSystemFeatureData;
                Require(
                    featureData != null,
                    "CoordinateSystemFeatureData is unavailable");
                selectionAccess =
                    featureData.AccessSelections(model, null);
                Require(
                    selectionAccess,
                    "Coordinate-system selection access failed");
                transform = featureData.Transform;
                Require(
                    transform != null,
                    "Coordinate-system transform is unavailable");
                double[] values = ToDoubleArray(transform.ArrayData);
                Require(
                    values.Length == 16,
                    "Expected 16 transform values; observed " +
                    values.Length);

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
                        coordinateSystemCount},
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
                    {"maximum_absolute_identity_error",
                        maximumAbsoluteError},
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

        public static int Run()
        {
            string diagnosticDirectory = Canonical(
                AppDomain.CurrentDomain.BaseDirectory);
            string candidateRoot = Canonical(
                Path.Combine(diagnosticDirectory, "..", ".."));
            string targetPath = Canonical(
                Path.Combine(
                    diagnosticDirectory,
                    "B51R1_SINGLE_CS_DIAGNOSTIC_COPY.SLDPRT"));
            string stageAPath = Canonical(
                Path.Combine(
                    candidateRoot,
                    "02_MASTER_SKELETON",
                    "B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT"));
            string originalFailReceiptPath = Canonical(
                Path.Combine(
                    candidateRoot,
                    "07_VERIFICATION",
                    "B51R1_SINGLE_CS_DIAGNOSTIC_FIRST_LAUNCH_RECEIPT.json"));
            string attempt1FailPath = Canonical(
                Path.Combine(
                    candidateRoot,
                    "07_VERIFICATION",
                    "B51R1_SINGLE_CS_DIAGNOSTIC_POSTSAVE_RECOVERY_FAIL_CLOSED.json"));
            string attempt1ProgressPath = Canonical(
                Path.Combine(
                    candidateRoot,
                    "08_REVIEWS",
                    "B51R1_SINGLE_CS_DIAGNOSTIC_POSTSAVE_RECOVERY_PROGRESS.log"));
            string transformPath = Canonical(
                Path.Combine(
                    candidateRoot,
                    "07_VERIFICATION",
                    "B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM_FIRST_LAUNCH.json"));
            string recoveryReceiptPath = Canonical(
                Path.Combine(
                    candidateRoot,
                    "07_VERIFICATION",
                    "B51R1_SINGLE_CS_DIAGNOSTIC_POSTSAVE_RECOVERY_ATTEMPT_002_RECEIPT.json"));
            string failureReceiptPath = Canonical(
                Path.Combine(
                    candidateRoot,
                    "07_VERIFICATION",
                    "B51R1_SINGLE_CS_DIAGNOSTIC_POSTSAVE_RECOVERY_ATTEMPT_002_FAIL_CLOSED.json"));
            progressPath = Canonical(
                Path.Combine(
                    candidateRoot,
                    "08_REVIEWS",
                    "B51R1_SINGLE_CS_DIAGNOSTIC_POSTSAVE_RECOVERY_ATTEMPT_002_PROGRESS.log"));

            SldWorks swApp = null;
            ModelDoc2 model = null;
            Process solidWorksProcess = null;

            try
            {
                Require(
                    File.Exists(targetPath) &&
                    File.Exists(stageAPath) &&
                    File.Exists(originalFailReceiptPath) &&
                    File.Exists(attempt1FailPath) &&
                    File.Exists(attempt1ProgressPath),
                    "Required immutable inputs or Attempt 1 evidence are missing");
                Require(
                    !File.Exists(transformPath) &&
                    !File.Exists(recoveryReceiptPath) &&
                    !File.Exists(failureReceiptPath) &&
                    !File.Exists(progressPath),
                    "An Attempt 2 output already exists; overwrite refused");

                CreateProgress(progressPath);
                Trace(
                    "CONTRACT | STRONG_TYPED_INTEROP; NO_DOCUMENT_CREATION_SAVE_OPEN_COPY_OR_PROCESS_TERMINATION");

                string originalFailHashBefore = Step(
                    "HASH_ORIGINAL_FAIL_RECEIPT_BEFORE",
                    delegate { return Sha256(originalFailReceiptPath); });
                string attempt1FailHashBefore = Step(
                    "HASH_ATTEMPT_1_FAIL_BEFORE",
                    delegate { return Sha256(attempt1FailPath); });
                string attempt1ProgressHashBefore = Step(
                    "HASH_ATTEMPT_1_PROGRESS_BEFORE",
                    delegate { return Sha256(attempt1ProgressPath); });
                string stageAHashBefore = Step(
                    "HASH_PROTECTED_STAGE_A_BEFORE_READ_ONLY",
                    delegate { return Sha256(stageAPath); });
                Require(
                    String.Equals(
                        stageAHashBefore,
                        ExpectedStageAHash,
                        StringComparison.Ordinal),
                    "Protected Stage A hash does not match frozen value");

                Process[] processes = Step(
                    "VERIFY_SOLE_SLDWORKS_PROCESS_IS_PID_3308",
                    delegate { return Process.GetProcessesByName("SLDWORKS"); });
                Require(
                    processes.Length == 1,
                    "Expected exactly one SLDWORKS process; observed " +
                    processes.Length);
                solidWorksProcess = processes[0];
                Require(
                    solidWorksProcess.Id == AuthorizedProcessId,
                    "The sole SLDWORKS process is not authorized PID 3308");
                solidWorksProcess.Refresh();
                Require(
                    !solidWorksProcess.HasExited &&
                    solidWorksProcess.Responding &&
                    solidWorksProcess.MainWindowHandle != IntPtr.Zero,
                    "Authorized SolidWorks process is not responsive and visible");

                swApp = Step(
                    "ATTACH_STRONG_TYPED_ROT_NO_PROCESS_START",
                    delegate
                    {
                        return (SldWorks)Marshal.GetActiveObject(
                            "SldWorks.Application");
                    });
                Require(swApp != null, "Active SolidWorks object is absent");
                Require(
                    swApp.GetProcessID() == AuthorizedProcessId,
                    "Strong-typed ROT object PID is not 3308");
                Require(
                    swApp.Visible && swApp.StartupProcessCompleted,
                    "Attached SolidWorks is not visible and fully started");
                Require(
                    swApp.GetDocumentCount() == 1,
                    "Expected exactly one open document");

                model = (ModelDoc2)swApp.ActiveDoc;
                Require(model != null, "Active document is unavailable");
                string activePath = model.GetPathName();
                Require(
                    !String.IsNullOrWhiteSpace(activePath) &&
                    SamePath(activePath, targetPath),
                    "Active document is not the fixed diagnostic target");

                Dictionary<string, object> transformEvidence = Step(
                    "READ_STRONG_TYPED_COORDINATE_SYSTEM_TRANSFORM",
                    delegate
                    {
                        return ReadAndValidateCoordinateSystem(model);
                    });

                int externalReferenceCount = Step(
                    "VERIFY_ZERO_EXTERNAL_FILE_REFERENCES",
                    delegate
                    {
                        ModelDocExtension extension = null;
                        try
                        {
                            extension = model.Extension;
                            Require(
                                extension != null,
                                "ModelDocExtension is unavailable");
                            return extension.ListExternalFileReferencesCount();
                        }
                        finally
                        {
                            ReleaseCom(extension);
                        }
                    });
                Require(
                    externalReferenceCount == 0,
                    "Diagnostic target has external references: " +
                    externalReferenceCount);

                string currentTitle = model.GetTitle();
                Require(
                    !String.IsNullOrWhiteSpace(currentTitle),
                    "Current model title is unavailable");
                Step(
                    "CLOSE_TARGET_USING_CURRENT_MODEL_TITLE",
                    delegate
                    {
                        swApp.CloseDoc(currentTitle);
                        return true;
                    });
                ReleaseCom(model);
                model = null;

                Require(
                    swApp.GetDocumentCount() == 0 &&
                    swApp.ActiveDoc == null,
                    "SolidWorks session is not empty after current-title close");

                long targetBytesAfterClose = Step(
                    "READ_TARGET_BYTES_AFTER_CLOSE",
                    delegate { return new FileInfo(targetPath).Length; });
                string targetHashAfterClose = Step(
                    "HASH_TARGET_AFTER_CLOSE",
                    delegate { return Sha256(targetPath); });
                string stageAHashAfter = Step(
                    "HASH_PROTECTED_STAGE_A_AFTER_READ_ONLY",
                    delegate { return Sha256(stageAPath); });
                string originalFailHashAfter = Step(
                    "HASH_ORIGINAL_FAIL_RECEIPT_AFTER",
                    delegate { return Sha256(originalFailReceiptPath); });
                string attempt1FailHashAfter = Step(
                    "HASH_ATTEMPT_1_FAIL_AFTER",
                    delegate { return Sha256(attempt1FailPath); });
                string attempt1ProgressHashAfter = Step(
                    "HASH_ATTEMPT_1_PROGRESS_AFTER",
                    delegate { return Sha256(attempt1ProgressPath); });
                Require(
                    String.Equals(
                        stageAHashBefore,
                        stageAHashAfter,
                        StringComparison.Ordinal) &&
                    String.Equals(
                        originalFailHashBefore,
                        originalFailHashAfter,
                        StringComparison.Ordinal) &&
                    String.Equals(
                        attempt1FailHashBefore,
                        attempt1FailHashAfter,
                        StringComparison.Ordinal) &&
                    String.Equals(
                        attempt1ProgressHashBefore,
                        attempt1ProgressHashAfter,
                        StringComparison.Ordinal),
                    "A protected artifact changed during Attempt 2");

                transformEvidence["schema"] =
                    "SER_B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM_FIRST_LAUNCH_V1";
                transformEvidence["generated_at_utc"] =
                    DateTime.UtcNow.ToString("o");
                transformEvidence["status"] =
                    "TRANSFORM_IDENTITY_CONFIRMED_DURING_POSTSAVE_RECOVERY_COLD_REOPEN_PENDING";
                transformEvidence["evidence_stage"] =
                    "SAME_VISIBLE_PROCESS_POSTSAVE_RECOVERY_ATTEMPT_002_STRONG_TYPED";
                transformEvidence["solidworks_process_id"] =
                    AuthorizedProcessId;
                transformEvidence["target_part"] = targetPath;
                transformEvidence["target_part_bytes"] =
                    targetBytesAfterClose;
                transformEvidence["target_part_sha256"] =
                    targetHashAfterClose;
                transformEvidence["external_file_reference_count"] =
                    externalReferenceCount;
                transformEvidence["protected_stage_a_sha256_before"] =
                    stageAHashBefore;
                transformEvidence["protected_stage_a_sha256_after"] =
                    stageAHashAfter;
                transformEvidence["protected_stage_a_unchanged"] = true;
                transformEvidence["original_fail_receipt_unchanged"] =
                    true;
                transformEvidence["attempt_1_fail_evidence_unchanged"] =
                    true;
                transformEvidence["document_close_method"] =
                    "CloseDoc(model.GetTitle())";
                transformEvidence["document_count_after_close"] = 0;
                transformEvidence["cold_process_reopen_status"] =
                    "NOT_RUN_REQUIRES_SEPARATE_VISIBLE_LAUNCH_AUTHORIZATION";
                transformEvidence["claim_limit"] =
                    "POSTSAVE_TRANSFORM_AND_CLOSE_RECOVERY_ONLY; FULL_SINGLE_CS_DIAGNOSTIC_PASS_NOT_CLAIMED; COLD_REOPEN_NOT_RUN; NO_MASTER_SKELETON_CARRIER_H10_T005_CONTROL_RELEASE_MANUFACTURING_OR_FLIGHT_CREDIT";
                Step(
                    "WRITE_IMMUTABLE_TRANSFORM_EVIDENCE",
                    delegate
                    {
                        WriteJsonCreateNew(
                            transformPath,
                            transformEvidence);
                        return true;
                    });
                string transformHash = Sha256(transformPath);

                DateTime exitRequestedAt = DateTime.UtcNow;
                Step(
                    "REQUEST_NORMAL_EXIT_FROM_EMPTY_SESSION",
                    delegate
                    {
                        Require(
                            swApp.GetDocumentCount() == 0 &&
                            swApp.ActiveDoc == null,
                            "Session is not empty before normal exit");
                        swApp.ExitApp();
                        return true;
                    });
                ReleaseCom(swApp);
                swApp = null;

                bool exited = Step(
                    "WAIT_FOR_NORMAL_PROCESS_EXIT",
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

                var receipt = new Dictionary<string, object>
                {
                    {"schema",
                        "SER_B51R1_SINGLE_CS_DIAGNOSTIC_POSTSAVE_RECOVERY_ATTEMPT_002_V1"},
                    {"generated_at_utc", DateTime.UtcNow.ToString("o")},
                    {"status",
                        "RECOVERED_CLOSE_AND_NORMAL_EXIT_COLD_REOPEN_PENDING"},
                    {"interop_binding", "STRONG_TYPED_SOLIDWORKS_INTEROP"},
                    {"solidworks_process_id", AuthorizedProcessId},
                    {"active_document_count_before", 1},
                    {"active_document_path_before", targetPath},
                    {"coordinate_system_name", CoordinateSystemName},
                    {"coordinate_system_count", 1},
                    {"coordinate_system_transform_identity", true},
                    {"external_file_reference_count",
                        externalReferenceCount},
                    {"close_title_used", currentTitle},
                    {"document_count_after_close", 0},
                    {"target_part_bytes_after_close",
                        targetBytesAfterClose},
                    {"target_part_sha256_after_close",
                        targetHashAfterClose},
                    {"transform_evidence", transformPath},
                    {"transform_evidence_sha256", transformHash},
                    {"protected_stage_a_sha256_before",
                        stageAHashBefore},
                    {"protected_stage_a_sha256_after",
                        stageAHashAfter},
                    {"protected_stage_a_unchanged", true},
                    {"original_fail_receipt_sha256_before",
                        originalFailHashBefore},
                    {"original_fail_receipt_sha256_after",
                        originalFailHashAfter},
                    {"original_fail_receipt_unchanged", true},
                    {"attempt_1_fail_sha256_before",
                        attempt1FailHashBefore},
                    {"attempt_1_fail_sha256_after",
                        attempt1FailHashAfter},
                    {"attempt_1_fail_unchanged", true},
                    {"attempt_1_progress_sha256_before",
                        attempt1ProgressHashBefore},
                    {"attempt_1_progress_sha256_after",
                        attempt1ProgressHashAfter},
                    {"attempt_1_progress_unchanged", true},
                    {"normal_exit_requested_at_utc",
                        exitRequestedAt.ToString("o")},
                    {"solidworks_process_exited", true},
                    {"solidworks_process_exit_code", exitCode},
                    {"cold_process_reopen_status",
                        "NOT_RUN_REQUIRES_SEPARATE_VISIBLE_LAUNCH_AUTHORIZATION"},
                    {"progress_log", progressPath},
                    {"claim_limit",
                        "RECOVERED CLOSE AND NORMAL EXIT ONLY; FULL SINGLE-CS DIAGNOSTIC PASS NOT CLAIMED; COLD REOPEN NOT RUN; NO MASTER-SKELETON CARRIER H10 T005 CONTROL-RELEASE MANUFACTURING OR FLIGHT CREDIT"}
                };
                Step(
                    "WRITE_IMMUTABLE_ATTEMPT_002_RECEIPT",
                    delegate
                    {
                        WriteJsonCreateNew(
                            recoveryReceiptPath,
                            receipt);
                        return true;
                    });
                Trace(
                    "COMPLETE | RECOVERED_CLOSE_AND_NORMAL_EXIT_COLD_REOPEN_PENDING");
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
                                    "SER_B51R1_SINGLE_CS_DIAGNOSTIC_POSTSAVE_RECOVERY_ATTEMPT_002_FAIL_CLOSED_V1"},
                                {"generated_at_utc",
                                    DateTime.UtcNow.ToString("o")},
                                {"status",
                                    "FAIL_CLOSED_POSTSAVE_RECOVERY_ATTEMPT_002"},
                                {"interop_binding",
                                    "STRONG_TYPED_SOLIDWORKS_INTEROP"},
                                {"solidworks_process_id",
                                    AuthorizedProcessId},
                                {"error_type",
                                    ex.GetType().FullName},
                                {"error_message",
                                    OneLine(ex.Message)},
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
}
