using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static class B51R1S01CR02MasterSkeletonPropertyRepairV4
{
    private const int DocumentTypePart = 1;
    private const int OpenSilent = 1;
    private const int OpenReadOnly = 2;
    private const int SaveSilent = 1;
    private const int CustomInfoText = 30;
    private const int CustomPropertyOnlyIfNew = 0;
    private const int CustomInfoAddResultAddedOrChanged = 0;
    private const int CustomInfoGetResultNotPresent = 1;
    private const int CustomInfoGetResultResolvedValue = 2;
    private const int AttachTimeoutMilliseconds = 30000;
    private const int ExitTimeoutMilliseconds = 30000;
    private const int S01NativeContractRequiredFeatureCount = 21;
    private const int HelperFeatureCount = 4;
    private const int ControlledFeaturePlusHelperCount = 25;

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

    private static Dictionary<string, string> ExpectedProperties(
        string expectedG1bSha256,
        string expectedFinalInputLockSha256)
    {
        return new Dictionary<string, string>(StringComparer.Ordinal)
        {
            {"OBJECT_ID", "B51R1_MASTER_SKELETON_V2"},
            {"MODEL_ROLE", "MASTER_SKELETON"},
            {"BOM_EXCLUDE", "TRUE"},
            {"FRAME_ID", "CS_S"},
            {"EVIDENCE_STATE", "EVIDENCE_BOUND_SOURCE_BOUND_MEASUREMENT_PASS"},
            {"H9_STATUS", "HUMAN_DECISION_REQUIRED"},
            {"MODE_A_STATUS", "EVALUATION_NOT_SELECTED"},
            {"MODE_B_STATUS", "EVALUATION_NOT_SELECTED"},
            {"MEASUREMENT_GATE_SHA256", "94400C1E282A9B35084E68B7A1B53DCC41BF33113D908C7895D0B73C672904FB"},
            {"ACCEPTED_URDF_SHA256", "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"},
            {"BUILD_STRATEGY", "ISOLATED_WORK_PART_THEN_FINAL_SAVEAS"},
            {"G07_G08_CONTACT_WINDOW_STATUS", "NATIVE_SOURCE_BOUND_PANEL_FOOTPRINT_ONLY_NO_CONTACT_CREDIT"},
            {"CLAIM_LIMIT", "DATUM_INTERFACE_CONTROL_ONLY_NO_MASS_STIFFNESS_ATTACHMENT_FLIGHT_CREDIT"},
            {"KO_SOLAR_SWEEP_STATUS", "NOT_EVALUATED_UNKNOWN_PARAM"},
            {"KO_ARM_RELEASE_STATUS", "NOT_EVALUATED_UNKNOWN_PARAM"},
            {"G1B_RECEIPT_SHA256", expectedG1bSha256},
            {"FINAL_INPUT_LOCK_SHA256", expectedFinalInputLockSha256},
            {"PANEL_PRIMARY_LOAD_CREDIT", "NONE"},
            {"PANEL_ATTACHMENT_CREDIT", "NONE"},
            {"PANEL_PHYSICAL_CONTACT_CREDIT", "NONE"},
            {"MASS_AUTHORITY", "NONE"},
            {"MASS_OWNER", "NONE_REFERENCE_ONLY"},
            {"MATERIAL", "NONE"},
            {"MANUFACTURING_AUTHORITY", "NONE"}
        };
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

    private static int BodyCount(ModelDoc2 model, int bodyType)
    {
        object raw = ((PartDoc)model).GetBodies2(bodyType, false);
        Array bodies = raw as Array;
        if (bodies == null) return 0;
        try { return bodies.Length; }
        finally
        {
            foreach (object body in bodies) ReleaseCom(body);
        }
    }

    private static Dictionary<string, object> VerifyGeometryContract(ModelDoc2 model)
    {
        Dictionary<string, List<string>> inventory = FeatureTypesByName(model);
        int exactFeatureCount = inventory.Values.Sum(types => types.Count);
        Require(RequiredFeatures.Count == ControlledFeaturePlusHelperCount &&
            S01NativeContractRequiredFeatureCount + HelperFeatureCount ==
                ControlledFeaturePlusHelperCount,
            "Static required-feature count contract is inconsistent");
        Require(exactFeatureCount == 44,
            "Exact feature inventory is " + exactFeatureCount + "; expected 44");
        foreach (KeyValuePair<string, string> required in RequiredFeatures)
        {
            List<string> types;
            Require(inventory.TryGetValue(required.Key, out types),
                "Required native feature is absent: " + required.Key);
            Require(types.Count == 1 && String.Equals(
                types[0], required.Value, StringComparison.Ordinal),
                "Required native feature type/count mismatch: " + required.Key);
        }

        object rawConfigurations = model.GetConfigurationNames();
        Array configurationArray = rawConfigurations as Array;
        Require(configurationArray != null, "Configuration names are unavailable");
        var configurations = new List<string>();
        foreach (object item in configurationArray)
            configurations.Add(Convert.ToString(item));
        configurations.Sort(StringComparer.Ordinal);
        string[] expectedConfigurations = RequiredConfigurations
            .OrderBy(item => item, StringComparer.Ordinal).ToArray();
        Require(configurations.SequenceEqual(expectedConfigurations, StringComparer.Ordinal),
            "Configuration set mismatch");

        int solidBodies = BodyCount(model, 0);
        int allBodies = BodyCount(model, -1);
        int externalReferences = model.ListExternalFileReferencesCount2();
        Require(solidBodies == 0, "Solid body count is " + solidBodies);
        Require(allBodies == 0, "All-body count is " + allBodies);
        Require(externalReferences == 0,
            "External file reference count is " + externalReferences);

        return new Dictionary<string, object>
        {
            {"exact_feature_inventory_count", exactFeatureCount},
            {"s01_native_contract_required_feature_count",
                S01NativeContractRequiredFeatureCount},
            {"helper_feature_count", HelperFeatureCount},
            {"controlled_feature_plus_helper_count", RequiredFeatures.Count},
            {"configurations", configurations},
            {"solid_body_count", solidBodies},
            {"all_body_count", allBodies},
            {"external_file_reference_count", externalReferences}
        };
    }

    private static Dictionary<string, object> ReadResolvedProperty(
        CustomPropertyManager manager,
        string name,
        string expected)
    {
        string raw;
        string resolved;
        bool wasResolved;
        bool linked;
        int result = manager.Get6(
            name, false, out raw, out resolved, out wasResolved, out linked);
        Require(result == CustomInfoGetResultResolvedValue,
            "Custom property " + name + " Get6 result=" + result + "; expected 2");
        int fieldType = manager.GetType2(name);
        Require(fieldType == CustomInfoText,
            "Custom property " + name + " type=" + fieldType + "; expected text=30");
        Require(wasResolved, "Custom property " + name + " was not resolved");
        Require(!linked, "Custom property " + name + " is linked");
        Require(String.Equals(raw, expected, StringComparison.Ordinal),
            "Custom property " + name + " raw value mismatch");
        Require(String.Equals(resolved, expected, StringComparison.Ordinal),
            "Custom property " + name + " resolved value mismatch");
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
        string stage,
        string progressPath)
    {
        var configurations = new List<Dictionary<string, object>>();
        Array rawConfigurations = model.GetConfigurationNames() as Array;
        Require(rawConfigurations != null,
            "Configuration names are unavailable during property-scope verification");
        string[] configurationNames = rawConfigurations.Cast<object>()
            .Select(Convert.ToString).ToArray();
        Require(configurationNames.Length == RequiredConfigurations.Length &&
            RequiredConfigurations.All(required =>
                configurationNames.Contains(required, StringComparer.Ordinal)),
            "Configuration set mismatch during property-scope verification");

        foreach (string configurationName in RequiredConfigurations)
        {
            Progress(progressPath, stage + "_LEGACY_CONFIG_ENUM_" + configurationName);
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
        Require(configurations.Count == RequiredConfigurations.Length,
            "Configuration property-scope verification count mismatch");
        return new Dictionary<string, object>
        {
            {"stage", stage},
            {"configuration_count", configurations.Count},
            {"repair_property_duplicate_count", 0},
            {"enumeration_api", "IModelDoc2.GetCustomInfoNames2"},
            {"configurations", configurations}
        };
    }

    private static Dictionary<string, object> RequireMissingProperty(
        CustomPropertyManager manager,
        string name)
    {
        string raw;
        string resolved;
        bool wasResolved;
        bool linked;
        int result = manager.Get6(
            name, false, out raw, out resolved, out wasResolved, out linked);
        Require(result == CustomInfoGetResultNotPresent,
            "Source property " + name + " Get6 result=" + result +
            "; expected NotPresent=1 before repair");
        return new Dictionary<string, object>
        {
            {"name", name},
            {"get6_result_before", result},
            {"enum_before", "swCustomInfoGetResult_NotPresent"}
        };
    }

    private static List<Dictionary<string, object>> VerifyProperties(
        ModelDoc2 model,
        Dictionary<string, string> expectedProperties)
    {
        ModelDocExtension extension = null;
        CustomPropertyManager manager = null;
        var results = new List<Dictionary<string, object>>();
        try
        {
            extension = model.Extension;
            Require(extension != null, "ModelDocExtension is unavailable");
            manager = extension.get_CustomPropertyManager("");
            Require(manager != null, "Document-level CustomPropertyManager is unavailable");
            foreach (KeyValuePair<string, string> expected in expectedProperties)
                results.Add(ReadResolvedProperty(manager, expected.Key, expected.Value));
            Require(results.Count == expectedProperties.Count,
                "Property readback count mismatch");
            return results;
        }
        finally
        {
            ReleaseCom(manager);
            ReleaseCom(extension);
        }
    }

    private static List<Dictionary<string, object>> RepairFiveProperties(
        ModelDoc2 model,
        Dictionary<string, string> expectedProperties)
    {
        ModelDocExtension extension = null;
        CustomPropertyManager manager = null;
        var results = new List<Dictionary<string, object>>();
        try
        {
            extension = model.Extension;
            Require(extension != null, "ModelDocExtension is unavailable");
            manager = extension.get_CustomPropertyManager("");
            Require(manager != null, "Document-level CustomPropertyManager is unavailable");

            foreach (KeyValuePair<string, string> expected in expectedProperties)
            {
                if (!RepairPropertyNames.Contains(expected.Key, StringComparer.Ordinal))
                    ReadResolvedProperty(manager, expected.Key, expected.Value);
            }

            foreach (string name in RepairPropertyNames)
            {
                Dictionary<string, object> evidence = RequireMissingProperty(manager, name);
                int addResult = manager.Add3(
                    name,
                    CustomInfoText,
                    expectedProperties[name],
                    CustomPropertyOnlyIfNew);
                Require(addResult == CustomInfoAddResultAddedOrChanged,
                    "Add3 failed for " + name + " with result=" + addResult);
                evidence["add3_result"] = addResult;
                evidence["field_type"] = CustomInfoText;
                evidence["add_option"] = "swCustomPropertyOnlyIfNew";
                evidence["add_option_value"] = CustomPropertyOnlyIfNew;
                evidence["post_add_readback"] = ReadResolvedProperty(
                    manager, name, expectedProperties[name]);
                results.Add(evidence);
            }
            Require(results.Count == RepairPropertyNames.Length,
                "Did not repair exactly five properties");
            return results;
        }
        finally
        {
            ReleaseCom(manager);
            ReleaseCom(extension);
        }
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
                "Sole SLDWORKS PID does not match authorized PID " + expectedProcessId);
            Require(!process.HasExited && process.Responding &&
                process.MainWindowHandle != IntPtr.Zero,
                "Sole SLDWORKS process is not visible and responsive");
            return Process.GetProcessById(process.Id);
        }
        finally
        {
            foreach (Process item in processes) item.Dispose();
        }
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
                    return app;
                ReleaseCom(app);
            }
            catch (Exception ex) { last = ex; }
            Thread.Sleep(500);
        }
        throw new InvalidOperationException(
            "Could not attach to the authorized startup-complete SolidWorks process",
            last);
    }

    private static ModelDoc2 OpenPart(
        SldWorks app,
        string path,
        bool readOnly,
        out int errors,
        out int warnings)
    {
        errors = 0;
        warnings = 0;
        ModelDoc2 model = app.OpenDoc6(
            path,
            DocumentTypePart,
            OpenSilent | (readOnly ? OpenReadOnly : 0),
            "",
            ref errors,
            ref warnings);
        Require(model != null, "OpenDoc6 returned null for " + path);
        Require(errors == 0 && warnings == 0,
            "OpenDoc6 errors/warnings were " + errors + "/" + warnings);
        Require(model.IsOpenedReadOnly() == readOnly,
            readOnly ? "Document was not opened read-only" :
                "Isolated work document unexpectedly opened read-only");
        Require(SamePath(model.GetPathName(), path), "Opened path mismatch");
        return model;
    }

    [STAThread]
    public static int Run(
        string sourcePath,
        string isolatedWorkPath,
        string targetRevisionPath,
        string protectedStageAPath,
        string receiptPath,
        string progressPath,
        int expectedProcessId,
        string expectedSourceSha256,
        string expectedStageASha256,
        string expectedG1bSha256,
        string expectedFinalInputLockSha256)
    {
        var receipt = new Dictionary<string, object>
        {
            {"schema", "B51R1_S01_CR02_MASTER_SKELETON_PROPERTY_REPAIR_RECEIPT_V1"},
            {"session_id", "S01_CR02"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"status", "S01_CR02_FAIL_CLOSED_NOT_STARTED"},
            {"source_path", sourcePath},
            {"isolated_work_path", isolatedWorkPath},
            {"target_revision_path", targetRevisionPath},
            {"protected_stage_a_path", protectedStageAPath},
            {"progress_path", progressPath},
            {"expected_process_id", expectedProcessId},
            {"source_access_mode", "FILESYSTEM_HASH_GUARD_ONLY_NOT_OPENED_IN_CAD"},
            {"isolated_work_open_mode", "SILENT_WRITABLE"},
            {"target_overwrite_permitted", false},
            {"configuration_enumeration_api", "IModelDoc2.GetCustomInfoNames2"},
            {"failed_s01_cr01_work_reuse_allowed", false},
            {"repair_property_names", RepairPropertyNames}
        };
        SldWorks app = null;
        ModelDoc2 model = null;
        Process process = null;
        bool normalClose = false;
        bool normalExit = false;
        string failureStage = "PRECONDITIONS";
        string sourceHashBefore = null;
        long sourceBytesBefore = 0;
        DateTime sourceWriteBefore = default(DateTime);
        string stageAHashBefore = null;
        long stageABytesBefore = 0;
        DateTime stageAWriteBefore = default(DateTime);
        string targetHashAfterSave = null;
        long targetBytesAfterSave = 0;
        DateTime targetWriteAfterSave = default(DateTime);
        try
        {
            Require(!File.Exists(receiptPath), "Receipt already exists; refusing overwrite");
            Require(!File.Exists(progressPath),
                "Progress log already exists; refusing overwrite");
            string[] contractPaths =
            {
                sourcePath,
                isolatedWorkPath,
                targetRevisionPath,
                protectedStageAPath,
                receiptPath,
                progressPath
            };
            Require(contractPaths.Select(Path.GetFullPath).Distinct(
                StringComparer.OrdinalIgnoreCase).Count() == contractPaths.Length,
                "Source, work, target, Stage A and receipt paths must be pairwise distinct");
            Require(isolatedWorkPath.IndexOf("WORK_S01_CR02",
                StringComparison.OrdinalIgnoreCase) >= 0,
                "S01_CR02 requires a distinct WORK_S01_CR02 isolated path");
            Require(String.Equals(Path.GetFileName(sourcePath),
                "B51R1_MASTER_SKELETON_V2.SLDPRT", StringComparison.OrdinalIgnoreCase),
                "S01_CR02 source must be the protected V2 file");
            Require(String.Equals(Path.GetFileName(targetRevisionPath),
                "B51R1_MASTER_SKELETON_V2_R1.SLDPRT", StringComparison.OrdinalIgnoreCase),
                "S01_CR02 target revision filename mismatch");
            Require(File.Exists(sourcePath), "Source Master Skeleton is absent");
            Require(File.Exists(protectedStageAPath), "Protected Stage A is absent");
            Require(!File.Exists(isolatedWorkPath),
                "Isolated work path already exists; refusing overwrite");
            Require(!File.Exists(targetRevisionPath),
                "Target revision already exists; refusing overwrite");
            Progress(progressPath, failureStage);

            sourceHashBefore = Sha256(sourcePath);
            sourceBytesBefore = new FileInfo(sourcePath).Length;
            sourceWriteBefore = File.GetLastWriteTimeUtc(sourcePath);
            Require(String.Equals(sourceHashBefore, expectedSourceSha256,
                StringComparison.OrdinalIgnoreCase), "Source hash mismatch");
            stageAHashBefore = Sha256(protectedStageAPath);
            stageABytesBefore = new FileInfo(protectedStageAPath).Length;
            stageAWriteBefore = File.GetLastWriteTimeUtc(protectedStageAPath);
            Require(String.Equals(stageAHashBefore, expectedStageASha256,
                StringComparison.OrdinalIgnoreCase), "Protected Stage A hash mismatch");
            receipt["source_sha256_before"] = sourceHashBefore;
            receipt["source_bytes_before"] = sourceBytesBefore;
            receipt["source_last_write_time_utc_before"] = sourceWriteBefore.ToString("o");
            receipt["protected_stage_a_sha256_before"] = stageAHashBefore;
            receipt["protected_stage_a_bytes_before"] = stageABytesBefore;
            receipt["protected_stage_a_last_write_time_utc_before"] =
                stageAWriteBefore.ToString("o");

            failureStage = "CREATE_BYTE_IDENTICAL_ISOLATED_WORK_COPY";
            Progress(progressPath, failureStage);
            string workDirectory = Path.GetDirectoryName(isolatedWorkPath);
            if (!String.IsNullOrWhiteSpace(workDirectory))
                Directory.CreateDirectory(workDirectory);
            File.Copy(sourcePath, isolatedWorkPath, false);
            Require(String.Equals(Sha256(isolatedWorkPath), sourceHashBefore,
                StringComparison.Ordinal),
                "Isolated work copy is not byte-identical to the source");
            receipt["isolated_work_sha256_before"] = Sha256(isolatedWorkPath);
            receipt["isolated_work_bytes_before"] =
                new FileInfo(isolatedWorkPath).Length;

            process = AssertSoleVisibleProcess(expectedProcessId);
            failureStage = "ATTACH_EXISTING_AUTHORIZED_PROCESS";
            Progress(progressPath, failureStage);
            app = AttachToExpectedProcess(expectedProcessId);
            Require(app.GetDocumentCount() == 0 && app.ActiveDoc == null,
                "Authorized SolidWorks process is not document-empty");
            receipt["solidworks_revision"] = app.RevisionNumber();
            receipt["solidworks_process_id"] = app.GetProcessID();

            failureStage = "OPEN_ISOLATED_WORK_COPY";
            Progress(progressPath, failureStage);
            int openErrors;
            int openWarnings;
            model = OpenPart(
                app, isolatedWorkPath, false, out openErrors, out openWarnings);
            Require(app.GetDocumentCount() == 1,
                "Expected one isolated work document after OpenDoc6");
            receipt["isolated_work_open_errors"] = openErrors;
            receipt["isolated_work_open_warnings"] = openWarnings;

            failureStage = "VERIFY_SOURCE_GEOMETRY_AND_PROPERTY_PRESTATE";
            Progress(progressPath, failureStage);
            Dictionary<string, string> expectedProperties = ExpectedProperties(
                expectedG1bSha256, expectedFinalInputLockSha256);
            receipt["source_geometry_contract"] = VerifyGeometryContract(model);
            receipt["configuration_property_prestate"] =
                VerifyNoConfigurationLevelRepairProperties(
                    model, "PRE_REPAIR", progressPath);

            failureStage = "ADD_AND_VERIFY_FIVE_PROPERTIES";
            Progress(progressPath, failureStage);
            receipt["property_repairs"] = RepairFiveProperties(model, expectedProperties);
            Require(model.ForceRebuild3(false), "ForceRebuild3 failed after property repair");
            receipt["all_properties_before_save"] = VerifyProperties(
                model, expectedProperties);
            receipt["configuration_property_post_add"] =
                VerifyNoConfigurationLevelRepairProperties(
                    model, "POST_ADD_PRE_SAVE", progressPath);
            receipt["geometry_contract_before_save"] = VerifyGeometryContract(model);

            failureStage = "SAVE_AS_NEW_REVISION";
            Progress(progressPath, failureStage);
            Require(!File.Exists(targetRevisionPath),
                "Target revision appeared before SaveAs; refusing overwrite");
            Require(String.Equals(Sha256(sourcePath), sourceHashBefore,
                StringComparison.Ordinal),
                "Source hash changed before SaveAs");
            Require(String.Equals(Sha256(protectedStageAPath), expectedStageASha256,
                StringComparison.OrdinalIgnoreCase),
                "Protected Stage A hash changed before SaveAs");
            int saveErrors = 0;
            int saveWarnings = 0;
            bool saved = model.Extension.SaveAs(
                targetRevisionPath,
                0,
                SaveSilent,
                null,
                ref saveErrors,
                ref saveWarnings);
            Require(saved && saveErrors == 0 && saveWarnings == 0,
                "SaveAs failed with errors/warnings " + saveErrors + "/" + saveWarnings);
            Require(File.Exists(targetRevisionPath), "Target revision was not created");
            receipt["save_errors"] = saveErrors;
            receipt["save_warnings"] = saveWarnings;

            failureStage = "CLOSE_AFTER_SAVE_AS";
            Progress(progressPath, failureStage);
            string title = model.GetTitle();
            Require(!String.IsNullOrWhiteSpace(title), "Saved document title is unavailable");
            app.CloseDoc(title);
            ReleaseCom(model);
            model = null;
            Require(app.GetDocumentCount() == 0 && app.ActiveDoc == null,
                "SolidWorks is not document-empty after SaveAs CloseDoc");
            normalClose = true;
            Require(String.Equals(Sha256(sourcePath), sourceHashBefore, StringComparison.Ordinal),
                "Source hash changed during append-only repair");
            Require(new FileInfo(sourcePath).Length == sourceBytesBefore &&
                File.GetLastWriteTimeUtc(sourcePath) == sourceWriteBefore,
                "Source length or write time changed during append-only repair");
            Require(String.Equals(Sha256(isolatedWorkPath), sourceHashBefore,
                StringComparison.Ordinal),
                "Isolated work file changed; repair must persist only to the new revision");
            targetHashAfterSave = Sha256(targetRevisionPath);
            targetBytesAfterSave = new FileInfo(targetRevisionPath).Length;
            targetWriteAfterSave = File.GetLastWriteTimeUtc(targetRevisionPath);
            receipt["target_revision_sha256_after_save"] = targetHashAfterSave;
            receipt["target_revision_bytes_after_save"] = targetBytesAfterSave;
            receipt["target_revision_last_write_time_utc_after_save"] =
                targetWriteAfterSave.ToString("o");

            failureStage = "SAME_PROCESS_REOPEN_NEW_REVISION_READ_ONLY";
            Progress(progressPath, failureStage);
            model = OpenPart(
                app, targetRevisionPath, true, out openErrors, out openWarnings);
            receipt["revision_open_errors"] = openErrors;
            receipt["revision_open_warnings"] = openWarnings;
            receipt["revision_geometry_contract"] = VerifyGeometryContract(model);
            receipt["revision_properties"] = VerifyProperties(model, expectedProperties);
            receipt["revision_configuration_property_scope"] =
                VerifyNoConfigurationLevelRepairProperties(
                    model, "REVISION_REOPEN", progressPath);
            Require(model.ForceRebuild3(false),
                "ForceRebuild3 failed on same-process revision reopen");
            receipt["revision_geometry_contract_after_rebuild"] =
                VerifyGeometryContract(model);
            receipt["revision_properties_after_rebuild"] =
                VerifyProperties(model, expectedProperties);
            receipt["revision_configuration_property_scope_after_rebuild"] =
                VerifyNoConfigurationLevelRepairProperties(
                    model, "REVISION_REOPEN_AFTER_REBUILD", progressPath);

            failureStage = "CLOSE_REVISION_WITHOUT_SAVE";
            Progress(progressPath, failureStage);
            title = model.GetTitle();
            app.CloseDoc(title);
            ReleaseCom(model);
            model = null;
            Require(app.GetDocumentCount() == 0 && app.ActiveDoc == null,
                "SolidWorks is not document-empty after revision CloseDoc");

            failureStage = "NORMAL_APPLICATION_EXIT";
            Progress(progressPath, failureStage);
            app.ExitApp();
            ReleaseCom(app);
            app = null;
            GC.Collect();
            GC.WaitForPendingFinalizers();
            Require(process.WaitForExit(ExitTimeoutMilliseconds),
                "SolidWorks did not exit normally within 30 seconds");
            Require(Process.GetProcessesByName("SLDWORKS").Length == 0,
                "A SolidWorks process remains after ExitApp");
            normalExit = true;

            Require(String.Equals(Sha256(sourcePath), sourceHashBefore, StringComparison.Ordinal),
                "Source hash changed after normal exit");
            Require(String.Equals(Sha256(isolatedWorkPath), sourceHashBefore,
                StringComparison.Ordinal),
                "Isolated work copy changed after normal exit");
            Require(String.Equals(Sha256(protectedStageAPath), expectedStageASha256,
                StringComparison.OrdinalIgnoreCase), "Protected Stage A hash changed");
            Require(new FileInfo(protectedStageAPath).Length == stageABytesBefore &&
                File.GetLastWriteTimeUtc(protectedStageAPath) == stageAWriteBefore,
                "Protected Stage A length or write time changed");
            Require(String.Equals(Sha256(targetRevisionPath), targetHashAfterSave,
                StringComparison.Ordinal) &&
                new FileInfo(targetRevisionPath).Length == targetBytesAfterSave &&
                File.GetLastWriteTimeUtc(targetRevisionPath) == targetWriteAfterSave,
                "Target revision changed during read-only reopen or normal exit");

            receipt["status"] = "S01_CR02_PASS_APPEND_ONLY_PROPERTY_REPAIR_REVISION_CREATED";
            receipt["completed_at_utc"] = DateTime.UtcNow.ToString("o");
            receipt["target_revision_bytes"] = new FileInfo(targetRevisionPath).Length;
            receipt["target_revision_sha256"] = Sha256(targetRevisionPath);
            receipt["target_revision_last_write_time_utc"] =
                File.GetLastWriteTimeUtc(targetRevisionPath).ToString("o");
            receipt["source_sha256_after"] = Sha256(sourcePath);
            receipt["isolated_work_sha256_after"] = Sha256(isolatedWorkPath);
            receipt["protected_stage_a_sha256_after"] = Sha256(protectedStageAPath);
            receipt["protected_stage_a_bytes_after"] =
                new FileInfo(protectedStageAPath).Length;
            receipt["protected_stage_a_last_write_time_utc_after"] =
                File.GetLastWriteTimeUtc(protectedStageAPath).ToString("o");
            receipt["target_revision_unchanged_during_read_only_reopen"] = true;
            receipt["source_unchanged"] = true;
            receipt["isolated_work_preserved_as_original_byte_identical_copy"] =
                String.Equals(Sha256(isolatedWorkPath), sourceHashBefore,
                    StringComparison.Ordinal);
            receipt["protected_stage_a_unchanged"] = true;
            receipt["normal_document_close"] = normalClose;
            receipt["normal_application_exit"] = normalExit;
            receipt["claim_limit"] =
                "APPEND_ONLY_MASTER_SKELETON_PROPERTY_REPAIR_REVISION_ONLY; S02_COLD_PROCESS_REOPEN_STILL_REQUIRED; NO_S03_H10_T005_MANUFACTURING_OR_FLIGHT_CREDIT";
            Progress(progressPath, "PASS");
            WriteJsonCreateNew(receiptPath, receipt);
            process.Dispose();
            return 0;
        }
        catch (Exception ex)
        {
            receipt["status"] = "S01_CR02_FAIL_CLOSED";
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
                    normalClose = true;
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
                    normalExit = process.WaitForExit(ExitTimeoutMilliseconds);
                    process.Dispose();
                }
            }
            catch { }
            receipt["normal_document_close_if_available"] = normalClose;
            receipt["normal_application_exit_if_available"] = normalExit;
            try
            {
                if (File.Exists(sourcePath))
                {
                    receipt["source_sha256_after_if_available"] = Sha256(sourcePath);
                    receipt["source_unchanged_if_available"] =
                        sourceHashBefore != null && String.Equals(
                            Sha256(sourcePath), sourceHashBefore, StringComparison.Ordinal);
                }
                if (File.Exists(protectedStageAPath))
                    receipt["protected_stage_a_sha256_after_if_available"] =
                        Sha256(protectedStageAPath);
                if (File.Exists(isolatedWorkPath))
                {
                    receipt["isolated_work_sha256_after_if_available"] =
                        Sha256(isolatedWorkPath);
                    receipt["isolated_work_equals_source_if_available"] =
                        sourceHashBefore != null && String.Equals(
                            Sha256(isolatedWorkPath), sourceHashBefore,
                            StringComparison.Ordinal);
                }
                if (File.Exists(targetRevisionPath))
                {
                    receipt["rejected_target_revision_exists"] = true;
                    receipt["rejected_target_revision_sha256"] = Sha256(targetRevisionPath);
                    receipt["rejected_target_revision_disposition"] =
                        "PRESERVE_AS_REJECTED_APPEND_ONLY_CANDIDATE_DO_NOT_CLAIM_PASS";
                }
            }
            catch { }
            if (!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath, receipt);
            return 1;
        }
    }
}
