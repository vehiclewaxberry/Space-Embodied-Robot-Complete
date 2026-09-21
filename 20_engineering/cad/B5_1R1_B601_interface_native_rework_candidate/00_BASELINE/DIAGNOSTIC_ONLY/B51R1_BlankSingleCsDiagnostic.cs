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

namespace B51R1.NativeCadDiagnostics
{
    public static class BlankSingleCsDiagnostic
    {
        private const string ExpectedCandidateDirectoryName =
            "B5_1R1_B601_interface_native_rework_candidate";
        private const string ExpectedDiagnosticDirectoryName =
            "DIAGNOSTIC_ONLY";
        private const string ExpectedTargetFileName =
            "B51R1_SINGLE_CS_DIAGNOSTIC_COPY.SLDPRT";
        private const string ExpectedReceiptFileName =
            "B51R1_SINGLE_CS_DIAGNOSTIC_FIRST_LAUNCH_RECEIPT.json";
        private const string ExpectedProgressFileName =
            "B51R1_SINGLE_CS_DIAGNOSTIC_FIRST_LAUNCH_PROGRESS.log";
        private const string ExpectedTransformFileName =
            "B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM_FIRST_LAUNCH.json";
        private const string ProtectedStageAFileName =
            "B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT";
        private const string CoordinateSystemName = "CS_DIAGNOSTIC_ONLY";
        private const string ExpectedSolidWorksRevisionPrefix = "32.5.";
        private const int DefaultPartTemplatePreference = 8;
        private const int PartDocumentType = 1;
        private const int SaveCurrentVersion = 0;
        private const int SaveSilent = 1;
        private const int ProcessExitWaitMilliseconds = 20000;

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

        private static void Require(bool condition, string message)
        {
            if (!condition)
            {
                throw new InvalidOperationException(message);
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
                writer.WriteLine();
            }
        }

        private static void ReleaseComObject(object value)
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
            Require(array != null, "Expected a COM numeric array");
            double[] values = new double[array.Length];
            int index = 0;
            foreach (object item in array)
            {
                values[index++] = Convert.ToDouble(item);
            }
            return values;
        }

        private static double VectorNorm(double[] vector)
        {
            return Math.Sqrt(
                vector[0] * vector[0] +
                vector[1] * vector[1] +
                vector[2] * vector[2]);
        }

        private static double Dot(double[] left, double[] right)
        {
            return
                left[0] * right[0] +
                left[1] * right[1] +
                left[2] * right[2];
        }

