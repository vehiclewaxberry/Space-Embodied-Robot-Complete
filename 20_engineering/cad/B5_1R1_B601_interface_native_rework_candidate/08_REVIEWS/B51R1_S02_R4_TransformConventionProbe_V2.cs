using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static class B51R1S02R4TransformConventionProbeV2
{
    private const int DocumentTypePart = 1;
    private const int OpenSilent = 1;
    private const int OpenReadOnly = 2;
    private const int ExitTimeoutMilliseconds = 30000;
    private const double TranslationToleranceMetres = 1.0e-9;

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

    private static double[] ToDoubleArray(object raw)
    {
        Array array = raw as Array;
        Require(array != null, "Expected an array");
        double[] values = new double[array.Length];
        int index = 0;
        foreach (object value in array) values[index++] = Convert.ToDouble(value);
        return values;
    }

    private static double MaximumError(double[] observed, double[] expected)
    {
        Require(observed.Length == expected.Length, "Array length mismatch");
        double result = 0.0;
        for (int index = 0; index < observed.Length; index++)
            result = Math.Max(result, Math.Abs(observed[index] - expected[index]));
        return result;
    }

    private static string ActiveConfigurationName(ModelDoc2 model)
    {
        ConfigurationManager manager = null;
        Configuration configuration = null;
        try
        {
            manager = model.ConfigurationManager;
            Require(manager != null, "ConfigurationManager unavailable");
            configuration = manager.ActiveConfiguration;
            Require(configuration != null, "ActiveConfiguration unavailable");
            return configuration.Name;
        }
        finally
        {
            ReleaseCom(configuration);
            ReleaseCom(manager);
        }
    }

    private static Feature FindUniqueFeature(ModelDoc2 model, string name, string type)
    {
        Feature cursor = null;
        Feature match = null;
        int count = 0;
        try
        {
            cursor = (Feature)model.FirstFeature();
            while (cursor != null)
            {
                Feature next = null;
                try
                {
                    next = (Feature)cursor.GetNextFeature();
                    if (String.Equals(cursor.Name, name, StringComparison.Ordinal) &&
                        String.Equals(cursor.GetTypeName2(), type, StringComparison.Ordinal))
                    {
                        count++;
                        if (match == null)
                        {
                            match = cursor;
                            cursor = null;
                        }
                    }
                }
                finally
                {
                    ReleaseCom(cursor);
                    cursor = next;
                }
            }
            Require(count == 1 && match != null,
                "Expected one " + type + " named " + name + "; observed " + count);
            return match;
        }
        catch
        {
            ReleaseCom(match);
            throw;
        }
        finally
        {
            ReleaseCom(cursor);
        }
    }

    private static double[] TransformPoint(MathUtility utility, double[] point, MathTransform transform)
    {
        MathPoint input = null;
        MathPoint output = null;
        try
        {
            input = utility.CreatePoint(point) as MathPoint;
            Require(input != null, "Could not create IMathPoint");
            output = input.MultiplyTransform(transform) as MathPoint;
            Require(output != null, "IMathPoint.MultiplyTransform failed");
            return ToDoubleArray(output.ArrayData);
        }
        finally
        {
            ReleaseCom(output);
            ReleaseCom(input);
        }
    }

    private static Dictionary<string, object> DescribeEntity(object entity)
    {
        var result = new Dictionary<string, object>();
        if (entity == null)
        {
            result["available"] = false;
            return result;
        }
        result["available"] = true;
        result["runtime_type"] = entity.GetType().FullName;
        result["is_com_object"] = Marshal.IsComObject(entity);
        try
        {
            SketchPoint point = entity as SketchPoint;
            if (point != null)
            {
                result["recognized_type"] = "ISketchPoint";
                result["coordinates_m"] = new double[] { point.X, point.Y, point.Z };
                return result;
            }
            Vertex vertex = entity as Vertex;
            if (vertex != null)
            {
                result["recognized_type"] = "IVertex";
                result["coordinates_m"] = ToDoubleArray(vertex.GetPoint());
                return result;
            }
            RefPoint refPoint = entity as RefPoint;
            if (refPoint != null)
            {
                result["recognized_type"] = "IRefPoint";
                result["coordinates_m"] = ToDoubleArray(refPoint.GetRefPoint());
                return result;
            }
            Feature feature = entity as Feature;
            if (feature != null)
            {
                result["recognized_type"] = "IFeature";
                result["feature_name"] = feature.Name;
                result["feature_type"] = feature.GetTypeName2();
                return result;
            }
            Array array = entity as Array;
            if (array != null)
            {
                result["recognized_type"] = "ARRAY";
                result["element_count"] = array.Length;
                var elements = new List<Dictionary<string, object>>();
                foreach (object value in array)
                {
                    try { elements.Add(DescribeEntity(value)); }
                    finally { ReleaseCom(value); }
                }
                result["elements"] = elements;
                return result;
            }
            result["recognized_type"] = "UNRECOGNIZED_READ_ONLY_ENTITY";
        }
        catch (Exception ex)
        {
            result["description_error"] = ex.GetType().FullName + ": " + ex.Message;
        }
        return result;
    }

    private static Dictionary<string, object> ProbeCoordinateSystem(
        ModelDoc2 model,
        MathUtility utility,
        string name,
        double[] expectedOrigin)
    {
        Feature feature = null;
        CoordinateSystemFeatureData data = null;
        ModelDocExtension extension = null;
        MathTransform featureTransform = null;
        MathTransform namedTransform = null;
        MathTransform inverse = null;
        object originEntity = null;
        bool selectionsAccessed = false;
        try
        {
            feature = FindUniqueFeature(model, name, "CoordSys");
            data = feature.GetDefinition() as CoordinateSystemFeatureData;
            Require(data != null, "CoordinateSystemFeatureData unavailable for " + name);
            selectionsAccessed = data.AccessSelections(model, null);
            Require(selectionsAccessed, "AccessSelections failed for " + name);
            featureTransform = data.Transform;
            Require(featureTransform != null, "Feature-data transform unavailable for " + name);
            extension = model.Extension;
            Require(extension != null, "ModelDocExtension unavailable for " + name);
            namedTransform = extension.GetCoordinateSystemTransformByName(name);
            Require(namedTransform != null, "Named coordinate transform unavailable for " + name);
            inverse = namedTransform.IInverse();
            Require(inverse != null, "Coordinate transform inverse unavailable for " + name);

            double[] featureRaw = ToDoubleArray(featureTransform.ArrayData);
            double[] namedRaw = ToDoubleArray(namedTransform.ArrayData);
            double[] inverseRaw = ToDoubleArray(inverse.ArrayData);
            Require(featureRaw.Length == 16 && namedRaw.Length == 16 && inverseRaw.Length == 16,
                "Expected 16-element coordinate transforms for " + name);

            double[] zero = { 0.0, 0.0, 0.0 };
            double[] zeroThroughRaw = TransformPoint(utility, zero, namedTransform);
            double[] zeroThroughInverse = TransformPoint(utility, zero, inverse);
            originEntity = data.OriginEntity;

            return new Dictionary<string, object>
            {
                {"name", name},
                {"expected_origin_m", expectedOrigin},
                {"feature_data_raw_transform", featureRaw},
                {"named_api_raw_transform", namedRaw},
                {"dual_api_raw_max_abs_error", MaximumError(featureRaw, namedRaw)},
                {"inverse_transform", inverseRaw},
                {"model_origin_through_raw_transform", zeroThroughRaw},
                {"local_origin_through_inverse_transform", zeroThroughInverse},
                {"raw_origin_candidate_max_abs_error_m", MaximumError(zeroThroughRaw, expectedOrigin)},
                {"inverse_origin_candidate_max_abs_error_m", MaximumError(zeroThroughInverse, expectedOrigin)},
                {"official_example_negated_raw_translation_m",
                    new double[] {-namedRaw[9], -namedRaw[10], -namedRaw[11]}},
                {"origin_entity_type_code", data.GetOriginEntityType()},
                {"origin_entity", DescribeEntity(originEntity)},
                {"x_flipped", data.XFlipped},
                {"y_flipped", data.YFlipped},
                {"z_flipped", data.ZFlipped}
            };
        }
        finally
        {
            ReleaseCom(originEntity);
            if (data != null && selectionsAccessed)
            {
                try { data.ReleaseSelectionAccess(); }
                catch { }
            }
            ReleaseCom(inverse);
            ReleaseCom(namedTransform);
            ReleaseCom(featureTransform);
            ReleaseCom(extension);
            ReleaseCom(data);
            ReleaseCom(feature);
        }
    }

    private static object TryNumericArray(Func<object> getter, out string error)
    {
        error = null;
        try { return ToDoubleArray(getter()); }
        catch (Exception ex)
        {
            error = ex.GetType().FullName + ": " + ex.Message;
            return null;
        }
    }

    private static Dictionary<string, object> ProbeReferencePlane(
        ModelDoc2 model,
        MathUtility utility,
        string name,
        double[] expectedOrigin)
    {
        Feature feature = null;
        RefPlane plane = null;
        MathTransform rawTransform = null;
        MathTransform inverse = null;
        try
        {
            feature = FindUniqueFeature(model, name, "RefPlane");
            plane = feature.GetSpecificFeature2() as RefPlane;
            Require(plane != null, "IRefPlane unavailable for " + name);
            rawTransform = plane.Transform;
            Require(rawTransform != null, "IRefPlane.Transform unavailable for " + name);
            inverse = rawTransform.IInverse();
            Require(inverse != null, "IRefPlane.Transform inverse unavailable for " + name);
            double[] raw = ToDoubleArray(rawTransform.ArrayData);
            double[] inverseRaw = ToDoubleArray(inverse.ArrayData);
            double[] zero = { 0.0, 0.0, 0.0 };
            double[] zeroThroughRaw = TransformPoint(utility, zero, rawTransform);
            double[] zeroThroughInverse = TransformPoint(utility, zero, inverse);

            string cornerError;
            object corners = TryNumericArray(() => plane.CornerPoints, out cornerError);
            string boxError;
            object box = TryNumericArray(() => plane.BoundingBox, out boxError);
            string legacyError;
            object legacy = TryNumericArray(() => plane.GetRefPlaneParams(), out legacyError);

            var result = new Dictionary<string, object>
            {
                {"name", name},
                {"expected_origin_m", expectedOrigin},
                {"raw_transform", raw},
                {"inverse_transform", inverseRaw},
                {"zero_through_raw_transform", zeroThroughRaw},
                {"zero_through_inverse_transform", zeroThroughInverse},
                {"raw_origin_candidate_max_abs_error_m", MaximumError(zeroThroughRaw, expectedOrigin)},
                {"inverse_origin_candidate_max_abs_error_m", MaximumError(zeroThroughInverse, expectedOrigin)},
                {"corner_points_if_numeric", corners},
                {"bounding_box_if_numeric", box},
                {"legacy_ref_plane_params_if_numeric", legacy}
            };
            if (cornerError != null) result["corner_points_read_error"] = cornerError;
            if (boxError != null) result["bounding_box_read_error"] = boxError;
            if (legacyError != null) result["legacy_params_read_error"] = legacyError;
            return result;
        }
        finally
        {
            ReleaseCom(inverse);
            ReleaseCom(rawTransform);
            ReleaseCom(plane);
            ReleaseCom(feature);
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
        string protectedStageAPath,
        string receiptPath,
        string progressPath,
        int expectedProcessId,
        string expectedTargetSha256,
        string expectedStageASha256)
    {
        var receipt = new Dictionary<string, object>
        {
            {"schema", "B51R1_S02_R4_TRANSFORM_CONVENTION_PROBE_V2"},
            {"session_id", "S02_R4"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"status", "S02_R4_FAIL_CLOSED_NOT_STARTED"},
            {"target_path", targetPath},
            {"protected_stage_a_path", protectedStageAPath},
            {"expected_process_id", expectedProcessId},
            {"open_mode", "SILENT_READ_ONLY"},
            {"save_api_call_count", 0},
            {"configuration_activation_call_count", 0},
            {"rebuild_call_count", 0},
            {"official_api_example_origin_rule",
                "ORIGIN_EQUALS_NEGATED_ARRAYDATA_9_10_11_IN_GET_COORDINATE_SYSTEM_TRANSFORM_EXAMPLE_VBA"}
        };
        SldWorks app = null;
        ModelDoc2 model = null;
        MathUtility utility = null;
        Process process = null;
        string stage = "PRECONDITIONS";
        try
        {
            Require(!File.Exists(receiptPath), "Receipt already exists");
            Require(!File.Exists(progressPath), "Progress log already exists");
            Require(File.Exists(targetPath), "Probe target is absent");
            Require(File.Exists(protectedStageAPath), "Protected Stage A is absent");
            Require(String.Equals(Sha256(targetPath), expectedTargetSha256,
                StringComparison.OrdinalIgnoreCase), "Probe target hash mismatch");
            Require(String.Equals(Sha256(protectedStageAPath), expectedStageASha256,
                StringComparison.OrdinalIgnoreCase), "Protected Stage A hash mismatch");
            receipt["target_sha256_before"] = Sha256(targetPath);
            receipt["protected_stage_a_sha256_before"] = Sha256(protectedStageAPath);
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
                "Read-only OpenDoc6 failed; errors=" + errors + "; warnings=" + warnings);
            Require(model.IsOpenedReadOnly(), "Probe target is not read-only");
            receipt["open_errors"] = errors;
            receipt["open_warnings"] = warnings;
            receipt["cold_open_configuration"] = ActiveConfigurationName(model);

            utility = app.GetMathUtility() as MathUtility;
            Require(utility != null, "IMathUtility unavailable");

            stage = "PROBE_COORDINATE_SYSTEMS";
            Progress(progressPath, stage);
            var coordinates = new List<Dictionary<string, object>>
            {
                ProbeCoordinateSystem(model, utility, "CS_S", new double[] {0.0, 0.0, 0.0}),
                ProbeCoordinateSystem(model, utility, "CS_M_DYNAMICS_X185_25", new double[] {0.18525, 0.0, 0.0}),
                ProbeCoordinateSystem(model, utility, "CS_M_DISPLAY_X198", new double[] {0.198, 0.0, 0.0}),
                ProbeCoordinateSystem(model, utility, "CS_A0_CLOCKED_25_DEG", new double[] {0.18525, 0.0, 0.0})
            };
            receipt["coordinate_systems"] = coordinates;

            stage = "PROBE_REFERENCE_PLANES";
            Progress(progressPath, stage);
            var planes = new List<Dictionary<string, object>>
            {
                ProbeReferencePlane(model, utility, "PLN_TASK_FACE_X183", new double[] {0.183, 0.0, 0.0}),
                ProbeReferencePlane(model, utility, "PLN_M_DYNAMICS_X185_25", new double[] {0.18525, 0.0, 0.0}),
                ProbeReferencePlane(model, utility, "PLN_M_DISPLAY_X198", new double[] {0.198, 0.0, 0.0})
            };
            receipt["reference_planes"] = planes;

            int translatedCoordinateRawMatches = 0;
            int translatedCoordinateInverseMatches = 0;
            for (int index = 1; index < coordinates.Count; index++)
            {
                if (Convert.ToDouble(coordinates[index]["raw_origin_candidate_max_abs_error_m"],
                    CultureInfo.InvariantCulture) <= TranslationToleranceMetres)
                    translatedCoordinateRawMatches++;
                if (Convert.ToDouble(coordinates[index]["inverse_origin_candidate_max_abs_error_m"],
                    CultureInfo.InvariantCulture) <= TranslationToleranceMetres)
                    translatedCoordinateInverseMatches++;
            }
            int planeRawMatches = 0;
            int planeInverseMatches = 0;
            foreach (Dictionary<string, object> plane in planes)
            {
                if (Convert.ToDouble(plane["raw_origin_candidate_max_abs_error_m"],
                    CultureInfo.InvariantCulture) <= TranslationToleranceMetres)
                    planeRawMatches++;
                if (Convert.ToDouble(plane["inverse_origin_candidate_max_abs_error_m"],
                    CultureInfo.InvariantCulture) <= TranslationToleranceMetres)
                    planeInverseMatches++;
            }
            receipt["direction_summary"] = new Dictionary<string, object>
            {
                {"translated_coordinate_system_count", 3},
                {"raw_origin_candidate_match_count", translatedCoordinateRawMatches},
                {"inverse_origin_candidate_match_count", translatedCoordinateInverseMatches},
                {"reference_plane_count", planes.Count},
                {"plane_raw_origin_candidate_match_count", planeRawMatches},
                {"plane_inverse_origin_candidate_match_count", planeInverseMatches},
                {"translation_tolerance_m", TranslationToleranceMetres},
                {"classification_deferred_to_evidence_addendum", true}
            };

            stage = "CLOSE_WITHOUT_SAVE";
            Progress(progressPath, stage);
            app.CloseDoc(model.GetTitle());
            ReleaseCom(model);
            model = null;
            Require(app.GetDocumentCount() == 0 && app.ActiveDoc == null,
                "SolidWorks is not document-empty after CloseDoc");
            Require(String.Equals(Sha256(targetPath), expectedTargetSha256,
                StringComparison.OrdinalIgnoreCase), "Probe target changed during inspection");
            Require(String.Equals(Sha256(protectedStageAPath), expectedStageASha256,
                StringComparison.OrdinalIgnoreCase), "Protected Stage A changed during inspection");

            stage = "NORMAL_EXIT";
            Progress(progressPath, stage);
            ReleaseCom(utility);
            utility = null;
            app.ExitApp();
            ReleaseCom(app);
            app = null;
            GC.Collect();
            GC.WaitForPendingFinalizers();
            Require(process.WaitForExit(ExitTimeoutMilliseconds),
                "SolidWorks did not exit normally within 30 seconds");
            Require(Process.GetProcessesByName("SLDWORKS").Length == 0,
                "SolidWorks process remains after normal exit");

            receipt["status"] = "PASS_READ_ONLY_TRANSFORM_CONVENTION_EVIDENCE_CAPTURED";
            receipt["target_sha256_after"] = Sha256(targetPath);
            receipt["protected_stage_a_sha256_after"] = Sha256(protectedStageAPath);
            receipt["normal_document_close"] = true;
            receipt["normal_application_exit"] = true;
            receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");
            receipt["claim_limit"] =
                "TRANSFORM_CONVENTION_EVIDENCE_CAPTURE_ONLY_NO_S02_PASS_ACTIVE_CANDIDATE_OR_S03_CREDIT";
            Progress(progressPath, "PASS");
            WriteJsonCreateNew(receiptPath, receipt);
            process.Dispose();
            return 0;
        }
        catch (Exception ex)
        {
            receipt["status"] = "S02_R4_FAIL_CLOSED";
            receipt["failed_stage"] = stage;
            receipt["error_type"] = ex.GetType().FullName;
            receipt["error_message"] = ex.Message;
            receipt["failed_at_utc"] = DateTime.UtcNow.ToString("o");
            try { Progress(progressPath, "FAIL_" + stage); } catch { }
            try
            {
                if (app != null && model != null) app.CloseDoc(model.GetTitle());
            }
            catch { }
            ReleaseCom(model);
            ReleaseCom(utility);
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
            try { receipt["target_sha256_after_if_available"] = Sha256(targetPath); }
            catch { }
            try { receipt["protected_stage_a_sha256_after_if_available"] = Sha256(protectedStageAPath); }
            catch { }
            if (!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath, receipt);
            return 1;
        }
    }
}
