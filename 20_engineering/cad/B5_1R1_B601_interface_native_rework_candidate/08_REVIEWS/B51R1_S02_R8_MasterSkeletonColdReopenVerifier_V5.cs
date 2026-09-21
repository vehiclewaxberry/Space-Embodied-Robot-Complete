using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static class B51R1S02R8MasterSkeletonColdReopenVerifierV5
{
    private const int DocumentTypePart = 1;
    private const int OpenSilent = 1;
    private const int OpenReadOnly = 2;
    private const int CustomInfoText = 30;
    private const int RebuildReadbackCount = 10;
    private const int AttachTimeoutMilliseconds = 30000;
    private const int ExitTimeoutMilliseconds = 30000;
    private const double TranslationToleranceMetres = 1.0e-9;
    private const double RotationElementTolerance = 1.0e-10;
    private const double HomogeneousTolerance = 1.0e-12;

    private static readonly Dictionary<string, string> RequiredFeatures =
        new Dictionary<string, string>(StringComparer.Ordinal)
        {
            {"PLN_TASK_FACE_X183", "RefPlane"},
            {"PLN_M_DYNAMICS_X185_25", "RefPlane"},
            {"PLN_M_DISPLAY_X198", "RefPlane"},
            {"PLN_PRIMARY_PY_Y110_15", "RefPlane"},
            {"PLN_PRIMARY_NY_YN110_15", "RefPlane"},
            {"PLN_PRIMARY_PZ_Z110_15", "RefPlane"},
            {"PLN_PRIMARY_NZ_ZN110_15", "RefPlane"},
            {"PLN_PANEL_OUTER_PY_Y113_15", "RefPlane"},
            {"PLN_PANEL_OUTER_NY_YN113_15", "RefPlane"},
            {"PLN_PANEL_OUTER_PZ_Z113_15", "RefPlane"},
            {"PLN_PANEL_OUTER_NZ_ZN113_15", "RefPlane"},
            {"SK_IF_B601_MOUNT_160_SQUARE_KO_D100", "ProfileFeature"},
            {"SK_G07_G08_PANEL_FOOTPRINT_WINDOWS", "ProfileFeature"},
            {"SK3D_AX_LONGERON_PY_PZ_REF", "3DProfileFeature"},
            {"SK3D_AX_LONGERON_PY_NZ_REF", "3DProfileFeature"},
            {"SK3D_AX_LONGERON_NY_PZ_REF", "3DProfileFeature"},
            {"SK3D_AX_LONGERON_NY_NZ_REF", "3DProfileFeature"},
            {"AX_LONGERON_PY_PZ", "RefAxis"},
            {"AX_LONGERON_PY_NZ", "RefAxis"},
            {"AX_LONGERON_NY_PZ", "RefAxis"},
            {"AX_LONGERON_NY_NZ", "RefAxis"},
            {"CS_S", "CoordSys"},
            {"CS_M_DYNAMICS_X185_25", "CoordSys"},
            {"CS_M_DISPLAY_X198", "CoordSys"},
            {"CS_A0_CLOCKED_25_DEG", "CoordSys"}
        };

    private static readonly string[] RequiredConfigurations =
    {
        "COMMON_CANONICAL",
        "MODE_A_EVALUATION",
        "MODE_B_EVALUATION"
    };

    private static readonly string[] RepairPropertyNames =
    {
        "G1B_RECEIPT_SHA256",
        "FINAL_INPUT_LOCK_SHA256",
        "PANEL_PRIMARY_LOAD_CREDIT",
        "PANEL_ATTACHMENT_CREDIT",
        "PANEL_PHYSICAL_CONTACT_CREDIT"
    };

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static string Sha256(string path)
    {
        using (FileStream stream = File.OpenRead(path))
        using (SHA256 digest = SHA256.Create())
        {
            return BitConverter.ToString(digest.ComputeHash(stream)).Replace("-", "");
        }
    }

    private static bool SamePath(string left, string right)
    {
        return String.Equals(
            Path.GetFullPath(left).TrimEnd(Path.DirectorySeparatorChar),
            Path.GetFullPath(right).TrimEnd(Path.DirectorySeparatorChar),
            StringComparison.OrdinalIgnoreCase);
    }

    private static void ReleaseCom(object value)
    {
        if (value == null || !Marshal.IsComObject(value)) return;
        try { Marshal.FinalReleaseComObject(value); }
        catch { }
    }

    private static string OneLine(string value)
    {
        if (String.IsNullOrEmpty(value)) return value;
        return value.Replace("\r", " ").Replace("\n", " ").Trim();
    }

    private static void Progress(string path, string stage)
    {
        File.AppendAllText(
            path,
            DateTime.UtcNow.ToString("o") + "|" + stage + System.Environment.NewLine,
            new UTF8Encoding(false));
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

    private static string FormatArray(double[] values)
    {
        return "[" + String.Join(",", values.Select(value =>
            value.ToString("R", CultureInfo.InvariantCulture))) + "]";
    }

    private static void WriteJsonCreateNew(string path, Dictionary<string, object> data)
    {
        string directory = Path.GetDirectoryName(path);
        if (!String.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);
        string json = new JavaScriptSerializer { MaxJsonLength = Int32.MaxValue }
            .Serialize(data);
        using (FileStream stream = new FileStream(
            path, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
        using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false)))
        {
            writer.Write(json);
            writer.WriteLine();
        }
    }

    private static double[] ToDoubleArray(object raw)
    {
        Array array = raw as Array;
        Require(array != null, "Coordinate-system transform ArrayData is not an array");
        double[] values = new double[array.Length];
        int index = 0;
        foreach (object value in array) values[index++] = Convert.ToDouble(value);
        return values;
    }

    private static Dictionary<string, List<string>> FeatureTypesByName(ModelDoc2 model)
    {
        var result = new Dictionary<string, List<string>>(StringComparer.Ordinal);
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
                    string name = cursor.Name;
                    string type = cursor.GetTypeName2();
                    List<string> types;
                    if (!result.TryGetValue(name, out types))
                    {
                        types = new List<string>();
                        result.Add(name, types);
                    }
                    types.Add(type);
                }
                finally
                {
                    ReleaseCom(cursor);
                    cursor = next;
                }
            }
        }
        finally
        {
            ReleaseCom(cursor);
        }
        return result;
    }

    private static Feature FindUniqueFeature(ModelDoc2 model, string name, string expectedType)
    {
        Feature cursor = null;
        Feature retained = null;
        int count = 0;
        try
        {
            cursor = (Feature)model.FirstFeature();
            while (cursor != null)
            {
                Feature next = null;
                bool keep = false;
                try
                {
                    next = (Feature)cursor.GetNextFeature();
                    if (String.Equals(cursor.Name, name, StringComparison.Ordinal))
                    {
                        count++;
                        Require(
                            String.Equals(cursor.GetTypeName2(), expectedType, StringComparison.Ordinal),
                            "Feature " + name + " has type " + cursor.GetTypeName2() +
                            "; expected " + expectedType);
                        if (retained == null)
                        {
                            retained = cursor;
                            keep = true;
                        }
                    }
                }
                finally
                {
                    if (!keep) ReleaseCom(cursor);
                    cursor = next;
                }
            }
        }
        finally
        {
            ReleaseCom(cursor);
        }
        if (count != 1 || retained == null)
        {
            ReleaseCom(retained);
            throw new InvalidOperationException(
                "Expected exactly one " + expectedType + " named " + name +
                "; observed " + count);
        }
        return retained;
    }

    private static double MaximumError(double[] observed, double[] expected, int start, int count)
    {
        double maximum = 0.0;
        for (int index = start; index < start + count; index++)
        {
            maximum = Math.Max(maximum, Math.Abs(observed[index] - expected[index]));
        }
        return maximum;
    }

    private static double[] InvertRigidRowTransform(double[] transform)
    {
        Require(transform.Length == 16, "Cannot invert a non-16-element transform");
        // SOLIDWORKS stores a row-vector homogeneous transform as [R 0; t 1].
        // For a rigid transform its inverse is [R^T 0; -t R^T 1].
        double[] inverse =
        {
            transform[0], transform[3], transform[6],
            transform[1], transform[4], transform[7],
            transform[2], transform[5], transform[8],
            0, 0, 0,
            1, 0, 0, 0
        };
        inverse[9] = -(transform[9] * inverse[0] +
            transform[10] * inverse[3] + transform[11] * inverse[6]);
        inverse[10] = -(transform[9] * inverse[1] +
            transform[10] * inverse[4] + transform[11] * inverse[7]);
        inverse[11] = -(transform[9] * inverse[2] +
            transform[10] * inverse[5] + transform[11] * inverse[8]);
        return inverse;
    }

    private static Dictionary<string, object> ReadCoordinateSystem(
        ModelDoc2 model,
        string name,
        double expectedX,
        double expectedRxRadians)
    {
        Feature feature = null;
        CoordinateSystemFeatureData data = null;
        ModelDocExtension extension = null;
        MathTransform featureTransform = null;
        MathTransform namedTransform = null;
        bool selectionsAccessed = false;
        try
        {
            feature = FindUniqueFeature(model, name, "CoordSys");
            data = feature.GetDefinition() as CoordinateSystemFeatureData;
            Require(data != null, "CoordinateSystemFeatureData unavailable for " + name);
            selectionsAccessed = data.AccessSelections(model, null);
            Require(selectionsAccessed, "AccessSelections failed for " + name);
            featureTransform = data.Transform;
            Require(featureTransform != null,
                "CoordinateSystemFeatureData.Transform unavailable for " + name);

            extension = model.Extension;
            Require(extension != null, "ModelDocExtension unavailable for " + name);
            namedTransform = extension.GetCoordinateSystemTransformByName(name);
            Require(namedTransform != null,
                "GetCoordinateSystemTransformByName unavailable for " + name);

            double[] featureRaw = ToDoubleArray(featureTransform.ArrayData);
            double[] namedRaw = ToDoubleArray(namedTransform.ArrayData);
            Require(featureRaw.Length == 16 && namedRaw.Length == 16,
                "Expected two 16-element coordinate-system transforms for " + name);
            double dualApiRawError = MaximumError(featureRaw, namedRaw, 0, 16);
            Require(
                dualApiRawError <= HomogeneousTolerance,
                name + " dual-API raw transform mismatch; maximum error=" +
                dualApiRawError);

            // S02_R7 proved that both raw APIs return the controlled local
            // frame pose in model coordinates. Inverting this matrix creates
            // the false negative-X translation observed in S02_R2.
            double[] canonicalPose = namedRaw;

            double cosine = Math.Cos(expectedRxRadians);
            double sine = Math.Sin(expectedRxRadians);
            double[] expected =
            {
                1, 0, 0,
                0, cosine, sine,
                0, -sine, cosine,
                expectedX, 0, 0,
                1, 0, 0, 0
            };
            double rawHomogeneousError = MaximumError(namedRaw, expected, 12, 4);
            double rotationError = MaximumError(canonicalPose, expected, 0, 9);
            double translationError = MaximumError(canonicalPose, expected, 9, 3);
            double homogeneousError = MaximumError(canonicalPose, expected, 12, 4);
            Require(
                rawHomogeneousError <= HomogeneousTolerance,
                name + " raw transform scale/tail mismatch; maximum error=" +
                rawHomogeneousError);
            Require(
                rotationError <= RotationElementTolerance,
                name + " local-to-model rotation mismatch; maximum error=" +
                rotationError + "; raw_model_to_local=" + FormatArray(namedRaw) +
                "; local_to_model=" + FormatArray(canonicalPose));
            Require(
                translationError <= TranslationToleranceMetres,
                name + " local-to-model translation mismatch; maximum error=" +
                translationError + " m; local_to_model=" + FormatArray(canonicalPose));
            Require(
                homogeneousError <= HomogeneousTolerance,
                name + " homogeneous transform tail mismatch; maximum error=" +
                homogeneousError);

            double recoveredRx = Math.Atan2(canonicalPose[5], canonicalPose[4]);
            Require(
                Math.Abs(recoveredRx - expectedRxRadians) <= RotationElementTolerance,
                name + " recovered +Rx angle mismatch");

            return new Dictionary<string, object>
            {
                {"name", name},
                {"api_readback",
                    "ICoordinateSystemFeatureData.Transform_AND_IModelDocExtension.GetCoordinateSystemTransformByName"},
                {"raw_local_to_model_feature_data_array", featureRaw},
                {"raw_local_to_model_named_api_array", namedRaw},
                {"dual_api_raw_max_abs_error", dualApiRawError},
                {"canonical_local_to_model_pose_array", canonicalPose},
                {"canonical_pose_source",
                    "RAW_ICoordinateSystemFeatureData.Transform_AND_RAW_IModelDocExtension.GetCoordinateSystemTransformByName"},
                {"raw_homogeneous_tail_max_abs_error", rawHomogeneousError},
                {"expected_translation_m", new double[] {expectedX, 0, 0}},
                {"expected_rx_rad", expectedRxRadians},
                {"expected_rx_deg", expectedRxRadians * 180.0 / Math.PI},
                {"recovered_rx_rad", recoveredRx},
                {"rotation_matrix_max_abs_error", rotationError},
                {"translation_max_abs_error_m", translationError},
                {"homogeneous_tail_max_abs_error", homogeneousError},
                {"rotation_element_tolerance", RotationElementTolerance},
                {"translation_tolerance_m", TranslationToleranceMetres},
                {"homogeneous_tolerance", HomogeneousTolerance},
                {"solidworks_transform_convention",
                    "RAW_ARRAYDATA_IS_CONTROLLED_LOCAL_TO_MODEL_POSE_PER_S02_R7_CROSS_EVIDENCE"}
            };
        }
        finally
        {
            if (data != null && selectionsAccessed)
            {
                try { data.ReleaseSelectionAccess(); }
                catch { }
            }
            ReleaseCom(namedTransform);
            ReleaseCom(featureTransform);
            ReleaseCom(extension);
            ReleaseCom(data);
            ReleaseCom(feature);
        }
    }

    private static Dictionary<string, object> ReadReferencePlane(
        ModelDoc2 model,
        string name,
        int expectedNormalAxis,
        double expectedSignedOffsetMetres)
    {
        Feature feature = null;
        RefPlane plane = null;
        MathTransform planeTransform = null;
        try
        {
            feature = FindUniqueFeature(model, name, "RefPlane");
            plane = feature.GetSpecificFeature2() as RefPlane;
            Require(plane != null, "IRefPlane unavailable for " + name);
            planeTransform = plane.Transform;
            Require(planeTransform != null, "IRefPlane.Transform unavailable for " + name);
            double[] raw = ToDoubleArray(planeTransform.ArrayData);
            Require(raw.Length == 16, "Expected 16 plane transform values for " + name);
            double[] pose = raw;

            double[] expectedOrigin = {0.0, 0.0, 0.0};
            expectedOrigin[expectedNormalAxis] = expectedSignedOffsetMetres;
            double originError = 0.0;
            for (int index = 0; index < 3; index++)
            {
                originError = Math.Max(
                    originError,
                    Math.Abs(pose[9 + index] - expectedOrigin[index]));
            }
            double nx = pose[6];
            double ny = pose[7];
            double nz = pose[8];
            double normalNorm = Math.Sqrt(nx * nx + ny * ny + nz * nz);
            Require(normalNorm > 0.0,
                "Reference-plane normal has zero norm for " + name);
            double[] unitNormal =
            {
                nx / normalNorm,
                ny / normalNorm,
                nz / normalNorm
            };
            double axisAlignment = Math.Abs(unitNormal[expectedNormalAxis]);
            double offAxisMaximum = 0.0;
            for (int index = 0; index < 3; index++)
            {
                if (index != expectedNormalAxis)
                    offAxisMaximum = Math.Max(offAxisMaximum, Math.Abs(unitNormal[index]));
            }
            double homogeneousError = MaximumError(
                pose,
                new double[]
                {
                    pose[0], pose[1], pose[2],
                    pose[3], pose[4], pose[5],
                    pose[6], pose[7], pose[8],
                    pose[9], pose[10], pose[11],
                    1, 0, 0, 0
                },
                12,
                4);
            Require(
                originError <= TranslationToleranceMetres,
                name + " plane origin mismatch; maximum error=" + originError + " m");
            Require(
                Math.Abs(1.0 - axisAlignment) <= RotationElementTolerance &&
                offAxisMaximum <= RotationElementTolerance,
                name + " plane normal is not parallel to expected model axis");
            Require(
                homogeneousError <= HomogeneousTolerance,
                name + " plane transform scale/tail mismatch; maximum error=" +
                homogeneousError);

            return new Dictionary<string, object>
            {
                {"name", name},
                {"api_readback", "IFeature.GetSpecificFeature2_IRefPlane.Transform_RAW"},
                {"raw_plane_to_model_array", raw},
                {"canonical_plane_to_model_array", pose},
                {"expected_origin_m", expectedOrigin},
                {"observed_origin_m", new double[] {pose[9], pose[10], pose[11]}},
                {"origin_max_abs_error_m", originError},
                {"expected_normal_axis_index", expectedNormalAxis},
                {"observed_unit_normal", unitNormal},
                {"absolute_axis_alignment", axisAlignment},
                {"off_axis_max_abs_component", offAxisMaximum},
                {"homogeneous_tail_max_abs_error", homogeneousError},
                {"translation_tolerance_m", TranslationToleranceMetres},
                {"direction_component_tolerance", RotationElementTolerance},
                {"homogeneous_tolerance", HomogeneousTolerance}
            };
        }
        finally
        {
            ReleaseCom(planeTransform);
            ReleaseCom(plane);
            ReleaseCom(feature);
        }
    }

    private static Dictionary<string, object> ReadReferenceAxis(
        ModelDoc2 model,
        string name,
        double expectedY,
        double expectedZ)
    {
        Feature feature = null;
        RefAxis axis = null;
        try
        {
            feature = FindUniqueFeature(model, name, "RefAxis");
            axis = feature.GetSpecificFeature2() as RefAxis;
            Require(axis != null, "IRefAxis unavailable for " + name);
            double[] observed = ToDoubleArray(axis.GetRefAxisParams());
            Require(observed.Length == 6,
                "Expected six IRefAxis endpoint values for " + name);
            double[] expected =
            {
                -0.183, expectedY, expectedZ,
                 0.183, expectedY, expectedZ
            };
            double directError = MaximumError(observed, expected, 0, 6);
            double[] reversed =
            {
                observed[3], observed[4], observed[5],
                observed[0], observed[1], observed[2]
            };
            double reversedError = MaximumError(reversed, expected, 0, 6);
            double endpointError = Math.Min(directError, reversedError);
            Require(
                endpointError <= TranslationToleranceMetres,
                name + " endpoint geometry mismatch; direct error=" +
                directError + " m; reversed error=" + reversedError +
                " m; observed=" + FormatArray(observed));
            return new Dictionary<string, object>
            {
                {"name", name},
                {"api_readback", "IRefAxis.GetRefAxisParams"},
                {"observed_endpoints_m", observed},
                {"expected_endpoints_m", expected},
                {"endpoint_order_semantics", "UNORIENTED_AXIS_ACCEPTS_REVERSED_ENDPOINT_ORDER"},
                {"accepted_order",
                    directError <= reversedError ? "DIRECT" : "REVERSED"},
                {"direct_max_abs_error_m", directError},
                {"reversed_max_abs_error_m", reversedError},
                {"accepted_max_abs_error_m", endpointError},
                {"translation_tolerance_m", TranslationToleranceMetres}
            };
        }
        finally
        {
            ReleaseCom(axis);
            ReleaseCom(feature);
        }
    }

    private static List<string> ConfigurationNames(ModelDoc2 model)
    {
        object raw = model.GetConfigurationNames();
        Array array = raw as Array;
        Require(array != null, "GetConfigurationNames did not return an array");
        var result = new List<string>();
        foreach (object value in array) result.Add(Convert.ToString(value));
        result.Sort(StringComparer.Ordinal);
        return result;
    }

    private static Dictionary<string, object> ReadProperty(
        CustomPropertyManager manager,
        string name,
        string expected)
    {
        string raw;
        string resolved;
        bool wasResolved;
        bool linked;
        int result = manager.Get6(name, false, out raw, out resolved, out wasResolved, out linked);
        Require(result == 2,
            "Custom property " + name +
            " was not freshly resolved; Get6 result=" + result);
        int fieldType = manager.GetType2(name);
        Require(fieldType == CustomInfoText,
            "Custom property " + name + " type=" + fieldType +
            "; expected text=30");
        Require(wasResolved,
            "Custom property " + name + " was not resolved by Get6");
        Require(!linked,
            "Custom property " + name + " unexpectedly contains a linked expression");
        Require(
            String.Equals(raw, expected, StringComparison.Ordinal),
            "Custom property " + name + " raw value mismatch: " + raw);
        Require(
            String.Equals(resolved, expected, StringComparison.Ordinal),
            "Custom property " + name + " resolved value mismatch: " + resolved);
        return new Dictionary<string, object>
        {
            {"name", name},
            {"raw", raw},
            {"resolved", resolved},
            {"get6_result", result},
            {"field_type", fieldType},
            {"was_resolved", wasResolved},
            {"linked", linked}
        };
    }

    private static Dictionary<string, object> VerifyNoConfigurationLevelRepairProperties(
        ModelDoc2 model,
        int iteration,
        string activeConfiguration,
        string progressPath)
    {
        var configurations = new List<Dictionary<string, object>>();
        foreach (string configurationName in RequiredConfigurations)
        {
            Progress(progressPath, String.Format(
                CultureInfo.InvariantCulture,
                "CYCLE_{0:D2}_{1}_LEGACY_CONFIG_ENUM_{2}",
                iteration,
                activeConfiguration,
                configurationName));
            Array rawNames = model.GetCustomInfoNames2(configurationName) as Array;
            var names = new List<string>();
            if (rawNames != null)
            {
                foreach (object rawName in rawNames)
                    names.Add(Convert.ToString(rawName));
            }
            int legacyCount = model.GetCustomInfoCount2(configurationName);
            Require(legacyCount == names.Count,
                "Legacy configuration property count mismatch: " + configurationName);
            string[] duplicates = names.Where(name =>
                RepairPropertyNames.Contains(name, StringComparer.Ordinal)).ToArray();
            Require(duplicates.Length == 0,
                "Repair property exists at configuration level " + configurationName +
                ": " + String.Join(",", duplicates));
            configurations.Add(new Dictionary<string, object>
            {
                {"configuration", configurationName},
                {"configuration_property_count", names.Count},
                {"repair_property_duplicate_count", duplicates.Length},
                {"enumeration_api", "IModelDoc2.GetCustomInfoNames2"}
            });
        }
        return new Dictionary<string, object>
        {
            {"configuration_count", configurations.Count},
            {"repair_property_duplicate_count", 0},
            {"enumeration_api", "IModelDoc2.GetCustomInfoNames2"},
            {"configurations", configurations}
        };
    }

    private static int BodyCount(ModelDoc2 model, int bodyType)
    {
        object raw = ((PartDoc)model).GetBodies2(bodyType, false);
        Array bodies = raw as Array;
        if (bodies == null) return 0;
        try
        {
            return bodies.Length;
        }
        finally
        {
            foreach (object body in bodies) ReleaseCom(body);
        }
    }

    private static Dictionary<string, object> ReadNoBodyMassEvidence(ModelDoc2 model)
    {
        ModelDocExtension extension = null;
        try
        {
            extension = model.Extension;
            Require(extension != null,
                "ModelDocExtension unavailable for mass-property readback");
            int status = -1;
            object raw = extension.GetMassProperties2(2, out status, false);
            Array values = raw as Array;
            int valueCount = values == null ? 0 : values.Length;
            Require(status == 2,
                "Expected swMassPropertiesStatus_NoBody=2; observed " + status);
            return new Dictionary<string, object>
            {
                {"api", "IModelDocExtension.GetMassProperties2"},
                {"accuracy", 2},
                {"use_selected", false},
                {"status", status},
                {"expected_status", "swMassPropertiesStatus_NoBody"},
                {"returned_value_count", valueCount},
                {"returned_payload_shape_is_advisory", true},
                {"cad_mass_kg", 0.0},
                {"basis", "NO_SOLID_BODY_AND_API_NO_BODY_STATUS"}
            };
        }
        finally
        {
            ReleaseCom(extension);
        }
    }

    private static Dictionary<string, object> RebuildActiveConfigurationAndReadback(
        ModelDoc2 model,
        int iteration,
        string activeConfiguration,
        string expectedG1bSha256,
        string expectedFinalLockSha256,
        string progressPath)
    {
        Require(
            String.Equals(
                ActiveConfigurationName(model),
                activeConfiguration,
                StringComparison.Ordinal),
            "Active configuration mismatch before rebuild: expected " +
            activeConfiguration);
        Progress(progressPath, String.Format(
            CultureInfo.InvariantCulture,
            "CYCLE_{0:D2}_BEFORE_REBUILD_{1}",
            iteration,
            activeConfiguration));
        bool rebuildApiResult = model.ForceRebuild3(false);
        Progress(progressPath, String.Format(
            CultureInfo.InvariantCulture,
            "CYCLE_{0:D2}_AFTER_REBUILD_{1}",
            iteration,
            activeConfiguration));
        Require(rebuildApiResult,
            "ForceRebuild3 did not rebuild all features at iteration " + iteration);
        Require(model.IsOpenedReadOnly(), "Document lost read-only state at iteration " + iteration);

        Dictionary<string, List<string>> inventory = FeatureTypesByName(model);
        int totalFeatureCount = inventory.Sum(pair => pair.Value.Count);
        Require(totalFeatureCount == 44,
            "Exact feature inventory count is " + totalFeatureCount +
            "; expected 44 at iteration " + iteration);
        var featureEvidence = new List<Dictionary<string, object>>();
        foreach (KeyValuePair<string, string> required in RequiredFeatures)
        {
            List<string> types;
            Require(inventory.TryGetValue(required.Key, out types),
                "Missing required feature at iteration " + iteration + ": " + required.Key);
            Require(types.Count == 1,
                "Required feature is not unique at iteration " + iteration + ": " + required.Key);
            Require(String.Equals(types[0], required.Value, StringComparison.Ordinal),
                "Required feature type mismatch at iteration " + iteration + ": " + required.Key);
            featureEvidence.Add(new Dictionary<string, object>
            {
                {"name", required.Key}, {"type", types[0]}, {"exact_count", types.Count}
            });
        }

        List<string> configurations = ConfigurationNames(model);
        string[] expectedConfigurations = RequiredConfigurations
            .OrderBy(value => value, StringComparer.Ordinal).ToArray();
        Require(configurations.SequenceEqual(expectedConfigurations, StringComparer.Ordinal),
            "Configuration set mismatch at iteration " + iteration);

        ModelDocExtension extension = null;
        CustomPropertyManager manager = null;
        var properties = new List<Dictionary<string, object>>();
        Dictionary<string, object> configurationPropertyScope =
            VerifyNoConfigurationLevelRepairProperties(
                model, iteration, activeConfiguration, progressPath);
        try
        {
            extension = model.Extension;
            Require(extension != null, "ModelDocExtension unavailable");
            manager = extension.get_CustomPropertyManager("");
            Require(manager != null, "Document-level CustomPropertyManager unavailable");
            properties.Add(ReadProperty(
                manager, "OBJECT_ID", "B51R1_MASTER_SKELETON_V2"));
            properties.Add(ReadProperty(manager, "MODEL_ROLE", "MASTER_SKELETON"));
            properties.Add(ReadProperty(manager, "BOM_EXCLUDE", "TRUE"));
            properties.Add(ReadProperty(manager, "FRAME_ID", "CS_S"));
            properties.Add(ReadProperty(
                manager,
                "EVIDENCE_STATE",
                "EVIDENCE_BOUND_SOURCE_BOUND_MEASUREMENT_PASS"));
            properties.Add(ReadProperty(manager, "H9_STATUS", "HUMAN_DECISION_REQUIRED"));
            properties.Add(ReadProperty(
                manager, "MODE_A_STATUS", "EVALUATION_NOT_SELECTED"));
            properties.Add(ReadProperty(
                manager, "MODE_B_STATUS", "EVALUATION_NOT_SELECTED"));
            properties.Add(ReadProperty(
                manager,
                "MEASUREMENT_GATE_SHA256",
                "94400C1E282A9B35084E68B7A1B53DCC41BF33113D908C7895D0B73C672904FB"));
            properties.Add(ReadProperty(
                manager,
                "ACCEPTED_URDF_SHA256",
                "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"));
            properties.Add(ReadProperty(manager, "BUILD_STRATEGY", "ISOLATED_WORK_PART_THEN_FINAL_SAVEAS"));
            properties.Add(ReadProperty(manager, "G07_G08_CONTACT_WINDOW_STATUS",
                "NATIVE_SOURCE_BOUND_PANEL_FOOTPRINT_ONLY_NO_CONTACT_CREDIT"));
            properties.Add(ReadProperty(
                manager,
                "CLAIM_LIMIT",
                "DATUM_INTERFACE_CONTROL_ONLY_NO_MASS_STIFFNESS_ATTACHMENT_FLIGHT_CREDIT"));
            properties.Add(ReadProperty(
                manager, "KO_SOLAR_SWEEP_STATUS", "NOT_EVALUATED_UNKNOWN_PARAM"));
            properties.Add(ReadProperty(
                manager, "KO_ARM_RELEASE_STATUS", "NOT_EVALUATED_UNKNOWN_PARAM"));
            properties.Add(ReadProperty(manager, "G1B_RECEIPT_SHA256", expectedG1bSha256));
            properties.Add(ReadProperty(manager, "FINAL_INPUT_LOCK_SHA256", expectedFinalLockSha256));
            properties.Add(ReadProperty(manager, "PANEL_PRIMARY_LOAD_CREDIT", "NONE"));
            properties.Add(ReadProperty(manager, "PANEL_ATTACHMENT_CREDIT", "NONE"));
            properties.Add(ReadProperty(manager, "PANEL_PHYSICAL_CONTACT_CREDIT", "NONE"));
            properties.Add(ReadProperty(manager, "MASS_AUTHORITY", "NONE"));
            properties.Add(ReadProperty(manager, "MASS_OWNER", "NONE_REFERENCE_ONLY"));
            properties.Add(ReadProperty(manager, "MATERIAL", "NONE"));
            properties.Add(ReadProperty(manager, "MANUFACTURING_AUTHORITY", "NONE"));
        }
        finally
        {
            ReleaseCom(manager);
            ReleaseCom(extension);
        }

        var transforms = new List<Dictionary<string, object>>
        {
            ReadCoordinateSystem(model, "CS_S", 0.0, 0.0),
            ReadCoordinateSystem(model, "CS_M_DYNAMICS_X185_25", 0.18525, 0.0),
            ReadCoordinateSystem(model, "CS_M_DISPLAY_X198", 0.198, 0.0),
            ReadCoordinateSystem(model, "CS_A0_CLOCKED_25_DEG", 0.18525, 25.0 * Math.PI / 180.0)
        };

        var referencePlanes = new List<Dictionary<string, object>>
        {
            ReadReferencePlane(model, "PLN_TASK_FACE_X183", 0, 0.183),
            ReadReferencePlane(model, "PLN_M_DYNAMICS_X185_25", 0, 0.18525),
            ReadReferencePlane(model, "PLN_M_DISPLAY_X198", 0, 0.198),
            ReadReferencePlane(model, "PLN_PRIMARY_PY_Y110_15", 1, 0.11015),
            ReadReferencePlane(model, "PLN_PRIMARY_NY_YN110_15", 1, -0.11015),
            ReadReferencePlane(model, "PLN_PANEL_OUTER_PY_Y113_15", 1, 0.11315),
            ReadReferencePlane(model, "PLN_PANEL_OUTER_NY_YN113_15", 1, -0.11315),
            ReadReferencePlane(model, "PLN_PRIMARY_PZ_Z110_15", 2, 0.11015),
            ReadReferencePlane(model, "PLN_PRIMARY_NZ_ZN110_15", 2, -0.11015),
            ReadReferencePlane(model, "PLN_PANEL_OUTER_PZ_Z113_15", 2, 0.11315),
            ReadReferencePlane(model, "PLN_PANEL_OUTER_NZ_ZN113_15", 2, -0.11315)
        };

        var referenceAxes = new List<Dictionary<string, object>>
        {
            ReadReferenceAxis(model, "AX_LONGERON_PY_PZ", 0.10165, 0.10165),
            ReadReferenceAxis(model, "AX_LONGERON_PY_NZ", 0.10165, -0.10165),
            ReadReferenceAxis(model, "AX_LONGERON_NY_PZ", -0.10165, 0.10165),
            ReadReferenceAxis(model, "AX_LONGERON_NY_NZ", -0.10165, -0.10165)
        };

        int solidBodies = BodyCount(model, 0);
        int allBodies = BodyCount(model, -1);
        int externalReferences = model.ListExternalFileReferencesCount2();
        Require(solidBodies == 0,
            "Solid body count is " + solidBodies + " at iteration " + iteration);
        Require(allBodies == 0,
            "All-body count is " + allBodies + " at iteration " + iteration);
        Require(externalReferences == 0,
            "External file reference count is " + externalReferences + " at iteration " + iteration);
        Dictionary<string, object> massEvidence = ReadNoBodyMassEvidence(model);

        return new Dictionary<string, object>
        {
            {"iteration", iteration},
            {"active_configuration", activeConfiguration},
            {"force_rebuild3_api_return", rebuildApiResult},
            {"read_only", model.IsOpenedReadOnly()},
            {"save_flag_after_rebuild", model.GetSaveFlag()},
            {"feature_inventory_count", totalFeatureCount},
            {"required_feature_count", featureEvidence.Count},
            {"required_features", featureEvidence},
            {"configurations", configurations},
            {"custom_properties", properties},
            {"configuration_property_scope", configurationPropertyScope},
            {"coordinate_systems", transforms},
            {"reference_planes", referencePlanes},
            {"reference_axes", referenceAxes},
            {"solid_body_count", solidBodies},
            {"all_body_count", allBodies},
            {"external_file_reference_count", externalReferences},
            {"mass_properties", massEvidence}
        };
    }

    private static Dictionary<string, object> RebuildAndReadbackCycle(
        ModelDoc2 model,
        int iteration,
        string expectedG1bSha256,
        string expectedFinalLockSha256,
        string progressPath)
    {
        string initialConfiguration = ActiveConfigurationName(model);
        var configurationReadbacks =
            new List<Dictionary<string, object>>();
        try
        {
            foreach (string configuration in RequiredConfigurations)
            {
                string before = ActiveConfigurationName(model);
                bool showCalled = !String.Equals(
                    before, configuration, StringComparison.Ordinal);
                if (showCalled)
                {
                    Progress(progressPath, String.Format(
                        CultureInfo.InvariantCulture,
                        "CYCLE_{0:D2}_BEFORE_SHOW_{1}_TO_{2}",
                        iteration,
                        before,
                        configuration));
                    Require(
                        model.ShowConfiguration2(configuration),
                        "Could not activate configuration " + configuration +
                        " at cycle " + iteration);
                    Progress(progressPath, String.Format(
                        CultureInfo.InvariantCulture,
                        "CYCLE_{0:D2}_AFTER_SHOW_{1}",
                        iteration,
                        configuration));
                }
                else
                {
                    Progress(progressPath, String.Format(
                        CultureInfo.InvariantCulture,
                        "CYCLE_{0:D2}_SKIP_SHOW_ALREADY_ACTIVE_{1}",
                        iteration,
                        configuration));
                }
                Require(
                    String.Equals(
                        ActiveConfigurationName(model),
                        configuration,
                        StringComparison.Ordinal),
                    "Configuration activation did not persist for " +
                    configuration + " at cycle " + iteration);
                configurationReadbacks.Add(
                    RebuildActiveConfigurationAndReadback(
                        model,
                        iteration,
                        configuration,
                        expectedG1bSha256,
                        expectedFinalLockSha256,
                        progressPath));
            }
        }
        finally
        {
            if (!String.IsNullOrWhiteSpace(initialConfiguration))
            {
                try
                {
                    string beforeRestore = ActiveConfigurationName(model);
                    if (!String.Equals(beforeRestore, initialConfiguration,
                        StringComparison.Ordinal))
                    {
                        Progress(progressPath, String.Format(
                            CultureInfo.InvariantCulture,
                            "CYCLE_{0:D2}_BEFORE_RESTORE_{1}_TO_{2}",
                            iteration,
                            beforeRestore,
                            initialConfiguration));
                        bool restored = model.ShowConfiguration2(initialConfiguration);
                        Progress(progressPath, String.Format(
                            CultureInfo.InvariantCulture,
                            restored ? "CYCLE_{0:D2}_AFTER_RESTORE_{1}" :
                                "CYCLE_{0:D2}_RESTORE_RETURNED_FALSE_{1}",
                            iteration,
                            initialConfiguration));
                    }
                }
                catch
                {
                    try { Progress(progressPath, String.Format(
                        CultureInfo.InvariantCulture,
                        "CYCLE_{0:D2}_RESTORE_EXCEPTION",
                        iteration)); }
                    catch { }
                }
            }
        }
        string restoredConfiguration = ActiveConfigurationName(model);
        Require(String.Equals(restoredConfiguration, initialConfiguration,
            StringComparison.Ordinal),
            "Cycle " + iteration + " did not restore the initial configuration");
        Require(
            configurationReadbacks.Count == RequiredConfigurations.Length,
            "Cycle " + iteration +
            " did not rebuild/read back all required configurations");
        return new Dictionary<string, object>
        {
            {"cycle", iteration},
            {"initial_configuration", initialConfiguration},
            {"configuration_rebuild_count", configurationReadbacks.Count},
            {"configuration_readbacks", configurationReadbacks},
            {"restored_configuration", restoredConfiguration}
        };
    }

    private static SldWorks AttachToExpectedProcess(int expectedProcessId)
    {
        DateTime deadline = DateTime.UtcNow.AddMilliseconds(AttachTimeoutMilliseconds);
        Exception last = null;
        while (DateTime.UtcNow < deadline)
        {
            try
            {
                SldWorks app = (SldWorks)Marshal.GetActiveObject("SldWorks.Application");
                if (app != null && app.GetProcessID() == expectedProcessId &&
                    app.Visible && app.StartupProcessCompleted)
                {
                    return app;
                }
                ReleaseCom(app);
            }
            catch (Exception ex)
            {
                last = ex;
            }
            Thread.Sleep(500);
        }
        throw new InvalidOperationException(
            "Could not attach to the expected fully started SolidWorks process within 30 seconds",
            last);
    }

    private static Process AssertSoleVisibleProcess(int expectedProcessId)
    {
        Process[] processes = Process.GetProcessesByName("SLDWORKS");
        try
        {
            Require(processes.Length == 1,
                "Expected exactly one SLDWORKS process; observed " + processes.Length);
            Process process = processes[0];
            process.Refresh();
            Require(process.Id == expectedProcessId,
                "Sole SLDWORKS PID does not match launched PID " + expectedProcessId);
            Require(!process.HasExited && process.Responding && process.MainWindowHandle != IntPtr.Zero,
                "Sole SLDWORKS process is not visible and responsive");
            return Process.GetProcessById(process.Id);
        }
        finally
        {
            foreach (Process process in processes) process.Dispose();
        }
    }

    [STAThread]
    public static int Run(
        string targetPath,
        string protectedStageAPath,
        string receiptPath,
        string progressPath,
        int expectedProcessId,
        string s01CurrentGatePath,
        string expectedS01CurrentGateSha256,
        string expectedTargetSha256,
        string expectedStageASha256,
        string expectedG1bSha256,
        string expectedFinalLockSha256)
    {
        var receipt = new Dictionary<string, object>
        {
            {"schema", "B51R1_S02_R8_MASTER_SKELETON_COLD_REOPEN_RECEIPT_V5"},
            {"session_id", "S02_R8"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"status", "S02_R8_FAIL_CLOSED_NOT_STARTED"},
            {"target_path", targetPath},
            {"protected_stage_a_path", protectedStageAPath},
            {"s01_current_gate_path", s01CurrentGatePath},
            {"progress_path", progressPath},
            {"expected_process_id", expectedProcessId},
            {"open_mode", "OpenDoc6_PART_SILENT_READ_ONLY"},
            {"save_api_call_count", 0},
            {"configuration_enumeration_api", "IModelDoc2.GetCustomInfoNames2"},
            {"required_rebuild_readback_cycle_count", RebuildReadbackCount},
            {"required_configuration_rebuild_count",
                RebuildReadbackCount * RequiredConfigurations.Length}
        };
        SldWorks app = null;
        ModelDoc2 model = null;
        Process process = null;
        string currentTitle = null;
        bool normalDocumentClose = false;
        bool normalApplicationExit = false;
        string failureStage = "PRECONDITIONS";
        try
        {
            Require(!File.Exists(receiptPath), "S02 receipt already exists; refusing overwrite");
            Require(!File.Exists(progressPath),
                "S02 progress log already exists; refusing overwrite");
            Require(new[] {targetPath, protectedStageAPath, s01CurrentGatePath,
                receiptPath, progressPath}.Select(Path.GetFullPath).Distinct(
                    StringComparer.OrdinalIgnoreCase).Count() == 5,
                "S02 input and output paths must be pairwise distinct");
            Progress(progressPath, failureStage);
            foreach (string path in new[] {targetPath, protectedStageAPath, s01CurrentGatePath})
            {
                Require(File.Exists(path), "Required S02 input is absent: " + path);
            }
            string targetHashBefore = Sha256(targetPath);
            string stageAHashBefore = Sha256(protectedStageAPath);
            string gateHashBefore = Sha256(s01CurrentGatePath);
            long targetBytesBefore = new FileInfo(targetPath).Length;
            long stageABytesBefore = new FileInfo(protectedStageAPath).Length;
            long gateBytesBefore = new FileInfo(s01CurrentGatePath).Length;
            DateTime targetWriteTimeBefore = File.GetLastWriteTimeUtc(targetPath);
            DateTime stageAWriteTimeBefore = File.GetLastWriteTimeUtc(protectedStageAPath);
            DateTime gateWriteTimeBefore = File.GetLastWriteTimeUtc(s01CurrentGatePath);
            Require(String.Equals(targetHashBefore, expectedTargetSha256, StringComparison.OrdinalIgnoreCase),
                "Final master-skeleton hash does not match the S01-bound expected hash");
            Require(String.Equals(stageAHashBefore, expectedStageASha256, StringComparison.OrdinalIgnoreCase),
                "Protected Stage A hash mismatch before S02");
            Require(String.Equals(gateHashBefore, expectedS01CurrentGateSha256, StringComparison.OrdinalIgnoreCase),
                "Versioned S01 current-gate hash mismatch before S02");

            receipt["target_sha256_before"] = targetHashBefore;
            receipt["protected_stage_a_sha256_before"] = stageAHashBefore;
            receipt["s01_current_gate_sha256_before"] = gateHashBefore;
            receipt["target_bytes_before"] = targetBytesBefore;
            receipt["protected_stage_a_bytes_before"] = stageABytesBefore;
            receipt["s01_current_gate_bytes_before"] = gateBytesBefore;
            receipt["target_last_write_time_utc_before"] =
                targetWriteTimeBefore.ToString("o");
            receipt["protected_stage_a_last_write_time_utc_before"] =
                stageAWriteTimeBefore.ToString("o");
            receipt["s01_current_gate_last_write_time_utc_before"] =
                gateWriteTimeBefore.ToString("o");
            process = AssertSoleVisibleProcess(expectedProcessId);

            failureStage = "ATTACH_EXPECTED_FRESH_PROCESS";
            Progress(progressPath, failureStage);
            app = AttachToExpectedProcess(expectedProcessId);
            Require(app.GetDocumentCount() == 0 && app.ActiveDoc == null,
                "Fresh S02 SolidWorks process is not document-empty before cold reopen");
            receipt["solidworks_revision"] = app.RevisionNumber();
            receipt["solidworks_process_id"] = app.GetProcessID();
            receipt["document_count_before_open"] = 0;

            failureStage = "OPEN_FINAL_TARGET_READ_ONLY";
            Progress(progressPath, failureStage);
            int openErrors = 0;
            int openWarnings = 0;
            model = app.OpenDoc6(
                targetPath,
                DocumentTypePart,
                OpenSilent | OpenReadOnly,
                "",
                ref openErrors,
                ref openWarnings);
            Require(model != null, "OpenDoc6 returned null for final master skeleton");
            Require(openErrors == 0 && openWarnings == 0,
                "OpenDoc6 errors/warnings were " + openErrors + "/" + openWarnings);
            Require(model.IsOpenedReadOnly(), "Final master skeleton did not open read-only");
            Require(SamePath(model.GetPathName(), targetPath),
                "Opened document path differs from the fixed final target");
            Require(app.GetDocumentCount() == 1,
                "Expected one open document after cold reopen");
            receipt["open_errors"] = openErrors;
            receipt["open_warnings"] = openWarnings;

            failureStage = "READ_INITIAL_ACTIVE_CONFIGURATION";
            Progress(progressPath, failureStage);
            receipt["cold_open_initial_active_configuration"] =
                ActiveConfigurationName(model);

            failureStage = "TEN_REBUILD_READBACK_CYCLES";
            Progress(progressPath, failureStage);
            var iterations = new List<Dictionary<string, object>>();
            for (int iteration = 1; iteration <= RebuildReadbackCount; iteration++)
            {
                Progress(progressPath, String.Format(
                    CultureInfo.InvariantCulture, "CYCLE_{0:D2}_BEGIN", iteration));
                iterations.Add(RebuildAndReadbackCycle(
                    model, iteration, expectedG1bSha256, expectedFinalLockSha256,
                    progressPath));
                Progress(progressPath, String.Format(
                    CultureInfo.InvariantCulture, "CYCLE_{0:D2}_PASS", iteration));
            }
            Require(iterations.Count == RebuildReadbackCount,
                "Did not complete exactly ten rebuild/readback cycles");
            receipt["rebuild_readbacks"] = iterations;

            failureStage = "CLOSE_DOCUMENT_WITHOUT_SAVE";
            Progress(progressPath, failureStage);
            currentTitle = model.GetTitle();
            Require(!String.IsNullOrWhiteSpace(currentTitle), "Open model title is unavailable");
            app.CloseDoc(currentTitle);
            ReleaseCom(model);
            model = null;
            Require(app.GetDocumentCount() == 0 && app.ActiveDoc == null,
                "SolidWorks session is not empty after read-only CloseDoc");
            normalDocumentClose = true;

            string targetHashAfterClose = Sha256(targetPath);
            string stageAHashAfterClose = Sha256(protectedStageAPath);
            string gateHashAfterClose = Sha256(s01CurrentGatePath);
            Require(String.Equals(targetHashAfterClose, targetHashBefore, StringComparison.Ordinal),
                "Final master-skeleton bytes changed during read-only S02");
            Require(String.Equals(stageAHashAfterClose, stageAHashBefore, StringComparison.Ordinal),
                "Protected Stage A bytes changed during S02");
            Require(String.Equals(gateHashAfterClose, gateHashBefore, StringComparison.Ordinal),
                "Versioned S01 current-gate bytes changed during S02");
            Require(new FileInfo(targetPath).Length == targetBytesBefore &&
                File.GetLastWriteTimeUtc(targetPath) == targetWriteTimeBefore,
                "Final master-skeleton length or write time changed during read-only S02");
            Require(new FileInfo(protectedStageAPath).Length == stageABytesBefore &&
                File.GetLastWriteTimeUtc(protectedStageAPath) == stageAWriteTimeBefore,
                "Protected Stage A length or write time changed during S02");
            Require(new FileInfo(s01CurrentGatePath).Length == gateBytesBefore &&
                File.GetLastWriteTimeUtc(s01CurrentGatePath) == gateWriteTimeBefore,
                "Versioned S01 current-gate length or write time changed during S02");

            failureStage = "NORMAL_APPLICATION_EXIT";
            Progress(progressPath, failureStage);
            app.ExitApp();
            ReleaseCom(app);
            app = null;
            GC.Collect();
            GC.WaitForPendingFinalizers();
            Require(process.WaitForExit(ExitTimeoutMilliseconds),
                "SolidWorks did not exit normally within 30 seconds");
            Process[] remaining = Process.GetProcessesByName("SLDWORKS");
            try
            {
                Require(remaining.Length == 0,
                    "SLDWORKS process count after normal ExitApp is " + remaining.Length);
            }
            finally
            {
                foreach (Process remainingProcess in remaining) remainingProcess.Dispose();
            }
            normalApplicationExit = true;

            string targetHashAfterExit = Sha256(targetPath);
            string stageAHashAfterExit = Sha256(protectedStageAPath);
            string gateHashAfterExit = Sha256(s01CurrentGatePath);
            Require(String.Equals(targetHashAfterExit, targetHashBefore, StringComparison.Ordinal),
                "Final master-skeleton hash changed after normal application exit");
            Require(String.Equals(stageAHashAfterExit, stageAHashBefore, StringComparison.Ordinal),
                "Protected Stage A hash changed after normal application exit");
            Require(String.Equals(gateHashAfterExit, gateHashBefore, StringComparison.Ordinal),
                "Versioned S01 current-gate hash changed after normal application exit");
            Require(new FileInfo(targetPath).Length == targetBytesBefore &&
                File.GetLastWriteTimeUtc(targetPath) == targetWriteTimeBefore,
                "Final master-skeleton length or write time changed after normal exit");
            Require(new FileInfo(protectedStageAPath).Length == stageABytesBefore &&
                File.GetLastWriteTimeUtc(protectedStageAPath) == stageAWriteTimeBefore,
                "Protected Stage A length or write time changed after normal exit");
            Require(new FileInfo(s01CurrentGatePath).Length == gateBytesBefore &&
                File.GetLastWriteTimeUtc(s01CurrentGatePath) == gateWriteTimeBefore,
                "Versioned S01 current-gate length or write time changed after normal exit");

            receipt["status"] = "S02_R8_MASTER_SKELETON_COLD_REOPEN_PASS";
            receipt["verification_scope"] =
                "READ_ONLY_PERSISTENCE_10_REBUILD_READBACK_CYCLES";
            receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");
            receipt["completed_rebuild_readback_count"] = iterations.Count;
            receipt["completed_configuration_rebuild_count"] =
                iterations.Count * RequiredConfigurations.Length;
            receipt["required_feature_count"] = RequiredFeatures.Count;
            receipt["s01_native_contract_required_feature_count"] = 21;
            receipt["controlled_feature_plus_helper_count"] =
                RequiredFeatures.Count;
            receipt["exact_feature_inventory_count"] = 44;
            receipt["required_configurations"] = RequiredConfigurations;
            receipt["solid_body_count"] = 0;
            receipt["all_body_count"] = 0;
            receipt["external_file_reference_count"] = 0;
            receipt["cad_mass_kg"] = 0.0;
            receipt["cad_mass_basis"] =
                "ZERO_SOLID_BODIES_PLUS_MASS_AUTHORITY_NONE_REFERENCE_DATUM_PART";
            receipt["normal_document_close"] = normalDocumentClose;
            receipt["normal_application_exit"] = normalApplicationExit;
            receipt["target_sha256_after"] = targetHashAfterExit;
            receipt["protected_stage_a_sha256_after"] = stageAHashAfterExit;
            receipt["s01_current_gate_sha256_after"] = gateHashAfterExit;
            receipt["target_bytes_after"] = new FileInfo(targetPath).Length;
            receipt["protected_stage_a_bytes_after"] =
                new FileInfo(protectedStageAPath).Length;
            receipt["s01_current_gate_bytes_after"] =
                new FileInfo(s01CurrentGatePath).Length;
            receipt["target_last_write_time_utc_after"] =
                File.GetLastWriteTimeUtc(targetPath).ToString("o");
            receipt["protected_stage_a_last_write_time_utc_after"] =
                File.GetLastWriteTimeUtc(protectedStageAPath).ToString("o");
            receipt["s01_current_gate_last_write_time_utc_after"] =
                File.GetLastWriteTimeUtc(s01CurrentGatePath).ToString("o");
            receipt["target_unchanged"] = true;
            receipt["protected_stage_a_unchanged"] = true;
            receipt["s01_current_gate_unchanged"] = true;
            receipt["save_api_call_count"] = 0;
            receipt["claim_limit"] =
                "MASTER_SKELETON_NATIVE_PERSISTENCE_ONLY; NO CARRIER ARTICULATION H10 T005 STRUCTURAL THERMAL MANUFACTURING OR FLIGHT CREDIT";
            Progress(progressPath, "PASS");
            WriteJsonCreateNew(receiptPath, receipt);
            process.Dispose();
            return 0;
        }
        catch (Exception ex)
        {
            receipt["status"] = "S02_R8_FAIL_CLOSED";
            receipt["failed_stage"] = failureStage;
            receipt["failed_at_utc"] = DateTime.UtcNow.ToString("o");
            receipt["error_type"] = ex.GetType().FullName;
            receipt["error_message"] = OneLine(ex.Message);
            receipt["error_hresult"] = "0x" + ex.HResult.ToString("X8");
            try { Progress(progressPath, "FAIL_" + failureStage); } catch { }
            try
            {
                if (app != null && model != null)
                {
                    string title = model.GetTitle();
                    if (!String.IsNullOrWhiteSpace(title)) app.CloseDoc(title);
                }
            }
            catch { }
            ReleaseCom(model);
            model = null;
            try
            {
                if (app != null && app.GetDocumentCount() == 0)
                {
                    normalDocumentClose = true;
                    app.ExitApp();
                }
            }
            catch { }
            ReleaseCom(app);
            app = null;
            GC.Collect();
            GC.WaitForPendingFinalizers();
            try
            {
                if (process != null)
                {
                    normalApplicationExit = process.WaitForExit(ExitTimeoutMilliseconds);
                    process.Dispose();
                }
            }
            catch { }
            receipt["normal_document_close_if_available"] = normalDocumentClose;
            receipt["normal_application_exit_if_available"] = normalApplicationExit;
            receipt["save_api_call_count"] = 0;
            try
            {
                if (File.Exists(targetPath)) receipt["target_sha256_after_if_available"] = Sha256(targetPath);
                if (File.Exists(protectedStageAPath))
                    receipt["protected_stage_a_sha256_after_if_available"] = Sha256(protectedStageAPath);
                if (File.Exists(s01CurrentGatePath))
                    receipt["s01_current_gate_sha256_after_if_available"] = Sha256(s01CurrentGatePath);
            }
            catch (Exception hashEx)
            {
                receipt["post_failure_hash_error"] = OneLine(hashEx.Message);
            }
            try
            {
                if (!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath, receipt);
            }
            catch { }
            return 1;
        }
    }
}