        private static Dictionary<string, object> InspectBlankReferenceGeometry(
            ModelDoc2 model)
        {
            var planeRecords =
                new List<Dictionary<string, object>>();
            var normals = new List<double[]>();
            var originRecords =
                new List<Dictionary<string, object>>();
            int allReferencePlaneCount = 0;
            Feature cursor = null;

            try
            {
                cursor = (Feature)model.FirstFeature();
                while (cursor != null)
                {
                    Feature next = null;
                    try
                    {
                        next = (Feature)cursor.GetNextFeature();
                        string typeName = cursor.GetTypeName2() ?? "";
                        if (String.Equals(
                            typeName,
                            "RefPlane",
                            StringComparison.Ordinal))
                        {
                            allReferencePlaneCount++;
                            if (planeRecords.Count < 3)
                            {
                                object specific = null;
                                MathTransform transform = null;
                                try
                                {
                                    specific = cursor.GetSpecificFeature2();
                                    RefPlane referencePlane =
                                        specific as RefPlane;
                                    Require(
                                        referencePlane != null,
                                        "Default RefPlane specific feature is unavailable");
                                    transform = referencePlane.Transform;
                                    Require(
                                        transform != null,
                                        "Default RefPlane transform is unavailable");
                                    double[] transformData =
                                        ToDoubleArray(transform.ArrayData);
                                    Require(
                                        transformData.Length >= 9,
                                        "Default RefPlane transform has fewer than 9 values");
                                    double[] normal = new double[]
                                    {
                                        transformData[6],
                                        transformData[7],
                                        transformData[8]
                                    };
                                    Require(
                                        Math.Abs(VectorNorm(normal) - 1.0) <= 1.0e-8,
                                        "Default RefPlane normal is not unit length");
                                    normals.Add(normal);
                                    planeRecords.Add(
                                        new Dictionary<string, object>
                                        {
                                            {"feature_order", planeRecords.Count + 1},
                                            {"role_by_default_feature_order",
                                                planeRecords.Count == 0
                                                    ? "FRONT"
                                                    : planeRecords.Count == 1
                                                        ? "TOP"
                                                        : "RIGHT"},
                                            {"localized_name", cursor.Name},
                                            {"type", typeName},
                                            {"normal_from_transform_local_z",
                                                normal},
                                            {"transform_array", transformData}
                                        });
                                }
                                finally
                                {
                                    ReleaseComObject(transform);
                                    ReleaseComObject(specific);
                                }
                            }
                        }
                        else if (String.Equals(
                            typeName,
                            "OriginProfileFeature",
                            StringComparison.Ordinal))
                        {
                            originRecords.Add(
                                new Dictionary<string, object>
                                {
                                    {"localized_name", cursor.Name},
                                    {"type", typeName}
                                });
                        }
                    }
                    finally
                    {
                        ReleaseComObject(cursor);
                        cursor = next;
                    }
                }
            }
            finally
            {
                ReleaseComObject(cursor);
            }

            Require(
                allReferencePlaneCount >= 3 && planeRecords.Count == 3,
                "Blank template must expose at least three RefPlane features; observed " +
                allReferencePlaneCount);
            Require(
                originRecords.Count == 1,
                "Blank template must expose exactly one OriginProfileFeature; observed " +
                originRecords.Count);

            double dotFrontTop = Dot(normals[0], normals[1]);
            double dotFrontRight = Dot(normals[0], normals[2]);
            double dotTopRight = Dot(normals[1], normals[2]);
            const double orthogonalityTolerance = 1.0e-8;
            Require(
                Math.Abs(dotFrontTop) <= orthogonalityTolerance &&
                Math.Abs(dotFrontRight) <= orthogonalityTolerance &&
                Math.Abs(dotTopRight) <= orthogonalityTolerance,
                "Default RefPlane normals are not mutually orthogonal");

            return new Dictionary<string, object>
            {
                {"reference_planes", planeRecords},
                {"selected_default_reference_plane_count", planeRecords.Count},
                {"reference_plane_count_total", allReferencePlaneCount},
                {"origin_features", originRecords},
                {"origin_feature_count", originRecords.Count},
                {"role_assignment_basis",
                    "SOLIDWORKS_DEFAULT_TEMPLATE_FEATURE_ORDER_FRONT_TOP_RIGHT"},
                {"orthogonality_tolerance", orthogonalityTolerance},
                {"normal_dot_products", new Dictionary<string, object>
                    {
                        {"front_top", dotFrontTop},
                        {"front_right", dotFrontRight},
                        {"top_right", dotTopRight}
                    }},
                {"mutually_orthogonal", true}
            };
        }

        private static Dictionary<string, object>
            ReadAndValidateCoordinateTransform(
                Feature coordinateFeature,
                ModelDoc2 model)
        {
            object rawDefinition = null;
            CoordinateSystemFeatureData featureData = null;
            MathTransform transform = null;
            bool selectionAccessAcquired = false;

            try
            {
                rawDefinition = coordinateFeature.GetDefinition();
                featureData = rawDefinition as CoordinateSystemFeatureData;
                Require(
                    featureData != null,
                    "Coordinate-system feature definition is unavailable");
                selectionAccessAcquired =
                    featureData.AccessSelections(model, null);
                Require(
                    selectionAccessAcquired,
                    "CoordinateSystemFeatureData.AccessSelections returned false");
                transform = featureData.Transform;
                Require(
                    transform != null,
                    "CoordinateSystemFeatureData.Transform returned null");
                double[] values = ToDoubleArray(transform.ArrayData);
                Require(
                    values.Length == 16,
                    "Coordinate-system transform must contain 16 values; observed " +
                    values.Length);

                double[] expectedRotation = new double[]
                {
                    1, 0, 0,
                    0, 1, 0,
                    0, 0, 1
                };
                double maximumRotationError = 0;
                for (int index = 0; index < 9; index++)
                {
                    maximumRotationError = Math.Max(
                        maximumRotationError,
                        Math.Abs(values[index] - expectedRotation[index]));
                }
                double maximumTranslationMagnitude = Math.Max(
                    Math.Abs(values[9]),
                    Math.Max(
                        Math.Abs(values[10]),
                        Math.Abs(values[11])));
                double scaleError = Math.Abs(values[12] - 1.0);
                const double rotationTolerance = 1.0e-9;
                const double translationToleranceMeters = 1.0e-12;
                const double scaleTolerance = 1.0e-12;
                Require(
                    maximumRotationError <= rotationTolerance,
                    "Coordinate-system rotation is not identity within tolerance");
                Require(
                    maximumTranslationMagnitude <=
                    translationToleranceMeters,
                    "Coordinate-system translation is not zero within tolerance");
                Require(
                    scaleError <= scaleTolerance,
                    "Coordinate-system transform scale is not one within tolerance");

                return new Dictionary<string, object>
                {
                    {"api",
                        "ICoordinateSystemFeatureData.Transform / IMathTransform.ArrayData"},
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
                    {"rotation_identity_tolerance", rotationTolerance},
                    {"translation_zero_tolerance_m",
                        translationToleranceMeters},
                    {"scale_unity_tolerance", scaleTolerance},
                    {"maximum_rotation_identity_error",
                        maximumRotationError},
                    {"maximum_translation_magnitude_m",
                        maximumTranslationMagnitude},
                    {"scale_unity_error", scaleError},
                    {"rotation_is_identity", true},
                    {"translation_is_zero", true},
                    {"scale_is_unity", true}
                };
            }
            finally
            {
                if (featureData != null && selectionAccessAcquired)
                {
                    try
                    {
                        featureData.ReleaseSelectionAccess();
                    }
                    catch
                    {
                    }
                }
                ReleaseComObject(transform);
                ReleaseComObject(featureData);
                if (!Object.ReferenceEquals(rawDefinition, featureData))
                {
                    ReleaseComObject(rawDefinition);
                }
            }
        }

