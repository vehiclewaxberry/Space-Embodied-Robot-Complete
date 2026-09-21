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
    public static class InsertCoordinateSystemSingleDiagnostic
    {
        private const string ExpectedStageAFileName =
            "B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT";
        private const string DisposablePrefix =
            "B51R1_MASTER_SKELETON_V2_INSERT_CSYS_DIAGNOSTIC_COPY_";
        private const string CoordinateName =
            "CS_INSERT_DIAGNOSTIC_SINGLE";
        private const string ExpectedSolidWorksRevisionPrefix = "32.5.";

        private static string progressPath;

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

        private static T Step<T>(string label, Func<T> action)
        {
            Trace("BEGIN | " + label);
            try
            {
                T result = action();
                Trace("END | " + label);
                return result;
            }
            catch (Exception ex)
            {
                SafeTrace(
                    "FAIL | " + label + " | " + ex.GetType().FullName +
                    " | " + OneLine(ex.Message));
                throw;
            }
        }

        private static string OneLine(string value)
        {
            return (value ?? "").Replace("\r", " ").Replace("\n", " ");
        }

        private static string CanonicalPath(string path)
        {
            if (String.IsNullOrWhiteSpace(path))
            {
                throw new ArgumentException("Path must not be empty");
            }
            return Path.GetFullPath(path);
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

        private static void Require(bool condition, string message)
        {
            if (!condition)
            {
                throw new InvalidOperationException(message);
            }
        }

        private static void RequireSameDirectory(
            string expectedDirectory,
            string path,
            string role)
        {
            string actualDirectory = Path.GetDirectoryName(path);
            Require(
                String.Equals(
                    expectedDirectory,
                    actualDirectory,
                    StringComparison.OrdinalIgnoreCase),
                role + " must remain inside the Stage A directory");
        }

        private static void WriteReceiptNew(
            string path,
            Dictionary<string, object> receipt)
        {
            string json = new JavaScriptSerializer().Serialize(receipt);
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
            }
        }

        private static Feature CreateOneCoordinateSystem(ModelDoc2 model)
        {
            SketchManager sketchManager = model.SketchManager;
            SelectionMgr selectionManager =
                (SelectionMgr)model.SelectionManager;

            Step(
                "OPEN_3D_SKETCH",
                delegate
                {
                    sketchManager.Insert3DSketch(true);
                    return true;
                });

            SketchPoint origin = Step(
                "CREATE_ORIGIN_POINT",
                delegate
                {
                    SketchPoint point = sketchManager.CreatePoint(0, 0, 0);
                    Require(point != null, "CreatePoint returned null");
                    return point;
                });

            SketchSegment xAxis = Step(
                "CREATE_X_AXIS_LINE",
                delegate
                {
                    SketchSegment segment = sketchManager.CreateLine(
                        0, 0, 0, 0.010, 0, 0);
                    Require(segment != null, "X-axis CreateLine returned null");
                    return segment;
                });

            SketchSegment yAxis = Step(
                "CREATE_Y_AXIS_LINE",
                delegate
                {
                    SketchSegment segment = sketchManager.CreateLine(
                        0, 0, 0, 0, 0.010, 0);
                    Require(segment != null, "Y-axis CreateLine returned null");
                    return segment;
                });

            Step(
                "CLOSE_3D_SKETCH",
                delegate
                {
                    sketchManager.Insert3DSketch(true);
                    return true;
                });

            Step(
                "CLEAR_SELECTION_BEFORE_COORDINATE_SYSTEM",
                delegate
                {
                    model.ClearSelection2(true);
                    return true;
                });

            SelectData originSelectionData = Step(
                "CREATE_ORIGIN_SELECT_DATA_MARK_1",
                delegate
                {
                    SelectData data = selectionManager.CreateSelectData();
                    Require(data != null, "Origin CreateSelectData returned null");
                    ((ISelectData)data).Mark = 1;
                    return data;
                });
            Step(
                "SELECT_ORIGIN_MARK_1",
                delegate
                {
                    Require(
                        origin.Select4(false, originSelectionData),
                        "Origin Select4 with mark 1 returned false");
                    return true;
                });

            SelectData xSelectionData = Step(
                "CREATE_X_AXIS_SELECT_DATA_MARK_2",
                delegate
                {
                    SelectData data = selectionManager.CreateSelectData();
                    Require(data != null, "X-axis CreateSelectData returned null");
                    ((ISelectData)data).Mark = 2;
                    return data;
                });
            Step(
                "SELECT_X_AXIS_MARK_2",
                delegate
                {
                    Require(
                        xAxis.Select4(true, xSelectionData),
                        "X-axis Select4 with mark 2 returned false");
                    return true;
                });

            SelectData ySelectionData = Step(
                "CREATE_Y_AXIS_SELECT_DATA_MARK_4",
                delegate
                {
                    SelectData data = selectionManager.CreateSelectData();
                    Require(data != null, "Y-axis CreateSelectData returned null");
                    ((ISelectData)data).Mark = 4;
                    return data;
                });
            Step(
                "SELECT_Y_AXIS_MARK_4",
                delegate
                {
                    Require(
                        yAxis.Select4(true, ySelectionData),
                        "Y-axis Select4 with mark 4 returned false");
                    return true;
                });

            Feature coordinateFeature = Step(
                "CALL_FEATUREMANAGER_INSERT_COORDINATE_SYSTEM",
                delegate
                {
                    Feature feature = model.FeatureManager.InsertCoordinateSystem(
                        false,
                        false,
                        false);
                    Require(
                        feature != null,
                        "InsertCoordinateSystem returned null");
                    return feature;
                });

            Step(
                "RENAME_AND_VERIFY_COORDINATE_FEATURE",
                delegate
                {
                    coordinateFeature.Name = CoordinateName;
                    Require(
                        String.Equals(
                            coordinateFeature.Name,
                            CoordinateName,
                            StringComparison.Ordinal),
                        "Coordinate-system feature rename did not persist");
                    Require(
                        !String.IsNullOrWhiteSpace(
                            coordinateFeature.GetTypeName2()),
                        "Coordinate-system feature type is empty");
                    return true;
                });

            Step(
                "CLEAR_SELECTION_AFTER_COORDINATE_SYSTEM",
                delegate
                {
                    model.ClearSelection2(true);
                    return true;
                });

            return coordinateFeature;
        }

        [STAThread]
        public static int Run(
            string protectedStageAPath,
            string disposableCopyPath,
            string receiptFilePath,
            string progressFilePath)
        {
            string source = CanonicalPath(protectedStageAPath);
            string disposable = CanonicalPath(disposableCopyPath);
            string receiptPath = CanonicalPath(receiptFilePath);
            progressPath = CanonicalPath(progressFilePath);

            string sourceDirectory = Path.GetDirectoryName(source);
            string sourceHashBefore = null;
            string sourceHashAfter = null;
            string disposableHashBeforeCad = null;
            SldWorks swApp = null;
            ModelDoc2 model = null;
            Process solidWorksProcess = null;

            var receipt = new Dictionary<string, object>
            {
                {"schema", "SER_B51R1_INSERT_COORDINATE_SYSTEM_SINGLE_DIAGNOSTIC_V1"},
                {"generated_at_utc", DateTime.UtcNow.ToString("o")},
                {"status", "FAIL_NOT_STARTED"},
                {"protected_stage_a", source},
                {"disposable_copy", disposable},
                {"progress_log", progressPath},
                {"coordinate_feature_name", CoordinateName},
                {"api_method", "IFeatureManager.InsertCoordinateSystem(Boolean,Boolean,Boolean)"},
                {"selection_marks", new Dictionary<string, object>
                    {
                        {"origin", 1},
                        {"x_axis", 2},
                        {"y_axis", 4},
                        {"z_axis_not_used", 8}
                    }},
                {"runtime_contract", new Dictionary<string, object>
                    {
                        {"solidworks_launch_permitted", false},
                        {"attachment_method", "Marshal.GetActiveObject"},
                        {"required_process_count", 1},
                        {"required_process_responding", true},
                        {"required_visible_main_window", true},
                        {"required_empty_document_session", true},
                        {"required_attached_process_identity_match", true},
                        {"protected_stage_a_direct_open_permitted", false}
                    }},
                {"claim_limit",
                    "SINGLE_DISPOSABLE_COPY_API_DIAGNOSTIC_ONLY_NO_MASTER_SKELETON_GATE_H10_T005_LOAD_PATH_MANUFACTURING_OR_FLIGHT_CREDIT"}
            };

            try
            {
                using (FileStream progressStream = new FileStream(
                    progressPath,
                    FileMode.CreateNew,
                    FileAccess.Write,
                    FileShare.Read))
                using (StreamWriter progressWriter = new StreamWriter(
                    progressStream,
                    new UTF8Encoding(false)))
                {
                    progressWriter.WriteLine(
                        DateTime.UtcNow.ToString("o") +
                        " | START | B51R1_INSERT_COORDINATE_SYSTEM_SINGLE_DIAGNOSTIC_V1");
                }

                Step(
                    "PREFLIGHT_PATH_CONTAINMENT_AND_NO_OVERWRITE",
                    delegate
                    {
                        Require(
                            String.Equals(
                                Path.GetFileName(source),
                                ExpectedStageAFileName,
                                StringComparison.OrdinalIgnoreCase),
                            "Protected source filename is not the validated Stage A name");
                        Require(
                            File.Exists(source),
                            "Protected Stage A source does not exist");
                        Require(
                            !String.Equals(
                                source,
                                disposable,
                                StringComparison.OrdinalIgnoreCase),
                            "Disposable path must not equal protected Stage A path");
                        RequireSameDirectory(
                            sourceDirectory,
                            disposable,
                            "Disposable copy");
                        RequireSameDirectory(
                            sourceDirectory,
                            receiptPath,
                            "Receipt");
                        RequireSameDirectory(
                            sourceDirectory,
                            progressPath,
                            "Progress log");
                        Require(
                            Path.GetFileName(disposable).StartsWith(
                                DisposablePrefix,
                                StringComparison.OrdinalIgnoreCase),
                            "Disposable filename does not use the diagnostic prefix");
                        Require(
                            String.Equals(
                                Path.GetExtension(disposable),
                                ".SLDPRT",
                                StringComparison.OrdinalIgnoreCase),
                            "Disposable copy must be an SLDPRT");
                        Require(
                            !File.Exists(disposable),
                            "Disposable copy already exists; overwrite refused");
                        Require(
                            !File.Exists(receiptPath),
                            "Receipt already exists; overwrite refused");
                        return true;
                    });

                sourceHashBefore = Step(
                    "HASH_PROTECTED_STAGE_A_BEFORE",
                    delegate { return Sha256(source); });
                receipt["protected_stage_a_sha256_before"] = sourceHashBefore;

                solidWorksProcess = Step(
                    "VERIFY_EXACTLY_ONE_SOLIDWORKS_PROCESS",
                    delegate
                    {
                        Process[] processes =
                            Process.GetProcessesByName("SLDWORKS");
                        Require(
                            processes.Length == 1,
                            "Expected exactly one externally started SLDWORKS process; observed " +
                            processes.Length);
                        return processes[0];
                    });
                receipt["solidworks_process_id"] = solidWorksProcess.Id;

                Step(
                    "VERIFY_SOLIDWORKS_PROCESS_RESPONDING_VISIBLE_WINDOW",
                    delegate
                    {
                        solidWorksProcess.Refresh();
                        Require(
                            !solidWorksProcess.HasExited,
                            "SLDWORKS process exited during preflight");
                        Require(
                            solidWorksProcess.Responding,
                            "SLDWORKS process is not responding");
                        Require(
                            solidWorksProcess.MainWindowHandle != IntPtr.Zero,
                            "SLDWORKS process has no visible main-window handle");
                        receipt["solidworks_main_window_title"] =
                            solidWorksProcess.MainWindowTitle;
                        return true;
                    });

                Step(
                    "VERIFY_PROTECTED_STAGE_A_READABLE",
                    delegate
                    {
                        using (FileStream stream = new FileStream(
                            source,
                            FileMode.Open,
                            FileAccess.Read,
                            FileShare.Read))
                        {
                            Require(
                                stream.Length > 0,
                                "Protected Stage A source is empty");
                        }
                        return true;
                    });

                Step(
                    "COPY_PROTECTED_STAGE_A_TO_DISPOSABLE",
                    delegate
                    {
                        File.Copy(source, disposable, false);
                        Require(
                            File.Exists(disposable),
                            "Disposable copy was not created");
                        return true;
                    });

                disposableHashBeforeCad = Step(
                    "VERIFY_DISPOSABLE_COPY_HASH_MATCHES_SOURCE",
                    delegate
                    {
                        string sourceHashAfterCopy = Sha256(source);
                        string copyHash = Sha256(disposable);
                        Require(
                            String.Equals(
                                sourceHashBefore,
                                sourceHashAfterCopy,
                                StringComparison.Ordinal),
                            "Protected Stage A changed during copy");
                        Require(
                            String.Equals(
                                sourceHashBefore,
                                copyHash,
                                StringComparison.Ordinal),
                            "Disposable copy hash does not match protected Stage A");
                        return copyHash;
                    });
                receipt["disposable_sha256_before_cad"] =
                    disposableHashBeforeCad;

                swApp = Step(
                    "ATTACH_ROT_ACTIVE_SOLIDWORKS_NO_LAUNCH",
                    delegate
                    {
                        object active =
                            Marshal.GetActiveObject("SldWorks.Application");
                        Require(
                            active != null,
                            "ROT returned no active SolidWorks object");
                        return (SldWorks)active;
                    });

                Step(
                    "VERIFY_ATTACHED_SESSION_IDENTITY_VISIBLE_EMPTY_2024_SP5",
                    delegate
                    {
                        string revision = swApp.RevisionNumber();
                        int attachedProcessId = swApp.GetProcessID();
                        Require(
                            attachedProcessId == solidWorksProcess.Id,
                            "ROT object process ID does not match the sole SLDWORKS process");
                        Require(
                            swApp.Visible,
                            "Attached SolidWorks application is not visible");
                        Require(
                            swApp.StartupProcessCompleted,
                            "SolidWorks startup process is not complete");
                        Require(
                            revision != null &&
                            revision.StartsWith(
                                ExpectedSolidWorksRevisionPrefix,
                                StringComparison.Ordinal),
                            "Expected SolidWorks 2024 SP5 revision prefix " +
                            ExpectedSolidWorksRevisionPrefix +
                            " but observed " + revision);
                        Require(
                            swApp.GetDocumentCount() == 0 &&
                            swApp.ActiveDoc == null,
                            "Attached SolidWorks session must contain zero documents");
                        receipt["solidworks_revision"] = revision;
                        receipt["attached_process_id"] = attachedProcessId;
                        return true;
                    });

                int openErrors = 0;
                int openWarnings = 0;
                model = Step(
                    "OPEN_DISPOSABLE_COPY_ONLY",
                    delegate
                    {
                        ModelDoc2 opened = (ModelDoc2)swApp.OpenDoc6(
                            disposable,
                            1,
                            1,
                            "",
                            ref openErrors,
                            ref openWarnings);
                        Require(opened != null, "OpenDoc6 returned null");
                        Require(
                            openErrors == 0,
                            "OpenDoc6 errors=" + openErrors +
                            " warnings=" + openWarnings);
                        return opened;
                    });
                receipt["open_errors"] = openErrors;
                receipt["open_warnings"] = openWarnings;

                Step(
                    "VERIFY_OPENED_PATH_IS_DISPOSABLE_NOT_PROTECTED_SOURCE",
                    delegate
                    {
                        string openedPath = CanonicalPath(model.GetPathName());
                        Require(
                            String.Equals(
                                openedPath,
                                disposable,
                                StringComparison.OrdinalIgnoreCase),
                            "Opened document is not the disposable copy");
                        Require(
                            !String.Equals(
                                openedPath,
                                source,
                                StringComparison.OrdinalIgnoreCase),
                            "Protected Stage A was opened directly");
                        return true;
                    });

                Feature coordinateFeature = CreateOneCoordinateSystem(model);
                receipt["coordinate_feature_type"] =
                    coordinateFeature.GetTypeName2();

                Step(
                    "FORCE_REBUILD_DISPOSABLE_COPY",
                    delegate
                    {
                        Require(
                            model.ForceRebuild3(false),
                            "ForceRebuild3 returned false");
                        return true;
                    });

                int saveErrors = 0;
                int saveWarnings = 0;
                Step(
                    "SAVE_DISPOSABLE_COPY_IN_PLACE",
                    delegate
                    {
                        bool saved = model.Save3(
                            1,
                            ref saveErrors,
                            ref saveWarnings);
                        Require(
                            saved && saveErrors == 0,
                            "Save3 failed saved=" + saved +
                            " errors=" + saveErrors +
                            " warnings=" + saveWarnings);
                        return true;
                    });
                receipt["save_errors"] = saveErrors;
                receipt["save_warnings"] = saveWarnings;

                string disposableTitle = model.GetTitle();
                Step(
                    "CLOSE_DISPOSABLE_COPY_BEFORE_HASH",
                    delegate
                    {
                        swApp.CloseDoc(disposableTitle);
                        return true;
                    });
                model = null;

                Step(
                    "VERIFY_ATTACHED_SESSION_EMPTY_AFTER_CLOSE",
                    delegate
                    {
                        Require(
                            swApp.GetDocumentCount() == 0 &&
                            swApp.ActiveDoc == null,
                            "SolidWorks session is not empty after closing diagnostic copy");
                        return true;
                    });

                string disposableHashAfterCad = Step(
                    "HASH_DISPOSABLE_COPY_AFTER_CLOSE",
                    delegate { return Sha256(disposable); });
                sourceHashAfter = Step(
                    "HASH_PROTECTED_STAGE_A_AFTER",
                    delegate { return Sha256(source); });

                Step(
                    "VERIFY_PROTECTED_STAGE_A_UNCHANGED",
                    delegate
                    {
                        Require(
                            String.Equals(
                                sourceHashBefore,
                                sourceHashAfter,
                                StringComparison.Ordinal),
                            "Protected Stage A hash changed");
                        return true;
                    });

                receipt["protected_stage_a_sha256_after"] = sourceHashAfter;
                receipt["protected_stage_a_unchanged"] = true;
                receipt["disposable_sha256_after_close"] =
                    disposableHashAfterCad;
                receipt["disposable_bytes_after_close"] =
                    new FileInfo(disposable).Length;
                receipt["document_count_final"] = swApp.GetDocumentCount();
                receipt["status"] =
                    "PASS_SINGLE_INSERT_COORDINATE_SYSTEM_ON_DISPOSABLE_COPY";
                receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");

                Step(
                    "WRITE_PASS_RECEIPT",
                    delegate
                    {
                        WriteReceiptNew(receiptPath, receipt);
                        return true;
                    });
                Trace(
                    "PASS | PASS_SINGLE_INSERT_COORDINATE_SYSTEM_ON_DISPOSABLE_COPY");

                if (swApp != null)
                {
                    Marshal.FinalReleaseComObject(swApp);
                    swApp = null;
                }
                return 0;
            }
            catch (Exception ex)
            {
                SafeTrace(
                    "FAIL_CLOSED | " + ex.GetType().FullName +
                    " | " + OneLine(ex.Message));
                receipt["status"] = "FAIL_CLOSED";
                receipt["failed_at_utc"] = DateTime.UtcNow.ToString("o");
                receipt["error_type"] = ex.GetType().FullName;
                receipt["error_message"] = ex.Message;
                receipt["error_hresult"] =
                    "0x" + ex.HResult.ToString("X8");

                try
                {
                    if (swApp != null && model != null)
                    {
                        string openedPath = CanonicalPath(model.GetPathName());
                        if (String.Equals(
                            openedPath,
                            disposable,
                            StringComparison.OrdinalIgnoreCase))
                        {
                            swApp.CloseDoc(model.GetTitle());
                            SafeTrace(
                                "FAIL_CLOSED_CLEANUP | CLOSED_DISPOSABLE_COPY_ONLY");
                        }
                    }
                }
                catch (Exception closeException)
                {
                    receipt["cleanup_close_error"] =
                        OneLine(closeException.Message);
                    SafeTrace(
                        "FAIL_CLOSED_CLEANUP_ERROR | " +
                        closeException.GetType().FullName +
                        " | " + OneLine(closeException.Message));
                }

                try
                {
                    if (File.Exists(source))
                    {
                        sourceHashAfter = Sha256(source);
                        receipt["protected_stage_a_sha256_after_if_available"] =
                            sourceHashAfter;
                        receipt["protected_stage_a_unchanged_if_available"] =
                            sourceHashBefore != null &&
                            String.Equals(
                                sourceHashBefore,
                                sourceHashAfter,
                                StringComparison.Ordinal);
                    }
                }
                catch (Exception hashException)
                {
                    receipt["protected_hash_after_error"] =
                        OneLine(hashException.Message);
                }

                try
                {
                    if (!File.Exists(receiptPath))
                    {
                        WriteReceiptNew(receiptPath, receipt);
                    }
                }
                catch (Exception receiptException)
                {
                    SafeTrace(
                        "FAIL_CLOSED_RECEIPT_ERROR | " +
                        receiptException.GetType().FullName +
                        " | " + OneLine(receiptException.Message));
                }

                if (swApp != null)
                {
                    try
                    {
                        Marshal.FinalReleaseComObject(swApp);
                    }
                    catch
                    {
                    }
                }
                return 1;
            }
        }
    }
}
