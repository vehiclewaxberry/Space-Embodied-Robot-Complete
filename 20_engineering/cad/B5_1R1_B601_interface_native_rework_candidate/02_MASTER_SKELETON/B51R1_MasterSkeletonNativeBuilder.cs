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

public static class B51R1MasterSkeletonNativeBuilder
{
    private const string MeasurementSha =
        "94400C1E282A9B35084E68B7A1B53DCC41BF33113D908C7895D0B73C672904FB";
    private const string UrdfSha =
        "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164";
    private static string ProgressPath;

    private static void Trace(string message)
    {
        if (String.IsNullOrWhiteSpace(ProgressPath))
        {
            return;
        }
        try
        {
            string line =
                DateTime.UtcNow.ToString("o") + " | " + message + System.Environment.NewLine;
            File.AppendAllText(ProgressPath, line, new UTF8Encoding(false));
        }
        catch
        {
            // The CAD transaction must not depend on the diagnostic log.
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
            Trace(
                "FAIL | " + label + " | " + ex.GetType().FullName + " | " +
                ex.Message.Replace("\r", " ").Replace("\n", " "));
            throw;
        }
    }

    private static void AddCreated(
        List<string> created,
        string label,
        Func<Feature> action)
    {
        Feature feature = Step(label, action);
        created.Add(feature.Name);
    }