        private static int CountFeatureByExactName(
            ModelDoc2 model,
            string exactName,
            out string featureType)
        {
            int count = 0;
            string observedType = null;
            Feature cursor = null;
            try
            {
                cursor = (Feature)model.FirstFeature();
                while (cursor != null)
                {
                    Feature next = null;
                    try
                    {
                        next = (Feature)cursor.GetNextFeature();
                        if (String.Equals(
                            cursor.Name,
                            exactName,
                            StringComparison.Ordinal))
                        {
                            count++;
                            observedType = cursor.GetTypeName2();
                        }
                    }
                    finally
                    {
                        ReleaseComObject(cursor);
                        cursor = next;
                    }
                }
            }
            finally
            {
                ReleaseComObject(cursor);
            }
            featureType = observedType;
            return count;
        }

        private static Feature CreateExactlyOneCoordinateSystem(ModelDoc2 model)
        {
            SketchManager sketchManager = null;
            SelectionMgr selectionManager = null;
            FeatureManager featureManager = null;
            SketchPoint origin = null;
            SketchSegment xAxis = null;
            SketchSegment yAxis = null;
            SelectData originSelectionData = null;
            SelectData xSelectionData = null;
            SelectData ySelectionData = null;

            try
            {
                sketchManager = model.SketchManager;
                selectionManager = (SelectionMgr)model.SelectionManager;
                featureManager = model.FeatureManager;
                Require(
                    sketchManager != null &&
                    selectionManager != null &&
                    featureManager != null,
                    "Sketch, selection, or feature manager is unavailable");

                Step(
                    "OPEN_SINGLE_SUPPORT_3D_SKETCH",
                    delegate
                    {
                        sketchManager.Insert3DSketch(true);
                        return true;
                    });

                origin = Step(
                    "CREATE_SUPPORT_ORIGIN_POINT",
                    delegate
                    {
                        SketchPoint point =
                            sketchManager.CreatePoint(0, 0, 0);
                        Require(point != null, "CreatePoint returned null");
                        return point;
                    });
                xAxis = Step(
                    "CREATE_SUPPORT_X_AXIS_LINE",
                    delegate
                    {
                        SketchSegment segment = sketchManager.CreateLine(
                            0, 0, 0, 0.010, 0, 0);
                        Require(
                            segment != null,
                            "X-axis CreateLine returned null");
                        return segment;
                    });
                yAxis = Step(
                    "CREATE_SUPPORT_Y_AXIS_LINE",
                    delegate
                    {
                        SketchSegment segment = sketchManager.CreateLine(
                            0, 0, 0, 0, 0.010, 0);
                        Require(
                            segment != null,
                            "Y-axis CreateLine returned null");
                        return segment;
                    });

                Step(
                    "CLOSE_SINGLE_SUPPORT_3D_SKETCH",
                    delegate
                    {
                        sketchManager.Insert3DSketch(true);
                        return true;
                    });

                model.ClearSelection2(true);
                originSelectionData = selectionManager.CreateSelectData();
                xSelectionData = selectionManager.CreateSelectData();
                ySelectionData = selectionManager.CreateSelectData();
                Require(
                    originSelectionData != null &&
                    xSelectionData != null &&
                    ySelectionData != null,
                    "CreateSelectData returned null");

                ((ISelectData)originSelectionData).Mark = 1;
                ((ISelectData)xSelectionData).Mark = 2;
                ((ISelectData)ySelectionData).Mark = 4;

                Require(
                    origin.Select4(false, originSelectionData),
                    "Origin Select4 with mark 1 returned false");
                Require(
                    xAxis.Select4(true, xSelectionData),
                    "X-axis Select4 with mark 2 returned false");
                Require(
                    yAxis.Select4(true, ySelectionData),
                    "Y-axis Select4 with mark 4 returned false");

                Feature coordinateFeature = Step(
                    "CALL_INSERT_COORDINATE_SYSTEM_EXACTLY_ONCE",
                    delegate
                    {
                        Feature feature =
                            featureManager.InsertCoordinateSystem(
                                false,
                                false,
                                false);
                        Require(
                            feature != null,
                            "InsertCoordinateSystem returned null");
                        return feature;
                    });

                coordinateFeature.Name = CoordinateSystemName;
                Require(
                    String.Equals(
                        coordinateFeature.Name,
                        CoordinateSystemName,
                        StringComparison.Ordinal),
                    "Coordinate-system feature rename did not persist");
                model.ClearSelection2(true);
                return coordinateFeature;
            }
            finally
            {
                ReleaseComObject(ySelectionData);
                ReleaseComObject(xSelectionData);
                ReleaseComObject(originSelectionData);
                ReleaseComObject(yAxis);
                ReleaseComObject(xAxis);
                ReleaseComObject(origin);
                ReleaseComObject(featureManager);
                ReleaseComObject(selectionManager);
                ReleaseComObject(sketchManager);
            }
        }

