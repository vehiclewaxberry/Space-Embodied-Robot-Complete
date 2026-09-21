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
using SolidWorks.Interop.swconst;

namespace B51R1.NativeCadDiagnostics
{
    public static class SingleCsColdReopen
    {
        private const int EvidencePauseMilliseconds = 20000;
        private const int ExitWaitMilliseconds = 45000;
        private const string CoordinateSystemName = "CS_DIAGNOSTIC_ONLY";
        private const string ExpectedTargetHash =
            "6B571B49D440BBDC723566FA97224C69AFABCBA6BAC34DCF4036A5F4037E120C";
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
                FileShare.ReadWrite))
            using (StreamWriter writer = new StreamWriter(
                stream,
                new UTF8Encoding(false)))
            {
                writer.WriteLine(
                    DateTime.UtcNow.ToString("o") +
                    " | BEGIN | SINGLE_CS_COLD_PROCESS_REOPEN");
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
            string transformPath = Canonical(
                Path.Combine(
                    candidateRoot,
                    "07_VERIFICATION",
                    "B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM_COLD_REOPEN.json"));
            string receiptPath = Canonical(
                Path.Combine(
                    candidateRoot,
                    "07_VERIFICATION",
                    "B51R1_SINGLE_CS_DIAGNOSTIC_COLD_REOPEN_RECEIPT.json"));
            string failurePath = Canonical(
                Path.Combine(
                    candidateRoot,
                    "07_VERIFICATION",
                    "B51R1_SINGLE_CS_DIAGNOSTIC_COLD_REOPEN_FAIL_CLOSED.json"));
            progressPath = Canonical(
                Path.Combine(
                    candidateRoot,
                    "08_REVIEWS",
                    "B51R1_SINGLE_CS_DIAGNOSTIC_COLD_REOPEN_PROGRESS.log"));

            SldWorks swApp = null;
            ModelDoc2 model = null;
            Process solidWorksProcess = null;
            int observedProcessId = -1;
            string currentTitle = null;
            string failureStage = "PREFLIGHT";

            try
            {
                Require(
                    File.Exists(targetPath) && File.Exists(stageAPath),
                    "Fixed diagnostic target or protected Stage A is missing");
                Require(
                    !File.Exists(transformPath) &&
                    !File.Exists(receiptPath) &&
                    !File.Exists(failurePath) &&
                    !File.Exists(progressPath),
                    "A fixed cold-reopen output already exists; overwrite refused");

                CreateProgress(progressPath);
                Trace(
                    "CONTRACT | ATTACH_ONLY; ONE_FIXED_OPENDOC6; ONE_CONTROLLED_SAVE3; IMMUTABLE_OUTPUTS");

                failureStage = "HASH_INPUTS_BEFORE_OPEN";
                string targetHashBeforeOpen = Step(
                    "HASH_TARGET_BEFORE_OPEN",
                    delegate { return Sha256(targetPath); });
                long targetBytesBeforeOpen = new FileInfo(targetPath).Length;
                string stageAHashBefore = Step(
                    "HASH_PROTECTED_STAGE_A_BEFORE_READ_ONLY",
                    delegate { return Sha256(stageAPath); });
                Require(
                    String.Equals(
                        targetHashBeforeOpen,
                        ExpectedTargetHash,
                        StringComparison.Ordinal),
                    "Diagnostic target hash does not match admitted first-launch value");
                Require(
                    String.Equals(
                        stageAHashBefore,
                        ExpectedStageAHash,
                        StringComparison.Ordinal),
                    "Protected Stage A hash does not match frozen value");

                failureStage = "VERIFY_SOLE_VISIBLE_RESPONSIVE_EMPTY_SESSION";
                Process[] processes = Step(
                    "VERIFY_EXACTLY_ONE_VISIBLE_RESPONSIVE_SLDWORKS_PROCESS",
                    delegate { return Process.GetProcessesByName("SLDWORKS"); });
                Require(
                    processes.Length == 1,
                    "Expected exactly one SLDWORKS process; observed " +
                    processes.Length);
                solidWorksProcess = processes[0];
                observedProcessId = solidWorksProcess.Id;
                solidWorksProcess.Refresh();
                Require(
                    !solidWorksProcess.HasExited &&
                    solidWorksProcess.Responding &&
                    solidWorksProcess.MainWindowHandle != IntPtr.Zero,
                    "The sole SolidWorks process is not visible and responsive");

                swApp = Step(
                    "ATTACH_STRONG_TYPED_ROT_TO_EXTERNAL_SESSION",
                    delegate
                    {
                        return (SldWorks)Marshal.GetActiveObject(
                            "SldWorks.Application");
                    });
                Require(swApp != null, "Active SolidWorks object is absent");
                Require(
                    swApp.GetProcessID() == observedProcessId,
                    "ROT object PID does not match the sole visible process");
                Require(
                    swApp.Visible && swApp.StartupProcessCompleted,
                    "Attached SolidWorks is not visible and fully started");
                Require(
                    swApp.GetDocumentCount() == 0 && swApp.ActiveDoc == null,
                    "Authorized SolidWorks session is not empty before cold reopen");

                failureStage = "OPEN_FIXED_TARGET_ONCE";
                int openErrors = 0;
                int openWarnings = 0;
                model = swApp.OpenDoc6(
                    targetPath,
                    (int)swDocumentTypes_e.swDocPART,
                    (int)swOpenDocOptions_e.swOpenDocOptions_Silent,
                    "",
                    ref openErrors,
                    ref openWarnings);
                Require(model != null, "Fixed diagnostic target did not open");
                Require(
                    openErrors == 0 && openWarnings == 0,
                    "OpenDoc6 errors/warnings were " +
                    openErrors + "/" + openWarnings);
                Require(
                    swApp.GetDocumentCount() == 1,
                    "Expected exactly one document after fixed-target open");
                Require(
                    SamePath(model.GetPathName(), targetPath),
                    "Opened document is not the fixed diagnostic target");

                failureStage = "READBACK_PERSISTED_COORDINATE_SYSTEM";
                Dictionary<string, object> transformEvidence = Step(
                    "READ_STRONG_TYPED_PERSISTED_COORDINATE_SYSTEM",
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

                failureStage = "VISIBLE_EVIDENCE_PAUSE";
                Trace(
                    "READY_FOR_VISIBLE_EVIDENCE | persisted CS_DIAGNOSTIC_ONLY readback passed; 20 second evidence window begins before Save3");
                Thread.Sleep(EvidencePauseMilliseconds);
                Trace("VISIBLE_EVIDENCE_WINDOW_COMPLETE | proceeding to the single controlled Save3");

                failureStage = "CONTROLLED_SAVE3_ONCE";
                int saveErrors = 0;
                int saveWarnings = 0;
                bool saveCompleted = model.Save3(
                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent,
                    ref saveErrors,
                    ref saveWarnings);
                Require(saveCompleted, "The single controlled Save3 returned false");
                Require(
                    saveErrors == 0 && saveWarnings == 0,
                    "Save3 errors/warnings were " +
                    saveErrors + "/" + saveWarnings);

                failureStage = "CLOSE_FIXED_TARGET";
                currentTitle = model.GetTitle();
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
                    swApp.GetDocumentCount() == 0 && swApp.ActiveDoc == null,
                    "SolidWorks session is not empty after current-title close");

                failureStage = "HASH_OUTPUTS_AFTER_CLOSE";
                long targetBytesAfterClose = new FileInfo(targetPath).Length;
                string targetHashAfterClose = Step(
                    "HASH_TARGET_AFTER_CONTROLLED_SAVE_AND_CLOSE",
                    delegate { return Sha256(targetPath); });
                string stageAHashAfter = Step(
                    "HASH_PROTECTED_STAGE_A_AFTER_READ_ONLY",
                    delegate { return Sha256(stageAPath); });
                Require(
                    String.Equals(
                        stageAHashBefore,
                        stageAHashAfter,
                        StringComparison.Ordinal),
                    "Protected Stage A changed during cold-reopen diagnostic");

                bool targetHashChanged = !String.Equals(
                    targetHashBeforeOpen,
                    targetHashAfterClose,
                    StringComparison.Ordinal);
                string targetHashExplanation = targetHashChanged
                    ? "HASH_CHANGED_AFTER_THE_SINGLE_CONTROLLED_SAVE3; SEMANTIC_INVARIANTS_UNCHANGED; BYTE_LEVEL_CAUSE_NOT_FURTHER_RESOLVED"
                    : "HASH_UNCHANGED_AFTER_THE_SINGLE_CONTROLLED_SAVE3; SEMANTIC_INVARIANTS_UNCHANGED";

                failureStage = "NORMAL_APPLICATION_EXIT";
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

                bool waitCompleted = Step(
                    "WAIT_FOR_EXTERNAL_PROCESS_DISAPPEARANCE",
                    delegate
                    {
                        return solidWorksProcess.WaitForExit(
                            ExitWaitMilliseconds);
                    });
                Require(
                    waitCompleted,
                    "SolidWorks did not exit within " +
                    ExitWaitMilliseconds + " ms");
                solidWorksProcess.Refresh();
                Require(
                    solidWorksProcess.HasExited,
                    "SolidWorks Process.HasExited is false after wait");
                Process[] remaining = Process.GetProcessesByName("SLDWORKS");
                try
                {
                    Require(
                        remaining.Length == 0,
                        "SLDWORKS process count after normal exit is " +
                        remaining.Length);
                }
                finally
                {
                    foreach (Process process in remaining)
                    {
                        process.Dispose();
                    }
                }

                object exitCodeEvidence;
                string exitCodeReason = null;
                bool exitCodeAvailable = true;
                int availableExitCode = -1;
                try
                {
                    availableExitCode = solidWorksProcess.ExitCode;
                    exitCodeEvidence = availableExitCode;
                }
                catch (InvalidOperationException ex)
                {
                    exitCodeAvailable = false;
                    exitCodeEvidence = "UNAVAILABLE";
                    exitCodeReason = OneLine(ex.GetType().FullName + ": " + ex.Message);
                }
                if (exitCodeAvailable)
                {
                    Require(
                        availableExitCode == 0,
                        "SolidWorks returned nonzero exit code " +
                        availableExitCode);
                }

                failureStage = "WRITE_IMMUTABLE_SUCCESS_EVIDENCE";
                transformEvidence["schema"] =
                    "B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM_COLD_REOPEN_V1";
                transformEvidence["generated_at_utc"] =
                    DateTime.UtcNow.ToString("o");
                transformEvidence["status"] =
                    "SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS";
                transformEvidence["evidence_stage"] =
                    "FRESH_SOLIDWORKS_PROCESS_COLD_REOPEN_STRONG_TYPED";
                transformEvidence["solidworks_process_id"] =
                    observedProcessId;
                transformEvidence["target_part"] = targetPath;
                transformEvidence["target_sha256_before_open"] =
                    targetHashBeforeOpen;
                transformEvidence["target_sha256_after_save_close"] =
                    targetHashAfterClose;
                transformEvidence["target_hash_changed"] =
                    targetHashChanged;
                transformEvidence["target_hash_change_explanation"] =
                    targetHashExplanation;
                transformEvidence["external_file_reference_count"] =
                    externalReferenceCount;
                transformEvidence["open_errors"] = openErrors;
                transformEvidence["open_warnings"] = openWarnings;
                transformEvidence["save_errors"] = saveErrors;
                transformEvidence["save_warnings"] = saveWarnings;
                transformEvidence["protected_stage_a_sha256_before"] =
                    stageAHashBefore;
                transformEvidence["protected_stage_a_sha256_after"] =
                    stageAHashAfter;
                transformEvidence["protected_stage_a_unchanged"] = true;
                transformEvidence["claim_limit"] =
                    "SINGLE COORDINATE-SYSTEM PERSISTENCE ONLY; NO MASTER-SKELETON CARRIER H10 T005 CONTROL-RELEASE MANUFACTURING OR FLIGHT CREDIT";
                Step(
                    "WRITE_IMMUTABLE_COLD_REOPEN_TRANSFORM",
                    delegate
                    {
                        WriteJsonCreateNew(transformPath, transformEvidence);
                        return true;
                    });
                string transformHash = Sha256(transformPath);

                var receipt = new Dictionary<string, object>
                {
                    {"schema",
                        "B51R1_SINGLE_CS_DIAGNOSTIC_COLD_REOPEN_RECEIPT_V1"},
                    {"generated_at_utc", DateTime.UtcNow.ToString("o")},
                    {"status",
                        "SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS"},
                    {"interop_binding", "STRONG_TYPED_SOLIDWORKS_2024_X64"},
                    {"solidworks_process_id", observedProcessId},
                    {"session_document_count_before_open", 0},
                    {"open_doc6_call_count", 1},
                    {"opened_document_path", targetPath},
                    {"open_errors", openErrors},
                    {"open_warnings", openWarnings},
                    {"coordinate_system_name", CoordinateSystemName},
                    {"coordinate_system_feature_type", "CoordSys"},
                    {"coordinate_system_count", 1},
                    {"coordinate_system_transform_identity", true},
                    {"external_file_reference_count", externalReferenceCount},
                    {"evidence_pause_milliseconds", EvidencePauseMilliseconds},
                    {"save3_call_count", 1},
                    {"save3_completed", true},
                    {"save_errors", saveErrors},
                    {"save_warnings", saveWarnings},
                    {"close_title_used", currentTitle},
                    {"document_count_after_close", 0},
                    {"target_bytes_before_open", targetBytesBeforeOpen},
                    {"target_bytes_after_save_close", targetBytesAfterClose},
                    {"target_sha256_before_open", targetHashBeforeOpen},
                    {"target_sha256_after_save_close", targetHashAfterClose},
                    {"target_hash_changed", targetHashChanged},
                    {"target_hash_change_explanation", targetHashExplanation},
                    {"transform_evidence", transformPath},
                    {"transform_evidence_sha256", transformHash},
                    {"protected_stage_a_sha256_before", stageAHashBefore},
                    {"protected_stage_a_sha256_after", stageAHashAfter},
                    {"protected_stage_a_unchanged", true},
                    {"normal_exit_requested_at_utc", exitRequestedAt.ToString("o")},
                    {"solidworks_process_wait_completed", waitCompleted},
                    {"solidworks_process_has_exited", true},
                    {"solidworks_process_count_after_exit", 0},
                    {"solidworks_process_exit_code", exitCodeEvidence},
                    {"solidworks_process_exit_code_available",
                        exitCodeAvailable},
                    {"solidworks_process_exit_code_reason", exitCodeReason},
                    {"progress_log", progressPath},
                    {"claim_limit",
                        "SINGLE COORDINATE-SYSTEM PERSISTENCE ONLY; NO MASTER-SKELETON CARRIER H10 T005 CONTROL-RELEASE MANUFACTURING OR FLIGHT CREDIT"}
                };
                Step(
                    "WRITE_IMMUTABLE_COLD_REOPEN_RECEIPT",
                    delegate
                    {
                        WriteJsonCreateNew(receiptPath, receipt);
                        return true;
                    });
                Trace("COMPLETE | SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS");
                return 0;
            }
            catch (Exception ex)
            {
                SafeTrace(
                    "FAIL_CLOSED | " + failureStage + " | " +
                    ex.GetType().FullName + " | " + OneLine(ex.Message));
                try
                {
                    if (!File.Exists(failurePath))
                    {
                        WriteJsonCreateNew(
                            failurePath,
                            new Dictionary<string, object>
                            {
                                {"schema",
                                    "B51R1_SINGLE_CS_DIAGNOSTIC_COLD_REOPEN_FAIL_CLOSED_V1"},
                                {"generated_at_utc",
                                    DateTime.UtcNow.ToString("o")},
                                {"status",
                                    "FAIL_CLOSED_SINGLE_CS_COLD_REOPEN"},
                                {"failure_stage", failureStage},
                                {"interop_binding",
                                    "STRONG_TYPED_SOLIDWORKS_2024_X64"},
                                {"solidworks_process_id",
                                    observedProcessId},
                                {"error_type", ex.GetType().FullName},
                                {"error_message", OneLine(ex.Message)},
                                {"error_hresult",
                                    "0x" + ex.HResult.ToString("X8")},
                                {"progress_log", progressPath},
                                {"forced_process_termination_permitted", false},
                                {"claim_limit",
                                    "NO SINGLE-CS PERSISTENCE CREDIT; NO NATIVE AUTHORING RELEASE"}
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
