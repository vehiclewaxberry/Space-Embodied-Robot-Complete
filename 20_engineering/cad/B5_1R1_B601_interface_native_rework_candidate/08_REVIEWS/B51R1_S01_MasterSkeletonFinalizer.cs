using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static class B51R1S01MasterSkeletonFinalizer
{
    private static string Sha256(string path)
    {
        using (var stream = File.OpenRead(path))
        using (var digest = SHA256.Create())
        {
            return BitConverter.ToString(digest.ComputeHash(stream)).Replace("-", "");
        }
    }

    private static void WriteJson(string path, Dictionary<string, object> data)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path, new JavaScriptSerializer().Serialize(data), new UTF8Encoding(false));
    }

    private static List<Dictionary<string, object>> Inventory(ModelDoc2 model)
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

    private static Feature FindFeature(ModelDoc2 model, string name)
    {
        Feature feature = (Feature)model.FirstFeature();
        while (feature != null)
        {
            if (String.Equals(feature.Name, name, StringComparison.OrdinalIgnoreCase))
            {
                return feature;
            }
            feature = (Feature)feature.GetNextFeature();
        }
        return null;
    }

    private static void RenameRequired(ModelDoc2 model, string oldName, string newName)
    {
        if (FindFeature(model, newName) != null)
        {
            throw new InvalidOperationException("Target feature name already exists: " + newName);
        }
        Feature feature = FindFeature(model, oldName);
        if (feature == null)
        {
            throw new InvalidOperationException("Required source feature missing: " + oldName);
        }
        feature.Name = newName;
        if (FindFeature(model, newName) == null || FindFeature(model, oldName) != null)
        {
            throw new InvalidOperationException("Feature rename did not persist: " + oldName + " -> " + newName);
        }
    }

    private static Feature AddFootprintWindows(ModelDoc2 model)
    {
        const string sketchName = "SK_G07_G08_PANEL_FOOTPRINT_WINDOWS";
        if (FindFeature(model, sketchName) != null)
        {
            throw new InvalidOperationException("Footprint sketch already exists; refusing ambiguous rerun");
        }
        model.ClearSelection2(true);
        if (!model.Extension.SelectByID2(
                "PLN_PANEL_OUTER_PZ_Z113_15", "PLANE", 0, 0, 0, false, 0, null, 0))
        {
            throw new InvalidOperationException("Could not select panel footprint plane");
        }
        var before = new HashSet<string>(
            Inventory(model).Select(row => Convert.ToString(row["name"])),
            StringComparer.OrdinalIgnoreCase);
        SketchManager sketches = model.SketchManager;
        sketches.InsertSketch(true);
        object a = sketches.CreateCenterRectangle(0.035, -0.10565, 0, 0.060, -0.09815, 0);
        object b = sketches.CreateCenterRectangle(0.035, 0.10565, 0, 0.060, 0.11315, 0);
        object c = sketches.CreateCenterRectangle(-0.070, -0.10565, 0, -0.040, -0.09815, 0);
        object d = sketches.CreateCenterRectangle(-0.070, 0.10565, 0, -0.040, 0.11315, 0);
        if (a == null || b == null || c == null || d == null)
        {
            throw new InvalidOperationException("One or more source-bound footprint rectangles failed");
        }
        sketches.InsertSketch(true);
        model.ClearSelection2(true);
        Feature created = null;
        Feature feature = (Feature)model.FirstFeature();
        while (feature != null)
        {
            if (!before.Contains(feature.Name) &&
                feature.GetTypeName2().IndexOf("Profile", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                created = feature;
            }
            feature = (Feature)feature.GetNextFeature();
        }
        if (created == null)
        {
            throw new InvalidOperationException("Could not locate footprint-window sketch feature");
        }
        created.Name = sketchName;
        return created;
    }

    private static int SolidBodyCount(ModelDoc2 model)
    {
        object raw = ((PartDoc)model).GetBodies2(0, true);
        return raw == null ? 0 : ((object[])raw).Length;
    }

    [STAThread]
    public static int Run(
        string workPath,
        string finalPath,
        string receiptPath,
        string g1bPath,
        string expectedG1bSha,
        string finalLockPath,
        string expectedFinalLockSha,
        string protectedStageAPath,
        string expectedStageASha)
    {
        var receipt = new Dictionary<string, object>
        {
            {"schema", "B51R1_S01_GATE_RECEIPT_V1"},
            {"session_id", "S01"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"status", "FAIL_CLOSED_NOT_STARTED"},
            {"work_path", workPath},
            {"final_path", finalPath}
        };
        SldWorks app = null;
        ModelDoc2 model = null;
        try
        {
            foreach (string required in new[] {workPath, g1bPath, finalLockPath, protectedStageAPath})
            {
                if (!File.Exists(required)) throw new FileNotFoundException("Required input absent", required);
            }
            if (File.Exists(finalPath)) throw new InvalidOperationException("Final target exists; refusing overwrite");
            if (Sha256(g1bPath) != expectedG1bSha) throw new InvalidOperationException("G1B hash mismatch");
            if (Sha256(finalLockPath) != expectedFinalLockSha) throw new InvalidOperationException("Final lock hash mismatch");
            if (Sha256(protectedStageAPath) != expectedStageASha) throw new InvalidOperationException("Protected Stage A hash mismatch before S01 finalization");

            app = (SldWorks)Marshal.GetActiveObject("SldWorks.Application");
            if (!app.Visible) throw new InvalidOperationException("Authorized SolidWorks session is not visible");
            int errors = 0;
            int warnings = 0;
            model = (ModelDoc2)app.OpenDoc6(workPath, 1, 1, "", ref errors, ref warnings);
            if (model == null || errors != 0) throw new InvalidOperationException("Could not open isolated work part: errors=" + errors);

            var renameMap = new Dictionary<string, string>
            {
                {"CS_SPACECRAFT_BODY", "CS_S"},
                {"CS_B601_BASE_ACCEPTED", "CS_M_DYNAMICS_X185_25"},
                {"CS_B601_BASE_DISPLAY_X198", "CS_M_DISPLAY_X198"},
                {"CS_B601_BASE_A0_25DEG_CANDIDATE", "CS_A0_CLOCKED_25_DEG"},
                {"PLN_PRIMARY_PY_110_15", "PLN_PRIMARY_PY_Y110_15"},
                {"PLN_PRIMARY_NY_110_15", "PLN_PRIMARY_NY_YN110_15"},
                {"PLN_PRIMARY_PZ_110_15", "PLN_PRIMARY_PZ_Z110_15"},
                {"PLN_PRIMARY_NZ_110_15", "PLN_PRIMARY_NZ_ZN110_15"},
                {"PLN_PANEL_OUTER_PY_113_15", "PLN_PANEL_OUTER_PY_Y113_15"},
                {"PLN_PANEL_OUTER_NY_113_15", "PLN_PANEL_OUTER_NY_YN113_15"},
                {"PLN_PANEL_OUTER_PZ_113_15", "PLN_PANEL_OUTER_PZ_Z113_15"},
                {"PLN_PANEL_OUTER_NZ_113_15", "PLN_PANEL_OUTER_NZ_ZN113_15"}
            };
            foreach (var pair in renameMap) RenameRequired(model, pair.Key, pair.Value);
            AddFootprintWindows(model);

            CustomPropertyManager props = model.Extension.get_CustomPropertyManager("");
            props.Set2("FRAME_ID", "CS_S");
            props.Set2("BUILD_STRATEGY", "ISOLATED_WORK_PART_THEN_FINAL_SAVEAS");
            props.Set2("G07_G08_CONTACT_WINDOW_STATUS", "NATIVE_SOURCE_BOUND_PANEL_FOOTPRINT_ONLY_NO_CONTACT_CREDIT");
            props.Set2("G1B_RECEIPT_SHA256", expectedG1bSha);
            props.Set2("FINAL_INPUT_LOCK_SHA256", expectedFinalLockSha);
            props.Set2("PANEL_PRIMARY_LOAD_CREDIT", "NONE");
            props.Set2("PANEL_ATTACHMENT_CREDIT", "NONE");
            props.Set2("PANEL_PHYSICAL_CONTACT_CREDIT", "NONE");

            model.ForceRebuild3(false);
            var inventory = Inventory(model);
            var names = new HashSet<string>(inventory.Select(row => Convert.ToString(row["name"])), StringComparer.OrdinalIgnoreCase);
            string[] expectedFeatures =
            {
                "PLN_TASK_FACE_X183", "PLN_M_DYNAMICS_X185_25", "PLN_M_DISPLAY_X198",
                "PLN_PRIMARY_PY_Y110_15", "PLN_PRIMARY_NY_YN110_15",
                "PLN_PRIMARY_PZ_Z110_15", "PLN_PRIMARY_NZ_ZN110_15",
                "PLN_PANEL_OUTER_PY_Y113_15", "PLN_PANEL_OUTER_NY_YN113_15",
                "PLN_PANEL_OUTER_PZ_Z113_15", "PLN_PANEL_OUTER_NZ_ZN113_15",
                "SK_IF_B601_MOUNT_160_SQUARE_KO_D100", "SK_G07_G08_PANEL_FOOTPRINT_WINDOWS",
                "AX_LONGERON_PY_PZ", "AX_LONGERON_PY_NZ", "AX_LONGERON_NY_PZ", "AX_LONGERON_NY_NZ",
                "CS_S", "CS_M_DYNAMICS_X185_25", "CS_M_DISPLAY_X198", "CS_A0_CLOCKED_25_DEG"
            };
            var missing = expectedFeatures.Where(name => !names.Contains(name)).ToList();
            var configurations = ((object[])model.GetConfigurationNames()).Select(value => Convert.ToString(value)).ToList();
            string[] expectedConfigurations = {"COMMON_CANONICAL", "MODE_A_EVALUATION", "MODE_B_EVALUATION"};
            var missingConfigurations = expectedConfigurations.Where(name => !configurations.Contains(name, StringComparer.OrdinalIgnoreCase)).ToList();
            int bodies = SolidBodyCount(model);
            int external = model.ListExternalFileReferencesCount2();
            if (missing.Count != 0 || missingConfigurations.Count != 0 || bodies != 0 || external != 0)
            {
                throw new InvalidOperationException("Final skeleton contract failed before save");
            }
            errors = 0;
            warnings = 0;
            bool saved = model.Extension.SaveAs(finalPath, 0, 1, null, ref errors, ref warnings);
            if (!saved || errors != 0 || !File.Exists(finalPath))
            {
                throw new InvalidOperationException("Final SaveAs failed: saved=" + saved + " errors=" + errors + " warnings=" + warnings);
            }
            string title = model.GetTitle();
            app.CloseDoc(title);
            model = null;
            if (Sha256(protectedStageAPath) != expectedStageASha) throw new InvalidOperationException("Protected Stage A changed during S01");

            receipt["status"] = "S01_PASS_NATIVE_MASTER_SKELETON_CREATED";
            receipt["solidworks_revision"] = app.RevisionNumber();
            receipt["visible"] = app.Visible;
            receipt["g1b_sha256"] = expectedG1bSha;
            receipt["input_lock_sha256"] = expectedFinalLockSha;
            receipt["protected_stage_a_sha256"] = expectedStageASha;
            receipt["work_bytes"] = new FileInfo(workPath).Length;
            receipt["work_sha256"] = Sha256(workPath);
            receipt["target_bytes"] = new FileInfo(finalPath).Length;
            receipt["target_sha256"] = Sha256(finalPath);
            receipt["features"] = inventory;
            receipt["required_feature_count"] = expectedFeatures.Length;
            receipt["missing_features"] = missing;
            receipt["configurations"] = configurations;
            receipt["missing_configurations"] = missingConfigurations;
            receipt["solid_body_count"] = bodies;
            receipt["external_file_reference_count"] = external;
            receipt["normal_document_close"] = true;
            receipt["claim_limit"] = "NATIVE_DATUM_SKELETON_CANDIDATE_ONLY_S02_COLD_REOPEN_REQUIRED";
            WriteJson(receiptPath, receipt);
            Marshal.FinalReleaseComObject(app);
            return 0;
        }
        catch (Exception ex)
        {
            receipt["status"] = "S01_FAIL_CLOSED";
            receipt["error_type"] = ex.GetType().FullName;
            receipt["error_message"] = ex.Message;
            receipt["error_hresult"] = "0x" + ex.HResult.ToString("X8");
            try
            {
                if (app != null && model != null) app.CloseDoc(model.GetTitle());
            }
            catch { }
            WriteJson(receiptPath, receipt);
            if (app != null) try { Marshal.FinalReleaseComObject(app); } catch { }
            return 1;
        }
    }
}