        [STAThread]
        public static int Run(
            string candidateRootPath,
            string targetPartPath,
            string receiptFilePath,
            string progressFilePath,
            string transformFilePath)
        {
            string candidateRoot = CanonicalPath(candidateRootPath);
            string target = CanonicalPath(targetPartPath);
            string receiptPath = CanonicalPath(receiptFilePath);
            progressPath = CanonicalPath(progressFilePath);
            string transformPath = CanonicalPath(transformFilePath);
            string protectedStageA = Path.Combine(
                candidateRoot,
                "02_MASTER_SKELETON",
                ProtectedStageAFileName);

            SldWorks swApp = null;
            ModelDoc2 model = null;
            Feature coordinateFeature = null;
            Process solidWorksProcess = null;
            bool attachedEmptySessionVerified = false;
            bool exitRequested = false;
            string diagnosticTitle = null;
            string protectedStageAHashBefore = null;
            string protectedStageAHashAfter = null;
            Dictionary<string, object> transformEvidence = null;

            var receipt = new Dictionary<string, object>
            {
                {"schema", "SER_B51R1_SINGLE_CS_DIAGNOSTIC_FIRST_LAUNCH_V1"},
                {"generated_at_utc", DateTime.UtcNow.ToString("o")},
                {"status", "FAIL_NOT_STARTED"},
                {"candidate_root", candidateRoot},
                {"target_part", target},
                {"receipt_path", receiptPath},
                {"progress_log", progressPath},
                {"transform_evidence_path", transformPath},
                {"protected_stage_a_path", protectedStageA},
                {"coordinate_system_name", CoordinateSystemName},
                {"runtime_contract", new Dictionary<string, object>
                    {
                        {"solidworks_launch_permitted_by_tool", false},
                        {"attachment_method", "Marshal.GetActiveObject"},
                        {"required_process_count", 1},
                        {"required_process_responding", true},
                        {"required_visible_main_window", true},
                        {"required_empty_document_session", true},
                        {"new_blank_part_only", true},
                        {"open_existing_document_permitted", false},
                        {"copy_existing_document_permitted", false},
                        {"stage_a_open_copy_or_write_permitted", false},
                        {"stage_a_read_only_hash_permitted", true},
                        {"insert_coordinate_system_call_count", 1},
                        {"normal_exit_required", true},
                        {"solidworks_process_termination_permitted", false}
                    }},
                {"claim_limit",
                    "FIRST_VISIBLE_LAUNCH_CREATE_SAVE_CLOSE_AND_NORMAL_EXIT_ONLY; COLD_PROCESS_REOPEN_NOT_RUN; NO_MASTER_SKELETON_CARRIER_H10_T005_CONTROL_RELEASE_MANUFACTURING_OR_FLIGHT_CREDIT"}
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
                        " | START | SER_B51R1_SINGLE_CS_DIAGNOSTIC_FIRST_LAUNCH_V1");
                }