    private static string Sha256(string path)
    {
        using (var stream = File.OpenRead(path))
        using (var sha = SHA256.Create())
        {
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "");
        }
    }

    private static HashSet<string> FeatureKeys(ModelDoc2 model)
    {
        var result = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        Feature feature = (Feature)model.FirstFeature();
        while (feature != null)
        {
            result.Add(feature.GetTypeName2() + "|" + feature.Name);
            feature = (Feature)feature.GetNextFeature();
        }
        return result;
    }

    private static Feature FindNewFeature(
        ModelDoc2 model,
        HashSet<string> before,
        params string[] acceptedTypes)
    {
        Feature selected = null;
        Feature feature = (Feature)model.FirstFeature();
        while (feature != null)
        {
            string typeName = feature.GetTypeName2() ?? "";
            string key = typeName + "|" + feature.Name;
            bool typeAccepted = acceptedTypes.Any(
                value => typeName.IndexOf(value, StringComparison.OrdinalIgnoreCase) >= 0);
            if (!before.Contains(key) && typeAccepted)
            {
                selected = feature;
            }
            feature = (Feature)feature.GetNextFeature();
        }
        return selected;
    }

    private static bool SelectDefaultPlane(ModelDoc2 model, params string[] names)
    {
        model.ClearSelection2(true);
        foreach (string name in names)
        {
            if (model.Extension.SelectByID2(name, "PLANE", 0, 0, 0, false, 0, null, 0))
            {
                return true;
            }
        }
        return false;
    }

    private static Feature AddOffsetPlane(
        ModelDoc2 model,
        string name,
        string[] basePlaneNames,
        double offsetMeters,
        bool flip)
    {
        if (!SelectDefaultPlane(model, basePlaneNames))
        {
            throw new InvalidOperationException(
                "Could not select default plane for " + name + ": " +
                string.Join("|", basePlaneNames));
        }
        int flags = 8 | (flip ? 256 : 0);
        object raw = model.FeatureManager.InsertRefPlane(flags, Math.Abs(offsetMeters), 0, 0, 0, 0);
        model.ClearSelection2(true);
        Feature feature = raw as Feature;
        if (feature == null)
        {
            throw new InvalidOperationException("InsertRefPlane returned null for " + name);
        }
        feature.Name = name;
        return feature;
    }

    private static Feature AddCoordinateSystem(
        ModelDoc2 model,
        string name,
        double x,
        double y,
        double z,
        double rx,
        double ry,
        double rz)
    {
        bool useRotation =
            Math.Abs(rx) > 1e-15 || Math.Abs(ry) > 1e-15 || Math.Abs(rz) > 1e-15;
        Feature feature = model.FeatureManager.CreateCoordinateSystemUsingNumericalValues(
            true, x, y, z, useRotation, rx, ry, rz);
        if (feature == null)
        {
            throw new InvalidOperationException(
                "CreateCoordinateSystemUsingNumericalValues returned null for " + name);
        }
        feature.Name = name;
        return feature;
    }

    private static Feature AddMountSketch(ModelDoc2 model)
    {
        model.ClearSelection2(true);
        if (!model.Extension.SelectByID2(
                "PLN_M_DYNAMICS_X185_25",
                "PLANE",
                0,
                0,
                0,
                false,
                0,
                null,
                0))
        {
            throw new InvalidOperationException("Could not select PLN_M_DYNAMICS_X185_25");
        }

        var before = FeatureKeys(model);
        SketchManager sketchManager = model.SketchManager;
        sketchManager.InsertSketch(true);
        object rectangle = sketchManager.CreateCenterRectangle(0, 0, 0, 0.08, 0.08, 0);
        SketchSegment circle = sketchManager.CreateCircleByRadius(0, 0, 0, 0.05);
        if (rectangle == null || circle == null)
        {
            throw new InvalidOperationException("Mount rectangle or keep-out circle creation failed");
        }
        sketchManager.InsertSketch(true);
        model.ClearSelection2(true);

        Feature sketchFeature = FindNewFeature(model, before, "ProfileFeature", "Sketch");
        if (sketchFeature == null)
        {
            throw new InvalidOperationException("Could not locate mount sketch feature");
        }
        sketchFeature.Name = "SK_IF_B601_MOUNT_160_SQUARE_KO_D100";
        return sketchFeature;
    }

    private static Feature AddLongeronAxis(
        ModelDoc2 model,
        string axisName,
        string sketchName,
        double y,
        double z)
    {
        SketchManager sketchManager = model.SketchManager;
        var beforeSketch = FeatureKeys(model);
        sketchManager.Insert3DSketch(true);
        SketchSegment segment = sketchManager.CreateLine(-0.183, y, z, 0.183, y, z);
        if (segment == null)
        {
            throw new InvalidOperationException("CreateLine failed for " + axisName);
        }
        sketchManager.Insert3DSketch(true);

        Feature sketchFeature = FindNewFeature(
            model, beforeSketch, "3DProfileFeature", "ProfileFeature", "Sketch");
        if (sketchFeature == null)
        {
            throw new InvalidOperationException("Could not locate 3D sketch for " + axisName);
        }
        sketchFeature.Name = sketchName;

        model.ClearSelection2(true);
        if (!segment.Select4(false, null))
        {
            throw new InvalidOperationException("Could not select 3D segment for " + axisName);
        }
        var beforeAxis = FeatureKeys(model);
        if (!model.InsertAxis2(true))
        {
            throw new InvalidOperationException("InsertAxis2 failed for " + axisName);
        }
        model.ClearSelection2(true);

        Feature axisFeature = FindNewFeature(model, beforeAxis, "RefAxis", "Axis");
        if (axisFeature == null)
        {
            throw new InvalidOperationException("Could not locate reference axis " + axisName);
        }
        axisFeature.Name = axisName;
        return axisFeature;
    }

    private static void AddProperty(CustomPropertyManager manager, string name, string value)
    {
        manager.Add3(name, 30, value, 2);
    }

    private static List<Dictionary<string, object>> FeatureInventory(ModelDoc2 model)
    {
        var result = new List<Dictionary<string, object>>();
        Feature feature = (Feature)model.FirstFeature();
        while (feature != null)
        {
            result.Add(new Dictionary<string, object>
            {
                {"name", feature.Name},
                {"type", feature.GetTypeName2()}
            });
            feature = (Feature)feature.GetNextFeature();
        }
        return result;
    }

    private static List<string> ConfigurationNames(ModelDoc2 model)
    {
        object raw = model.GetConfigurationNames();
        if (raw == null)
        {
            return new List<string>();
        }
        return ((object[])raw).Select(value => Convert.ToString(value)).ToList();
    }

    private static int SolidBodyCount(ModelDoc2 model)
    {
        PartDoc part = (PartDoc)model;
        object raw = part.GetBodies2(0, true);
        if (raw == null)
        {
            return 0;
        }
        return ((object[])raw).Length;
    }

    private static void WriteReceipt(string receiptPath, Dictionary<string, object> receipt)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(receiptPath));
        string json = new JavaScriptSerializer().Serialize(receipt);
        File.WriteAllText(receiptPath, json, new UTF8Encoding(false));
    }

    private static Dictionary<string, object> SaveCheckpoint(
        ModelDoc2 model,
        string path,
        string label)
    {
        return Step(label, () =>
        {
            if (File.Exists(path))
            {
                throw new InvalidOperationException(
                    "Checkpoint already exists; refusing overwrite: " + path);
            }
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            int errors = 0;
            int warnings = 0;
            bool saved = model.Extension.SaveAs(path, 0, 1, null, ref errors, ref warnings);
            if (!saved || errors != 0 || !File.Exists(path))
            {
                throw new InvalidOperationException(
                    "SaveAs failed saved=" + saved + " errors=" + errors +
                    " warnings=" + warnings + " path=" + path);
            }
            return new Dictionary<string, object>
            {
                {"label", label},
                {"path", path},
                {"bytes", new FileInfo(path).Length},
                {"sha256", "DEFERRED_UNTIL_DOCUMENT_CLOSE"},
                {"save_errors", errors},
                {"save_warnings", warnings}
            };
        });
    }

    private static void FinalizeCheckpointHashes(
        List<Dictionary<string, object>> checkpoints)
    {
        foreach (Dictionary<string, object> checkpoint in checkpoints)
        {
            string path = Convert.ToString(checkpoint["path"]);
            checkpoint["bytes"] = new FileInfo(path).Length;
            checkpoint["sha256"] = Sha256(path);
        }
    }

    private static int RunInternal(
        string targetPath,
        string receiptPath,
        bool stopAfterStageA)
    {
        ProgressPath = Path.Combine(
            Path.GetDirectoryName(receiptPath),
            Path.GetFileNameWithoutExtension(receiptPath) + "_PROGRESS.log");
        Directory.CreateDirectory(Path.GetDirectoryName(ProgressPath));
        File.WriteAllText(
            ProgressPath,
            DateTime.UtcNow.ToString("o") + " | START | B51R1_MASTER_SKELETON_NATIVE_BUILD_V2" +
            System.Environment.NewLine,
            new UTF8Encoding(false));

        var receipt = new Dictionary<string, object>
        {
            {"schema", "SER_B51R1_MASTER_SKELETON_NATIVE_BUILD_V2"},
            {"target", targetPath},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"status", "FAIL_NOT_STARTED"},
            {"progress_log", ProgressPath},
            {"strategy", "STAGE_A_THEN_ONE_COORDINATE_SYSTEM_PER_CHECKPOINT"}
        };

        SldWorks swApp = null;
        ModelDoc2 model = null;
        string title = null;
        try
        {
            if (File.Exists(targetPath))
            {
                throw new InvalidOperationException("Target already exists; refusing overwrite");
            }
            string targetDirectory = Path.GetDirectoryName(targetPath);
            string targetStem = Path.GetFileNameWithoutExtension(targetPath);
            string stageAPath = Path.Combine(
                targetDirectory, targetStem + "_STAGE_A_RECOVERY.SLDPRT");
            string cs01Path = Path.Combine(
                targetDirectory, targetStem + "_STAGE_B_CS01_RECOVERY.SLDPRT");
            string cs02Path = Path.Combine(
                targetDirectory, targetStem + "_STAGE_B_CS02_RECOVERY.SLDPRT");
            string cs03Path = Path.Combine(
                targetDirectory, targetStem + "_STAGE_B_CS03_RECOVERY.SLDPRT");
            foreach (string checkpointPath in new[]
            {
                stageAPath, cs01Path, cs02Path, cs03Path
            })
            {
                if (File.Exists(checkpointPath))
                {
                    throw new InvalidOperationException(
                        "Recovery checkpoint already exists; refusing overwrite: " +
                        checkpointPath);
                }
            }

            string template =
                @"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2024\templates\gb_part.prtdot";
            if (!File.Exists(template))
            {
                throw new FileNotFoundException("Part template not found", template);
            }

            swApp = Step(
                "ATTACH_ACTIVE_SOLIDWORKS",
                () => (SldWorks)Marshal.GetActiveObject("SldWorks.Application"));
            receipt["solidworks_revision"] = swApp.RevisionNumber();
            receipt["visible"] = swApp.Visible;
            receipt["document_count_before"] = swApp.GetDocumentCount();

            model = Step(
                "CREATE_NEW_PART_FROM_GB_TEMPLATE",
                () => (ModelDoc2)swApp.NewDocument(template, 0, 0, 0));
            if (model == null)
            {
                throw new InvalidOperationException("NewDocument returned null");
            }
            title = model.GetTitle();
            receipt["new_document_title"] = title;

            var created = new List<string>();
            var checkpoints = new List<Dictionary<string, object>>();

            string[] right = {"Right Plane", "右视基准面"};
            string[] top = {"Top Plane", "上视基准面"};
            string[] front = {"Front Plane", "前视基准面"};

            AddCreated(
                created,
                "ADD_PLANE_PLN_TASK_FACE_X183",
                () => AddOffsetPlane(model, "PLN_TASK_FACE_X183", right, 0.183, false));
            AddCreated(
                created,
                "ADD_PLANE_PLN_M_DYNAMICS_X185_25",
                () => AddOffsetPlane(
                    model, "PLN_M_DYNAMICS_X185_25", right, 0.18525, false));
            AddCreated(
                created,
                "ADD_PLANE_PLN_M_DISPLAY_X198",
                () => AddOffsetPlane(model, "PLN_M_DISPLAY_X198", right, 0.198, false));

            AddCreated(
                created,
                "ADD_PLANE_PLN_PRIMARY_PY_110_15",
                () => AddOffsetPlane(
                    model, "PLN_PRIMARY_PY_110_15", top, 0.11015, false));
            AddCreated(
                created,
                "ADD_PLANE_PLN_PRIMARY_NY_110_15",
                () => AddOffsetPlane(
                    model, "PLN_PRIMARY_NY_110_15", top, 0.11015, true));
            AddCreated(
                created,
                "ADD_PLANE_PLN_PANEL_OUTER_PY_113_15",
                () => AddOffsetPlane(
                    model, "PLN_PANEL_OUTER_PY_113_15", top, 0.11315, false));
            AddCreated(
                created,
                "ADD_PLANE_PLN_PANEL_OUTER_NY_113_15",
                () => AddOffsetPlane(
                    model, "PLN_PANEL_OUTER_NY_113_15", top, 0.11315, true));

            AddCreated(
                created,
                "ADD_PLANE_PLN_PRIMARY_PZ_110_15",
                () => AddOffsetPlane(
                    model, "PLN_PRIMARY_PZ_110_15", front, 0.11015, false));
            AddCreated(
                created,
                "ADD_PLANE_PLN_PRIMARY_NZ_110_15",
                () => AddOffsetPlane(
                    model, "PLN_PRIMARY_NZ_110_15", front, 0.11015, true));
            AddCreated(
                created,
                "ADD_PLANE_PLN_PANEL_OUTER_PZ_113_15",
                () => AddOffsetPlane(
                    model, "PLN_PANEL_OUTER_PZ_113_15", front, 0.11315, false));
            AddCreated(
                created,
                "ADD_PLANE_PLN_PANEL_OUTER_NZ_113_15",
                () => AddOffsetPlane(
                    model, "PLN_PANEL_OUTER_NZ_113_15", front, 0.11315, true));

            AddCreated(created, "ADD_MOUNT_SKETCH", () => AddMountSketch(model));
            AddCreated(
                created,
                "ADD_AXIS_AX_LONGERON_PY_PZ",
                () => AddLongeronAxis(
                    model,
                    "AX_LONGERON_PY_PZ",
                    "SK3D_AX_LONGERON_PY_PZ_REF",
                    0.10165,
                    0.10165));
            AddCreated(
                created,
                "ADD_AXIS_AX_LONGERON_PY_NZ",
                () => AddLongeronAxis(
                    model,
                    "AX_LONGERON_PY_NZ",
                    "SK3D_AX_LONGERON_PY_NZ_REF",
                    0.10165,
                    -0.10165));
            AddCreated(
                created,
                "ADD_AXIS_AX_LONGERON_NY_PZ",
                () => AddLongeronAxis(
                    model,
                    "AX_LONGERON_NY_PZ",
                    "SK3D_AX_LONGERON_NY_PZ_REF",
                    -0.10165,
                    0.10165));
            AddCreated(
                created,
                "ADD_AXIS_AX_LONGERON_NY_NZ",
                () => AddLongeronAxis(
                    model,
                    "AX_LONGERON_NY_NZ",
                    "SK3D_AX_LONGERON_NY_NZ_REF",
                    -0.10165,
                    -0.10165));

            ConfigurationManager configurationManager = model.ConfigurationManager;
            Step(
                "RENAME_DEFAULT_CONFIGURATION_COMMON_CANONICAL",
                () =>
                {
                    Configuration common = configurationManager.ActiveConfiguration;
                    common.Name = "COMMON_CANONICAL";
                    return true;
                });
            Configuration modeA = Step(
                "ADD_CONFIGURATION_MODE_A_EVALUATION",
                () => configurationManager.AddConfiguration2(
                    "MODE_A_EVALUATION",
                    "H9 12U deployer-compatible evaluation branch; not selected",
                    "",
                    0,
                    "",
                    "",
                    false));
            if (modeA == null)
            {
                throw new InvalidOperationException("Could not create MODE_A_EVALUATION");
            }
            Configuration modeB = Step(
                "ADD_CONFIGURATION_MODE_B_EVALUATION",
                () => configurationManager.AddConfiguration2(
                    "MODE_B_EVALUATION",
                    "H9 external service-bay evaluation branch; not selected",
                    "",
                    0,
                    "",
                    "",
                    false));
            if (modeB == null)
            {
                throw new InvalidOperationException("Could not create MODE_B_EVALUATION");
            }

            Step(
                "ADD_CUSTOM_PROPERTIES",
                () =>
                {
                    CustomPropertyManager properties =
                        model.Extension.get_CustomPropertyManager("");
                    AddProperty(properties, "OBJECT_ID", "B51R1_MASTER_SKELETON_V2");
                    AddProperty(properties, "MODEL_ROLE", "MASTER_SKELETON");
                    AddProperty(properties, "MASS_AUTHORITY", "NONE");
                    AddProperty(properties, "BOM_EXCLUDE", "TRUE");
                    AddProperty(properties, "FRAME_ID", "CS_SPACECRAFT_BODY");
                    AddProperty(
                        properties,
                        "EVIDENCE_STATE",
                        "EVIDENCE_BOUND_SOURCE_BOUND_MEASUREMENT_PASS");
                    AddProperty(properties, "H9_STATUS", "HUMAN_DECISION_REQUIRED");
                    AddProperty(properties, "MODE_A_STATUS", "EVALUATION_NOT_SELECTED");
                    AddProperty(properties, "MODE_B_STATUS", "EVALUATION_NOT_SELECTED");
                    AddProperty(properties, "MEASUREMENT_GATE_SHA256", MeasurementSha);
                    AddProperty(properties, "ACCEPTED_URDF_SHA256", UrdfSha);
                    AddProperty(properties, "MASS_OWNER", "NONE_REFERENCE_ONLY");
                    AddProperty(properties, "MATERIAL", "NONE");
                    AddProperty(properties, "MANUFACTURING_AUTHORITY", "NONE");
                    AddProperty(
                        properties,
                        "CLAIM_LIMIT",
                        "DATUM_INTERFACE_CONTROL_ONLY_NO_MASS_STIFFNESS_ATTACHMENT_FLIGHT_CREDIT");
                    AddProperty(
                        properties,
                        "BUILD_STRATEGY",
                        "STAGE_A_THEN_COORDINATE_SYSTEM_CHECKPOINTS");
                    AddProperty(
                        properties,
                        "G07_G08_CONTACT_WINDOW_STATUS",
                        "SOURCE_BOUND_BBOX_AVAILABLE_NATIVE_SKETCH_PENDING");
                    AddProperty(
                        properties,
                        "KO_SOLAR_SWEEP_STATUS",
                        "NOT_EVALUATED_UNKNOWN_PARAM");
                    AddProperty(
                        properties,
                        "KO_ARM_RELEASE_STATUS",
                        "NOT_EVALUATED_UNKNOWN_PARAM");
                    return true;
                });

            Step("FORCE_REBUILD_STAGE_A", () => model.ForceRebuild3(false));
            int bodyCount = Step("VERIFY_ZERO_SOLID_BODIES_STAGE_A", () => SolidBodyCount(model));
            if (bodyCount != 0)
            {
                throw new InvalidOperationException(
                    "Master Skeleton unexpectedly contains " + bodyCount + " solid bodies");
            }

            checkpoints.Add(
                SaveCheckpoint(model, stageAPath, "SAVE_STAGE_A_RECOVERY_CHECKPOINT"));
            receipt["status"] = "PASS_STAGE_A_CHECKPOINT_COORDINATE_SYSTEMS_PENDING";
            receipt["checkpoints"] = checkpoints;
            WriteReceipt(receiptPath, receipt);
            Trace("RECEIPT | PASS_STAGE_A_CHECKPOINT_COORDINATE_SYSTEMS_PENDING");

            if (stopAfterStageA)
            {
                receipt["status"] =
                    "PASS_NATIVE_MASTER_SKELETON_STAGE_A_BUILT_COORDINATE_SYSTEMS_PENDING";
                receipt["created_contract_features"] = created;
                receipt["features"] = FeatureInventory(model);
                receipt["configurations"] = ConfigurationNames(model);
                receipt["solid_body_count"] = bodyCount;
                receipt["checkpoints"] = checkpoints;
                receipt["claim_limit"] =
                    "STAGE_A_NATIVE_REFERENCE_GEOMETRY_ONLY_COORDINATE_SYSTEMS_KEEP_OUTS_AND_CONTACT_WINDOWS_PENDING";
                Step(
                    "CLOSE_STAGE_A_DOCUMENT",
                    () =>
                    {
                        swApp.CloseDoc(model.GetTitle());
                        return true;
                    });
                model = null;
                FinalizeCheckpointHashes(checkpoints);
                receipt["checkpoints"] = checkpoints;
                WriteReceipt(receiptPath, receipt);
                Trace(
                    "PASS | PASS_NATIVE_MASTER_SKELETON_STAGE_A_BUILT_COORDINATE_SYSTEMS_PENDING");
                Marshal.FinalReleaseComObject(swApp);
                return 0;
            }

            AddCreated(
                created,
                "ADD_COORDINATE_SYSTEM_CS_SPACECRAFT_BODY",
                () => AddCoordinateSystem(
                    model, "CS_SPACECRAFT_BODY", 0, 0, 0, 0, 0, 0));
            checkpoints.Add(
                SaveCheckpoint(model, cs01Path, "SAVE_STAGE_B_CS01_RECOVERY_CHECKPOINT"));
            receipt["status"] = "PASS_STAGE_B_CS01_CHECKPOINT";
            receipt["checkpoints"] = checkpoints;
            WriteReceipt(receiptPath, receipt);

            AddCreated(
                created,
                "ADD_COORDINATE_SYSTEM_CS_B601_BASE_ACCEPTED",
                () => AddCoordinateSystem(
                    model, "CS_B601_BASE_ACCEPTED", 0.18525, 0, 0, 0, 0, 0));
            checkpoints.Add(
                SaveCheckpoint(model, cs02Path, "SAVE_STAGE_B_CS02_RECOVERY_CHECKPOINT"));
            receipt["status"] = "PASS_STAGE_B_CS02_CHECKPOINT";
            receipt["checkpoints"] = checkpoints;
            WriteReceipt(receiptPath, receipt);

            AddCreated(
                created,
                "ADD_COORDINATE_SYSTEM_CS_B601_BASE_DISPLAY_X198",
                () => AddCoordinateSystem(
                    model, "CS_B601_BASE_DISPLAY_X198", 0.198, 0, 0, 0, 0, 0));
            checkpoints.Add(
                SaveCheckpoint(model, cs03Path, "SAVE_STAGE_B_CS03_RECOVERY_CHECKPOINT"));
            receipt["status"] = "PASS_STAGE_B_CS03_CHECKPOINT";
            receipt["checkpoints"] = checkpoints;
            WriteReceipt(receiptPath, receipt);

            AddCreated(
                created,
                "ADD_COORDINATE_SYSTEM_CS_B601_BASE_A0_25DEG_CANDIDATE",
                () => AddCoordinateSystem(
                    model,
                    "CS_B601_BASE_A0_25DEG_CANDIDATE",
                    0.18525,
                    0,
                    0,
                    25.0 * Math.PI / 180.0,
                    0,
                    0));
            checkpoints.Add(SaveCheckpoint(model, targetPath, "SAVE_FINAL_NATIVE_TARGET"));

            receipt["status"] = "PASS_NATIVE_MASTER_SKELETON_BUILT";
            receipt["created_contract_features"] = created;
            receipt["features"] = FeatureInventory(model);
            receipt["configurations"] = ConfigurationNames(model);
            receipt["solid_body_count"] = bodyCount;
            receipt["checkpoints"] = checkpoints;
            receipt["claim_limit"] =
                "NATIVE_DATUM_PART_ONLY_NO_MASS_STIFFNESS_ATTACHMENT_MANUFACTURING_FLIGHT_CREDIT";

            Step(
                "CLOSE_FINAL_NATIVE_DOCUMENT",
                () =>
                {
                    swApp.CloseDoc(model.GetTitle());
                    return true;
                });
            model = null;
            FinalizeCheckpointHashes(checkpoints);
            receipt["checkpoints"] = checkpoints;
            receipt["target_bytes"] = new FileInfo(targetPath).Length;
            receipt["target_sha256"] = Sha256(targetPath);
            WriteReceipt(receiptPath, receipt);
            Trace("PASS | PASS_NATIVE_MASTER_SKELETON_BUILT");
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
            try
            {
                receipt["error_message"] = ex.Message;
            }
            catch
            {
                receipt["error_message"] = "<unavailable>";
            }
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

    [STAThread]
    public static int Run(string targetPath, string receiptPath)
    {
        return RunInternal(targetPath, receiptPath, false);
    }

    [STAThread]
    public static int RunStageAOnly(string targetPath, string receiptPath)
    {
        return RunInternal(targetPath, receiptPath, true);
    }
}
