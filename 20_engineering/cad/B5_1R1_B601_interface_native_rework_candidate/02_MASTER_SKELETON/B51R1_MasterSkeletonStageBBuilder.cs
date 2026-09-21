using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static class B51R1MasterSkeletonStageBBuilder
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
            bool accepted = acceptedTypes.Any(
                value => typeName.IndexOf(
                    value, StringComparison.OrdinalIgnoreCase) >= 0);
            if (!before.Contains(key) && accepted)
            {
                selected = feature;
            }
            feature = (Feature)feature.GetNextFeature();
        }
        return selected;
    }

    private static Feature AddCoordinateSystemFromSketch(
        ModelDoc2 model,
        string coordinateName,
        double originX,
        double originY,
        double originZ,
        double yDirectionY,
        double yDirectionZ)
    {
        SketchManager manager = model.SketchManager;
        var beforeSketch = FeatureKeys(model);
        manager.Insert3DSketch(true);
        SketchPoint origin = manager.CreatePoint(originX, originY, originZ);
        SketchSegment xLine = manager.CreateLine(
            originX,
            originY,
            originZ,
            originX + 0.01,
            originY,
            originZ);
        SketchSegment yLine = manager.CreateLine(
            originX,
            originY,
            originZ,
            originX,
            originY + 0.01 * yDirectionY,
            originZ + 0.01 * yDirectionZ);
        manager.Insert3DSketch(true);
        if (origin == null || xLine == null || yLine == null)
        {
            throw new InvalidOperationException(
                "Could not create coordinate construction entities for " +
                coordinateName);
        }

        Feature sketchFeature = FindNewFeature(
            model,
            beforeSketch,
            "3DProfileFeature",
            "ProfileFeature",
            "Sketch");
        if (sketchFeature == null)
        {
            throw new InvalidOperationException(
                "Could not locate coordinate construction sketch for " +
                coordinateName);
        }
        sketchFeature.Name = "SK3D_CSYS_" + coordinateName + "_CONSTRUCTION";

        object[] xEntities = {xLine};
        object[] yEntities = {yLine};
        model.ClearSelection2(true);
        Feature coordinateFeature = model.FeatureManager.CreateCoordinateSystem(
            origin, xEntities, yEntities, null);
        if (coordinateFeature == null)
        {
            throw new InvalidOperationException(
                "CreateCoordinateSystem returned null for " + coordinateName);
        }
        coordinateFeature.Name = coordinateName;
        return coordinateFeature;
    }

    private static void AddRectangle(
        SketchManager manager,
        double xMin,
        double xMax,
        double yMin,
        double yMax,
        double z)
    {
        if (manager.CreateLine(xMin, yMin, z, xMax, yMin, z) == null ||
            manager.CreateLine(xMax, yMin, z, xMax, yMax, z) == null ||
            manager.CreateLine(xMax, yMax, z, xMin, yMax, z) == null ||
            manager.CreateLine(xMin, yMax, z, xMin, yMin, z) == null)
        {
            throw new InvalidOperationException("Contact-window rectangle failed");
        }
    }

    private static Feature AddContactWindowSketch(
        ModelDoc2 model,
        string name,
        double xMin,
        double xMax)
    {
        SketchManager manager = model.SketchManager;
        var before = FeatureKeys(model);
        manager.Insert3DSketch(true);
        AddRectangle(
            manager, xMin, xMax, -0.11315, -0.09815, 0.11315);
        AddRectangle(
            manager, xMin, xMax, 0.09815, 0.11315, 0.11315);
        manager.Insert3DSketch(true);
        Feature feature = FindNewFeature(
            model, before, "3DProfileFeature", "ProfileFeature", "Sketch");
        if (feature == null)
        {
            throw new InvalidOperationException(
                "Could not locate contact-window sketch " + name);
        }
        feature.Name = name;
        return feature;
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
            int errors = 0;
            int warnings = 0;
            bool saved = model.Extension.SaveAs(
                path, 0, 1, null, ref errors, ref warnings);
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

    private static int SolidBodyCount(ModelDoc2 model)
    {
        PartDoc part = (PartDoc)model;
        object raw = part.GetBodies2(0, true);
        return raw == null ? 0 : ((object[])raw).Length;
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

    private static void WriteReceipt(
        string receiptPath,
        Dictionary<string, object> receipt)
    {
        string json = new JavaScriptSerializer().Serialize(receipt);
        File.WriteAllText(receiptPath, json, new UTF8Encoding(false));
    }

    [STAThread]
    public static int Run(
        string stageAPath,
        string finalPath,
        string receiptPath)
    {
        ProgressPath = Path.Combine(
            Path.GetDirectoryName(receiptPath),
            Path.GetFileNameWithoutExtension(receiptPath) + "_PROGRESS.log");
        File.WriteAllText(
            ProgressPath,
            DateTime.UtcNow.ToString("o") +
            " | START | B51R1_MASTER_SKELETON_STAGE_B_V1" +
            System.Environment.NewLine,
            new UTF8Encoding(false));

        var receipt = new Dictionary<string, object>
        {
            {"schema", "SER_B51R1_MASTER_SKELETON_STAGE_B_BUILD_V1"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"input_stage_a", stageAPath},
            {"target", finalPath},
            {"status", "FAIL_NOT_STARTED"},
            {"progress_log", ProgressPath},
            {"coordinate_system_method", "ENTITY_DRIVEN_CREATE_COORDINATE_SYSTEM"},
            {"numerical_coordinate_system_api_used", false}
        };

        SldWorks swApp = null;
        ModelDoc2 model = null;
        try
        {
            if (!File.Exists(stageAPath))
            {
                throw new FileNotFoundException("Stage A input not found", stageAPath);
            }
            if (File.Exists(finalPath) || File.Exists(receiptPath))
            {
                throw new InvalidOperationException(
                    "Final target or receipt already exists; refusing overwrite");
            }

            string directory = Path.GetDirectoryName(finalPath);
            string stem = Path.GetFileNameWithoutExtension(finalPath);
            string cs01Path = Path.Combine(
                directory, stem + "_STAGE_B_CS01_RECOVERY.SLDPRT");
            string cs02Path = Path.Combine(
                directory, stem + "_STAGE_B_CS02_RECOVERY.SLDPRT");
            string cs03Path = Path.Combine(
                directory, stem + "_STAGE_B_CS03_RECOVERY.SLDPRT");
            string cs04Path = Path.Combine(
                directory, stem + "_STAGE_B_CS04_RECOVERY.SLDPRT");
            foreach (string path in new[] {cs01Path, cs02Path, cs03Path, cs04Path})
            {
                if (File.Exists(path))
                {
                    throw new InvalidOperationException(
                        "Stage B checkpoint already exists; refusing overwrite: " + path);
                }
            }

            swApp = Step(
                "ATTACH_ACTIVE_SOLIDWORKS",
                () => (SldWorks)Marshal.GetActiveObject("SldWorks.Application"));
            receipt["solidworks_revision"] = swApp.RevisionNumber();
            receipt["visible"] = swApp.Visible;
            receipt["document_count_before"] = swApp.GetDocumentCount();
            if (!swApp.Visible || swApp.GetDocumentCount() != 0 || swApp.ActiveDoc != null)
            {
                throw new InvalidOperationException(
                    "Expected an empty visible SolidWorks session before Stage B");
            }

            int openErrors = 0;
            int openWarnings = 0;
            model = Step(
                "OPEN_STAGE_A_READ_WRITE",
                () => (ModelDoc2)swApp.OpenDoc6(
                    stageAPath, 1, 1, "", ref openErrors, ref openWarnings));
            if (model == null || openErrors != 0)
            {
                throw new InvalidOperationException(
                    "Stage A open failed errors=" + openErrors +
                    " warnings=" + openWarnings);
            }
            receipt["open_errors"] = openErrors;
            receipt["open_warnings"] = openWarnings;

            var created = new List<string>();
            var checkpoints = new List<Dictionary<string, object>>();

            Feature feature = Step(
                "ADD_CS_SPACECRAFT_BODY",
                () => AddCoordinateSystemFromSketch(
                    model, "CS_SPACECRAFT_BODY", 0, 0, 0, 1, 0));
            created.Add(feature.Name);
            checkpoints.Add(
                SaveCheckpoint(model, cs01Path, "SAVE_STAGE_B_CS01_CHECKPOINT"));

            feature = Step(
                "ADD_CS_B601_BASE_ACCEPTED",
                () => AddCoordinateSystemFromSketch(
                    model, "CS_B601_BASE_ACCEPTED", 0.18525, 0, 0, 1, 0));
            created.Add(feature.Name);
            checkpoints.Add(
                SaveCheckpoint(model, cs02Path, "SAVE_STAGE_B_CS02_CHECKPOINT"));

            feature = Step(
                "ADD_CS_B601_BASE_DISPLAY_X198",
                () => AddCoordinateSystemFromSketch(
                    model, "CS_B601_BASE_DISPLAY_X198", 0.198, 0, 0, 1, 0));
            created.Add(feature.Name);
            checkpoints.Add(
                SaveCheckpoint(model, cs03Path, "SAVE_STAGE_B_CS03_CHECKPOINT"));

            double angle = 25.0 * Math.PI / 180.0;
            feature = Step(
                "ADD_CS_B601_BASE_A0_25DEG_CANDIDATE",
                () => AddCoordinateSystemFromSketch(
                    model,
                    "CS_B601_BASE_A0_25DEG_CANDIDATE",
                    0.18525,
                    0,
                    0,
                    Math.Cos(angle),
                    Math.Sin(angle)));
            created.Add(feature.Name);
            checkpoints.Add(
                SaveCheckpoint(model, cs04Path, "SAVE_STAGE_B_CS04_CHECKPOINT"));

            feature = Step(
                "ADD_WIN_G07_CONTACT",
                () => AddContactWindowSketch(
                    model, "WIN_G07_CONTACT", 0.010, 0.060));
            created.Add(feature.Name);
            feature = Step(
                "ADD_WIN_G08_CONTACT",
                () => AddContactWindowSketch(
                    model, "WIN_G08_CONTACT", -0.100, -0.040));
            created.Add(feature.Name);

            Step(
                "UPDATE_STAGE_B_PROPERTIES",
                () =>
                {
                    CustomPropertyManager properties =
                        model.Extension.get_CustomPropertyManager("");
                    properties.Add3(
                        "G07_G08_CONTACT_WINDOW_STATUS",
                        30,
                        "SOURCE_BOUND_PANEL_LAYER_FOOTPRINT_NO_PRIMARY_CONTACT_CREDIT",
                        2);
                    properties.Add3(
                        "G07_G08_CONTACT_WINDOW_SOURCE",
                        30,
                        "DURABLE_MEASUREMENT_FINAL_SHA256_94400C1E282A9B35084E68B7A1B53DCC41BF33113D908C7895D0B73C672904FB",
                        2);
                    properties.Add3(
                        "KO_SOLAR_SWEEP_STATUS",
                        30,
                        "NOT_EVALUATED_UNKNOWN_PARAM_NO_GEOMETRY_CREATED",
                        2);
                    properties.Add3(
                        "KO_ARM_RELEASE_STATUS",
                        30,
                        "NOT_EVALUATED_UNKNOWN_PARAM_NO_GEOMETRY_CREATED",
                        2);
                    return true;
                });

            Step("FORCE_REBUILD_STAGE_B", () => model.ForceRebuild3(false));
            int bodyCount = Step("VERIFY_ZERO_SOLID_BODIES_STAGE_B", () =>
                SolidBodyCount(model));
            if (bodyCount != 0)
            {
                throw new InvalidOperationException(
                    "Stage B unexpectedly contains solid bodies: " + bodyCount);
            }
            int externalReferenceCount = model.ListExternalFileReferencesCount2();
            if (externalReferenceCount != 0)
            {
                throw new InvalidOperationException(
                    "Stage B unexpectedly contains external file references: " +
                    externalReferenceCount);
            }

            checkpoints.Add(
                SaveCheckpoint(model, finalPath, "SAVE_FINAL_MASTER_SKELETON_TARGET"));
            receipt["status"] =
                "PASS_NATIVE_MASTER_SKELETON_KNOWN_DATUMS_AND_CONTACT_WINDOWS_BUILT_WITH_KEEP_OUT_HOLDS";
            receipt["created_features"] = created;
            receipt["features"] = FeatureInventory(model);
            receipt["solid_body_count"] = bodyCount;
            receipt["external_file_reference_count"] = externalReferenceCount;
            receipt["checkpoints"] = checkpoints;
            receipt["remaining_holds"] = new[]
            {
                "SOLAR_SWEEP_KEEP_OUT_GEOMETRY_TBD",
                "ARM_RELEASE_KEEP_OUT_GEOMETRY_TBD",
                "TRUE_COLD_PROCESS_REOPEN_NOT_RUN",
                "H9_HUMAN_DECISION_REQUIRED"
            };
            receipt["claim_limit"] =
                "NATIVE_KNOWN_DATUM_AND_PANEL_LAYER_CONTACT_WINDOWS_ONLY_NO_KEEP_OUT_CLEARANCE_LOAD_PATH_H10_T005_MANUFACTURING_OR_FLIGHT_CREDIT";

            Step(
                "CLOSE_FINAL_MASTER_SKELETON",
                () =>
                {
                    swApp.CloseDoc(model.GetTitle());
                    return true;
                });
            model = null;
            FinalizeCheckpointHashes(checkpoints);
            receipt["checkpoints"] = checkpoints;
            receipt["target_bytes"] = new FileInfo(finalPath).Length;
            receipt["target_sha256"] = Sha256(finalPath);
            receipt["document_count_final"] = swApp.GetDocumentCount();
            WriteReceipt(receiptPath, receipt);
            Trace(
                "PASS | PASS_NATIVE_MASTER_SKELETON_KNOWN_DATUMS_AND_CONTACT_WINDOWS_BUILT_WITH_KEEP_OUT_HOLDS");
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