                Step(
                    "PREFLIGHT_EXACT_PATHS_AND_NO_OVERWRITE",
                    delegate
                    {
                        Require(
                            String.Equals(
                                Path.GetFileName(candidateRoot),
                                ExpectedCandidateDirectoryName,
                                StringComparison.OrdinalIgnoreCase),
                            "Candidate root directory name is not the isolated B5.1R1 candidate");
                        string diagnosticDirectory =
                            Path.Combine(
                                candidateRoot,
                                "00_BASELINE",
                                ExpectedDiagnosticDirectoryName);
                        string verificationDirectory =
                            Path.Combine(candidateRoot, "07_VERIFICATION");
                        string reviewDirectory =
                            Path.Combine(candidateRoot, "08_REVIEWS");
                        Require(
                            String.Equals(
                                Path.GetDirectoryName(target),
                                diagnosticDirectory,
                                StringComparison.OrdinalIgnoreCase) &&
                            String.Equals(
                                Path.GetFileName(target),
                                ExpectedTargetFileName,
                                StringComparison.OrdinalIgnoreCase),
                            "Target path is outside the fixed DIAGNOSTIC_ONLY target");
                        Require(
                            String.Equals(
                                Path.GetDirectoryName(receiptPath),
                                verificationDirectory,
                                StringComparison.OrdinalIgnoreCase) &&
                            String.Equals(
                                Path.GetFileName(receiptPath),
                                ExpectedReceiptFileName,
                                StringComparison.OrdinalIgnoreCase),
                            "Receipt path is outside the fixed verification location");
                        Require(
                            String.Equals(
                                Path.GetDirectoryName(transformPath),
                                verificationDirectory,
                                StringComparison.OrdinalIgnoreCase) &&
                            String.Equals(
                                Path.GetFileName(transformPath),
                                ExpectedTransformFileName,
                                StringComparison.OrdinalIgnoreCase),
                            "Transform evidence path is outside the fixed verification location");
                        Require(
                            String.Equals(
                                Path.GetDirectoryName(progressPath),
                                reviewDirectory,
                                StringComparison.OrdinalIgnoreCase) &&
                            String.Equals(
                                Path.GetFileName(progressPath),
                                ExpectedProgressFileName,
                                StringComparison.OrdinalIgnoreCase),
                            "Progress path is outside the fixed review location");
                        Require(
                            Directory.Exists(diagnosticDirectory) &&
                            Directory.Exists(verificationDirectory) &&
                            Directory.Exists(reviewDirectory),
                            "Required candidate directories are missing");
                        Require(
                            !File.Exists(target),
                            "Diagnostic target already exists; overwrite refused");
                        Require(
                            !File.Exists(receiptPath),
                            "First-launch receipt already exists; overwrite refused");
                        Require(
                            !File.Exists(transformPath),
                            "First-launch transform evidence already exists; overwrite refused");
                        Require(
                            File.Exists(protectedStageA) &&
                            String.Equals(
                                Path.GetFileName(protectedStageA),
                                ProtectedStageAFileName,
                                StringComparison.OrdinalIgnoreCase),
                            "Protected Stage A file is missing");
                        return true;
                    });

                protectedStageAHashBefore = Step(
                    "HASH_PROTECTED_STAGE_A_BEFORE_READ_ONLY",
                    delegate
                    {
                        return Sha256(protectedStageA);
                    });
                receipt["protected_stage_a_sha256_before"] =
                    protectedStageAHashBefore;

