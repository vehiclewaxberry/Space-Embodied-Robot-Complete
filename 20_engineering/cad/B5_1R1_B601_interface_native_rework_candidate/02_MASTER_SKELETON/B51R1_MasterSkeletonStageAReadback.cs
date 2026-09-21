using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static class B51R1MasterSkeletonStageAReadback
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

    private static string Sha256(string path)
    {
        using (var stream = File.OpenRead(path))
        using (var sha = SHA256.Create())
        {
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "");
        }
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
        return raw == null ? 0 : ((object[])raw).Length;
    }

    private static Dictionary<string, string> PropertyReadback(ModelDoc2 model)
    {
        string[] names =
        {
            "OBJECT_ID",
            "MODEL_ROLE",
            "MASS_AUTHORITY",
            "BOM_EXCLUDE",
            "FRAME_ID",
            "H9_STATUS",
            "MODE_A_STATUS",
            "MODE_B_STATUS",
            "MEASUREMENT_GATE_SHA256",
            "ACCEPTED_URDF_SHA256",
            "KO_SOLAR_SWEEP_STATUS",
            "KO_ARM_RELEASE_STATUS",
            "G07_G08_CONTACT_WINDOW_STATUS"
        };
        CustomPropertyManager manager = model.Extension.get_CustomPropertyManager("");
        return names.ToDictionary(name => name, name => manager.Get(name));
    }

    private static void WriteReceipt(
        string receiptPath,
        Dictionary<string, object> receipt)
    {
        string json = new JavaScriptSerializer().Serialize(receipt);
        File.WriteAllText(receiptPath, json, new UTF8Encoding(false));
    }

    [STAThread]
    public static int Run(string partPath, string receiptPath)
    {
        ProgressPath = Path.Combine(
            Path.GetDirectoryName(receiptPath),
            Path.GetFileNameWithoutExtension(receiptPath) + "_PROGRESS.log");
        File.WriteAllText(
            ProgressPath,
            DateTime.UtcNow.ToString("o") +
            " | START | B51R1_MASTER_SKELETON_STAGE_A_READBACK_V1" +
            System.Environment.NewLine,
            new UTF8Encoding(false));

        var receipt = new Dictionary<string, object>
        {
            {"schema", "SER_B51R1_MASTER_SKELETON_STAGE_A_READBACK_V1"},
            {"generated_at_utc", DateTime.UtcNow.ToString("o")},
            {"part", partPath},
            {"status", "FAIL_NOT_STARTED"},
            {"reopen_mode", "SAME_VISIBLE_SESSION_READ_ONLY_REOPEN"},
            {"progress_log", ProgressPath}
        };

        SldWorks swApp = null;
        ModelDoc2 model = null;
        try
        {
            if (!File.Exists(partPath))
            {
                throw new FileNotFoundException("Stage A part not found", partPath);
            }
            if (File.Exists(receiptPath))
            {
                throw new InvalidOperationException(
                    "Receipt already exists; refusing overwrite: " + receiptPath);
            }

            Trace("BEGIN | ATTACH_ACTIVE_SOLIDWORKS");
            swApp = (SldWorks)Marshal.GetActiveObject("SldWorks.Application");
            Trace("END | ATTACH_ACTIVE_SOLIDWORKS");
            receipt["solidworks_revision"] = swApp.RevisionNumber();
            receipt["visible"] = swApp.Visible;
            receipt["document_count_before"] = swApp.GetDocumentCount();
            if (!swApp.Visible || swApp.GetDocumentCount() != 0 || swApp.ActiveDoc != null)
            {
                throw new InvalidOperationException(
                    "Expected an empty visible SolidWorks session before readback");
            }

            int openErrors = 0;
            int openWarnings = 0;
            Trace("BEGIN | OPEN_STAGE_A_READ_ONLY");
            model = (ModelDoc2)swApp.OpenDoc6(
                partPath, 1, 3, "", ref openErrors, ref openWarnings);
            Trace("END | OPEN_STAGE_A_READ_ONLY");
            if (model == null || openErrors != 0)
            {
                throw new InvalidOperationException(
                    "Stage A reopen failed errors=" + openErrors +
                    " warnings=" + openWarnings);
            }
            receipt["open_errors"] = openErrors;
            receipt["open_warnings"] = openWarnings;
            receipt["opened_path"] = model.GetPathName();

            var inventory = FeatureInventory(model);
            var featureNames = new HashSet<string>(
                inventory.Select(item => Convert.ToString(item["name"])),
                StringComparer.OrdinalIgnoreCase);
            string[] expectedFeatures =
            {
                "PLN_TASK_FACE_X183",
                "PLN_M_DYNAMICS_X185_25",
                "PLN_M_DISPLAY_X198",
                "PLN_PRIMARY_PY_110_15",
                "PLN_PRIMARY_NY_110_15",
                "PLN_PANEL_OUTER_PY_113_15",
                "PLN_PANEL_OUTER_NY_113_15",
                "PLN_PRIMARY_PZ_110_15",
                "PLN_PRIMARY_NZ_110_15",
                "PLN_PANEL_OUTER_PZ_113_15",
                "PLN_PANEL_OUTER_NZ_113_15",
                "SK_IF_B601_MOUNT_160_SQUARE_KO_D100",
                "AX_LONGERON_PY_PZ",
                "AX_LONGERON_PY_NZ",
                "AX_LONGERON_NY_PZ",
                "AX_LONGERON_NY_NZ"
            };
            var missingFeatures =
                expectedFeatures.Where(name => !featureNames.Contains(name)).ToList();

            var configurations = ConfigurationNames(model);
            string[] expectedConfigurations =
            {
                "COMMON_CANONICAL",
                "MODE_A_EVALUATION",
                "MODE_B_EVALUATION"
            };
            var missingConfigurations = expectedConfigurations
                .Where(name => !configurations.Contains(
                    name, StringComparer.OrdinalIgnoreCase))
                .ToList();

            var properties = PropertyReadback(model);
            var propertyFailures = new List<string>();
            if (properties["MODEL_ROLE"] != "MASTER_SKELETON")
            {
                propertyFailures.Add("MODEL_ROLE");
            }
            if (properties["MASS_AUTHORITY"] != "NONE")
            {
                propertyFailures.Add("MASS_AUTHORITY");
            }
            if (properties["BOM_EXCLUDE"] != "TRUE")
            {
                propertyFailures.Add("BOM_EXCLUDE");
            }
            if (properties["H9_STATUS"] != "HUMAN_DECISION_REQUIRED")
            {
                propertyFailures.Add("H9_STATUS");
            }

            int bodyCount = SolidBodyCount(model);
            int externalReferenceCount = model.ListExternalFileReferencesCount2();
            receipt["features"] = inventory;
            receipt["expected_feature_count"] = expectedFeatures.Length;
            receipt["missing_features"] = missingFeatures;
            receipt["configurations"] = configurations;
            receipt["missing_configurations"] = missingConfigurations;
            receipt["properties"] = properties;
            receipt["property_failures"] = propertyFailures;
            receipt["solid_body_count"] = bodyCount;
            receipt["external_file_reference_count"] = externalReferenceCount;

            Trace("BEGIN | CLOSE_STAGE_A_READBACK");
            swApp.CloseDoc(model.GetTitle());
            model = null;
            Trace("END | CLOSE_STAGE_A_READBACK");
            receipt["document_count_final"] = swApp.GetDocumentCount();
            receipt["part_bytes"] = new FileInfo(partPath).Length;
            receipt["part_sha256"] = Sha256(partPath);

            if (missingFeatures.Count != 0 ||
                missingConfigurations.Count != 0 ||
                propertyFailures.Count != 0 ||
                bodyCount != 0 ||
                externalReferenceCount != 0 ||
                swApp.GetDocumentCount() != 0)
            {
                throw new InvalidOperationException(
                    "Stage A readback contract failed; inspect receipt fields");
            }

            receipt["status"] =
                "PASS_STAGE_A_NATIVE_REFERENCE_GEOMETRY_SAME_SESSION_REOPEN";
            receipt["remaining_holds"] = new[]
            {
                "FORMAL_COORDINATE_SYSTEMS_PENDING",
                "G07_G08_CONTACT_WINDOW_SKETCHES_PENDING",
                "SOLAR_SWEEP_KEEP_OUT_GEOMETRY_TBD",
                "ARM_RELEASE_KEEP_OUT_GEOMETRY_TBD",
                "TRUE_COLD_PROCESS_REOPEN_NOT_RUN"
            };
            receipt["claim_limit"] =
                "STAGE_A_NATIVE_REFERENCE_GEOMETRY_ONLY_NO_FINAL_MASTER_SKELETON_CARRIER_H10_OR_T005_CREDIT";
            WriteReceipt(receiptPath, receipt);
            Trace("PASS | PASS_STAGE_A_NATIVE_REFERENCE_GEOMETRY_SAME_SESSION_REOPEN");
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