                solidWorksProcess = Step(
                    "VERIFY_EXACTLY_ONE_EXTERNALLY_STARTED_SOLIDWORKS_PROCESS",
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
                    "VERIFY_PROCESS_RESPONDING_AND_VISIBLE_WINDOW",
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
                            "SLDWORKS process has no visible main window");
                        receipt["solidworks_main_window_title"] =
                            solidWorksProcess.MainWindowTitle;
                        return true;
                    });

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
                    "VERIFY_ATTACHED_IDENTITY_VISIBLE_EMPTY_2024_SP5",
                    delegate
                    {
                        int attachedProcessId = swApp.GetProcessID();
                        string revision = swApp.RevisionNumber();
                        Require(
                            attachedProcessId == solidWorksProcess.Id,
                            "ROT object PID does not match the sole SLDWORKS process");
                        Require(swApp.Visible, "Attached SolidWorks is not visible");
                        Require(
                            swApp.StartupProcessCompleted,
                            "SolidWorks startup is not complete");
                        Require(
                            revision != null &&
                            revision.StartsWith(
                                ExpectedSolidWorksRevisionPrefix,
                                StringComparison.Ordinal),
                            "Expected SolidWorks 2024 SP5 revision prefix " +
                            ExpectedSolidWorksRevisionPrefix +
                            " but observed " + revision);
                        Require(
                            swApp.GetDocumentCount() == 0,
                            "Attached SolidWorks session must contain zero documents");
                        receipt["solidworks_revision"] = revision;
                        receipt["attached_process_id"] = attachedProcessId;
                        attachedEmptySessionVerified = true;
                        return true;
                    });

                string templatePath = Step(
                    "READ_CONFIGURED_DEFAULT_PART_TEMPLATE",
                    delegate
                    {
                        string configured =
                            swApp.GetUserPreferenceStringValue(
                                DefaultPartTemplatePreference);
                        Require(
                            !String.IsNullOrWhiteSpace(configured),
                            "SolidWorks default part template preference is empty");
                        string canonical = CanonicalPath(configured);
                        Require(
                            File.Exists(canonical),
                            "Configured default part template does not exist");
                        Require(
                            String.Equals(
                                Path.GetExtension(canonical),
                                ".PRTDOT",
                                StringComparison.OrdinalIgnoreCase),
                            "Configured default part template is not a PRTDOT");
                        return canonical;
                    });
                receipt["default_part_template"] = templatePath;
                receipt["default_part_template_sha256"] = Sha256(templatePath);

                model = Step(
                    "CREATE_NEW_BLANK_PART_FROM_CONFIGURED_TEMPLATE",
                    delegate
                    {
                        ModelDoc2 created = (ModelDoc2)swApp.NewDocument(
                            templatePath,
                            0,
                            0,
                            0);
                        Require(created != null, "NewDocument returned null");
                        Require(
                            created.GetType() == PartDocumentType,
                            "NewDocument did not create a part document");
                        Require(
                            String.IsNullOrEmpty(created.GetPathName()),
                            "New blank part unexpectedly has an existing file path");
                        Require(
                            swApp.GetDocumentCount() == 1,
                            "Expected exactly one newly created blank document");
                        return created;
                    });
                diagnosticTitle = model.GetTitle();
                receipt["new_blank_part_title"] = diagnosticTitle;
                receipt["feature_count_before_coordinate"] =
                    model.GetFeatureCount();

                receipt["blank_reference_geometry"] = Step(
                    "CONFIRM_DEFAULT_FRONT_TOP_RIGHT_PLANES_AND_ORIGIN",
                    delegate
                    {
                        return InspectBlankReferenceGeometry(model);
                    });

                coordinateFeature = CreateExactlyOneCoordinateSystem(model);
                receipt["coordinate_feature_name"] = coordinateFeature.Name;
                receipt["coordinate_feature_type"] =
                    coordinateFeature.GetTypeName2();
                transformEvidence = Step(
                    "READ_AND_VALIDATE_COORDINATE_SYSTEM_TRANSFORM",
                    delegate
                    {
                        return ReadAndValidateCoordinateTransform(
                            coordinateFeature,
                            model);
                    });
                ReleaseComObject(coordinateFeature);
                coordinateFeature = null;

                Step(
                    "REBUILD_NEW_BLANK_PART",
                    delegate
                    {
                        Require(
                            model.ForceRebuild3(false),
                            "ForceRebuild3 returned false");
                        return true;
                    });

                string coordinateType = null;
                int coordinateCount = Step(
                    "VERIFY_EXACTLY_ONE_NAMED_COORDINATE_SYSTEM",
                    delegate
                    {
                        int count = CountFeatureByExactName(
                            model,
                            CoordinateSystemName,
                            out coordinateType);
                        Require(
                            count == 1,
                            "Expected exactly one feature named " +
                            CoordinateSystemName +
                            "; observed " + count);
                        return count;
                    });
                receipt["coordinate_feature_count_by_exact_name"] =
                    coordinateCount;
                receipt["coordinate_feature_type_readback"] =
                    coordinateType;
                receipt["feature_count_after_coordinate"] =
                    model.GetFeatureCount();

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
                            int count =
                                extension.ListExternalFileReferencesCount();
                            Require(
                                count == 0,
                                "New diagnostic part has external file references: " +
                                count);
                            return count;
                        }
                        finally
                        {
                            ReleaseComObject(extension);
                        }
                    });
                receipt["external_file_reference_count"] =
                    externalReferenceCount;

                int saveErrors = 0;
                int saveWarnings = 0;
                Step(
                    "SAVE_AS_FIXED_DIAGNOSTIC_TARGET",
                    delegate
                    {
                        ModelDocExtension extension = null;
                        try
                        {
                            extension = model.Extension;
                            Require(
                                extension != null,
                                "ModelDocExtension is unavailable");
                            bool saved = extension.SaveAs3(
                                target,
                                SaveCurrentVersion,
                                SaveSilent,
                                null,
                                null,
                                ref saveErrors,
                                ref saveWarnings);
                        Require(
                            saved && saveErrors == 0 && saveWarnings == 0,
                            "SaveAs3 failed saved=" + saved +
                            " errors=" + saveErrors +
                            " warnings=" + saveWarnings);
                            Require(
                                String.Equals(
                                    CanonicalPath(model.GetPathName()),
                                    target,
                                    StringComparison.OrdinalIgnoreCase),
                                "Saved document path is not the fixed diagnostic target");
                            return true;
                        }
                        finally
                        {
                            ReleaseComObject(extension);
                        }
                    });
                receipt["save_errors"] = saveErrors;
                receipt["save_warnings"] = saveWarnings;

                Step(
                    "CLOSE_DIAGNOSTIC_DOCUMENT",
                    delegate
                    {
                        swApp.CloseDoc(diagnosticTitle);
                        return true;
                    });
                ReleaseComObject(model);
                model = null;

                Step(
                    "VERIFY_SESSION_EMPTY_AFTER_CLOSE",
                    delegate
                    {
                        Require(
                            swApp.GetDocumentCount() == 0,
                            "SolidWorks session is not empty after closing the diagnostic part");
                        return true;
                    });

                long targetBytesAfterClose =
                    new FileInfo(target).Length;
                string targetHashAfterClose = Sha256(target);
                receipt["target_bytes_after_close"] =
                    targetBytesAfterClose;
                receipt["target_sha256_after_close"] =
                    targetHashAfterClose;

                protectedStageAHashAfter = Step(
                    "HASH_PROTECTED_STAGE_A_AFTER_CLOSE_READ_ONLY",
                    delegate
                    {
                        return Sha256(protectedStageA);
                    });
                Require(
                    String.Equals(
                        protectedStageAHashBefore,
                        protectedStageAHashAfter,
                        StringComparison.Ordinal),
                    "Protected Stage A SHA256 changed during diagnostic");
                receipt["protected_stage_a_sha256_after"] =
                    protectedStageAHashAfter;
                receipt["protected_stage_a_unchanged"] = true;

                transformEvidence["schema"] =
                    "SER_B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM_FIRST_LAUNCH_V1";
                transformEvidence["generated_at_utc"] =
                    DateTime.UtcNow.ToString("o");
                transformEvidence["status"] =
                    "PASS_IDENTITY_TRANSFORM_FIRST_LAUNCH_COLD_REOPEN_PENDING";
                transformEvidence["target_part"] = target;
                transformEvidence["target_part_bytes"] =
                    targetBytesAfterClose;
                transformEvidence["target_part_sha256"] =
                    targetHashAfterClose;
                transformEvidence["coordinate_system_name"] =
                    CoordinateSystemName;
                transformEvidence["protected_stage_a"] =
                    protectedStageA;
                transformEvidence["protected_stage_a_sha256_before"] =
                    protectedStageAHashBefore;
                transformEvidence["protected_stage_a_sha256_after"] =
                    protectedStageAHashAfter;
                transformEvidence["protected_stage_a_unchanged"] = true;
                transformEvidence["cold_process_reopen_status"] =
                    "NOT_RUN_REQUIRES_SEPARATE_VISIBLE_LAUNCH_AUTHORIZATION";
                transformEvidence["claim_limit"] =
                    "FIRST_LAUNCH_TRANSFORM_EVIDENCE_ONLY; NO_COLD_REOPEN_MASTER_SKELETON_CARRIER_H10_T005_CONTROL_RELEASE_MANUFACTURING_OR_FLIGHT_CREDIT";

                Step(
                    "WRITE_FIRST_LAUNCH_TRANSFORM_EVIDENCE",
                    delegate
                    {
                        WriteReceiptNew(
                            transformPath,
                            transformEvidence);
                        return true;
                    });
                receipt["transform_evidence_sha256"] =
                    Sha256(transformPath);
                receipt["document_count_before_exit"] =
                    swApp.GetDocumentCount();
                receipt["exit_requested_at_utc"] =
                    DateTime.UtcNow.ToString("o");

                Step(
                    "REQUEST_NORMAL_SOLIDWORKS_EXIT",
                    delegate
                    {
                        Require(
                            swApp.GetDocumentCount() == 0 &&
                            swApp.ActiveDoc == null,
                            "SolidWorks session is no longer empty immediately before ExitApp");
                        exitRequested = true;
                        swApp.ExitApp();
                        return true;
                    });
                ReleaseComObject(swApp);
                swApp = null;

                bool processExited = Step(
                    "VERIFY_SOLIDWORKS_PROCESS_EXITED_NORMALLY",
                    delegate
                    {
                        bool exited =
                            solidWorksProcess.WaitForExit(
                                ProcessExitWaitMilliseconds);
                        Require(
                            exited,
                            "SolidWorks did not exit within " +
                            ProcessExitWaitMilliseconds + " ms");
                        return true;
                    });
                receipt["solidworks_process_exited"] = processExited;
                receipt["solidworks_process_has_exited"] =
                    solidWorksProcess.HasExited;
                receipt["solidworks_process_exit_time_utc"] =
                    solidWorksProcess.ExitTime.ToUniversalTime().ToString("o");
                int solidWorksExitCode = solidWorksProcess.ExitCode;
                receipt["solidworks_process_exit_code"] =
                    solidWorksExitCode;
                Require(
                    solidWorksExitCode == 0,
                    "SolidWorks exited with non-zero process exit code " +
                    solidWorksExitCode);
                receipt["normal_exit_observed_at_utc"] =
                    DateTime.UtcNow.ToString("o");
                receipt["cold_process_reopen_status"] =
                    "NOT_RUN_REQUIRES_SEPARATE_VISIBLE_LAUNCH_AUTHORIZATION";
                receipt["status"] =
                    "PASS_FIRST_LAUNCH_CREATED_SAVED_CLOSED_AND_NORMAL_EXIT_COLD_REOPEN_PENDING";
                receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");

                Step(
                    "WRITE_FIRST_LAUNCH_PASS_RECEIPT",
                    delegate
                    {
                        WriteReceiptNew(receiptPath, receipt);
                        return true;
                    });
                Trace(
                    "PASS | PASS_FIRST_LAUNCH_CREATED_SAVED_CLOSED_AND_NORMAL_EXIT_COLD_REOPEN_PENDING");
                return 0;
            }
            catch (Exception ex)
            {
                SafeTrace(
                    "FAIL_CLOSED | " + ex.GetType().FullName +
                    " | " + OneLine(ex.Message));
                receipt["status"] = "FAIL_CLOSED_FIRST_LAUNCH";
                receipt["failed_at_utc"] = DateTime.UtcNow.ToString("o");
                receipt["error_type"] = ex.GetType().FullName;
                receipt["error_message"] = ex.Message;
                receipt["error_hresult"] =
                    "0x" + ex.HResult.ToString("X8");
                receipt["normal_exit_requested_before_failure"] =
                    exitRequested;

                try
                {
                    if (swApp != null &&
                        model != null &&
                        attachedEmptySessionVerified)
                    {
                        string path = model.GetPathName();
                        if (String.IsNullOrEmpty(path) ||
                            String.Equals(
                                CanonicalPath(path),
                                target,
                                StringComparison.OrdinalIgnoreCase))
                        {
                            swApp.CloseDoc(model.GetTitle());
                            SafeTrace(
                                "FAIL_CLOSED_CLEANUP | CLOSED_DIAGNOSTIC_DOCUMENT_ONLY");
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

                ReleaseComObject(coordinateFeature);
                ReleaseComObject(model);
                model = null;

                try
                {
                    if (swApp != null &&
                        attachedEmptySessionVerified &&
                        swApp.GetDocumentCount() == 0)
                    {
                        swApp.ExitApp();
                        exitRequested = true;
                        receipt["fail_closed_normal_exit_requested"] = true;
                        SafeTrace(
                            "FAIL_CLOSED_CLEANUP | REQUESTED_NORMAL_SOLIDWORKS_EXIT");
                    }
                }
                catch (Exception exitException)
                {
                    receipt["cleanup_exit_error"] =
                        OneLine(exitException.Message);
                    SafeTrace(
                        "FAIL_CLOSED_EXIT_ERROR | " +
                        exitException.GetType().FullName +
                        " | " + OneLine(exitException.Message));
                }

                ReleaseComObject(swApp);
                swApp = null;

                try
                {
                    if (File.Exists(protectedStageA))
                    {
                        protectedStageAHashAfter =
                            Sha256(protectedStageA);
                        receipt["protected_stage_a_sha256_after_if_available"] =
                            protectedStageAHashAfter;
                        receipt["protected_stage_a_unchanged_if_available"] =
                            protectedStageAHashBefore != null &&
                            String.Equals(
                                protectedStageAHashBefore,
                                protectedStageAHashAfter,
                                StringComparison.Ordinal);
                    }
                    if (File.Exists(target))
                    {
                        receipt["target_exists_after_failure"] = true;
                        receipt["target_bytes_after_failure"] =
                            new FileInfo(target).Length;
                        receipt["target_sha256_after_failure"] =
                            Sha256(target);
                    }
                    else
                    {
                        receipt["target_exists_after_failure"] = false;
                    }
                }
                catch (Exception targetEvidenceException)
                {
                    receipt["target_evidence_error"] =
                        OneLine(targetEvidenceException.Message);
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
                return 1;
            }
            finally
            {
                ReleaseComObject(coordinateFeature);
                ReleaseComObject(model);
                ReleaseComObject(swApp);
                if (solidWorksProcess != null)
                {
                    solidWorksProcess.Dispose();
                }
            }
        }
    }
}
