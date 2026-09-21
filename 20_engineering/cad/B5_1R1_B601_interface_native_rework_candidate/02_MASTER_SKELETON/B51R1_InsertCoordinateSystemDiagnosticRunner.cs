using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading;
using B51R1.NativeCadDiagnostics;

internal static class B51R1InsertCoordinateSystemDiagnosticRunner
{
    private const string AuthorizationToken = "--authorized-attach-only";
    private const int WatchdogTimeoutMilliseconds = 120000;
    private const string InteropPath =
        @"F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll";

    private static Assembly ResolveSolidWorksInterop(
        object sender,
        ResolveEventArgs args)
    {
        AssemblyName requested = new AssemblyName(args.Name);
        if (String.Equals(
            requested.Name,
            "SolidWorks.Interop.sldworks",
            StringComparison.OrdinalIgnoreCase) &&
            File.Exists(InteropPath))
        {
            return Assembly.LoadFrom(InteropPath);
        }
        return null;
    }

    private static string JsonEscape(string value)
    {
        if (value == null)
        {
            return "";
        }
        return value
            .Replace("\\", "\\\\")
            .Replace("\"", "\\\"")
            .Replace("\r", "\\r")
            .Replace("\n", "\\n");
    }

    private static void WriteWatchdogFailClosed(
        string watchdogPath,
        string receipt,
        string progress)
    {
        string json =
            "{" +
            "\"schema\":\"SER_B51R1_INSERT_COORDINATE_SYSTEM_WATCHDOG_V1\"," +
            "\"generated_at_utc\":\"" +
            JsonEscape(DateTime.UtcNow.ToString("o")) + "\"," +
            "\"status\":\"FAIL_CLOSED_WORKER_TIMEOUT\"," +
            "\"timeout_milliseconds\":" +
            WatchdogTimeoutMilliseconds + "," +
            "\"solidworks_process_termination_permitted\":false," +
            "\"runner_self_termination_only\":true," +
            "\"receipt_path\":\"" + JsonEscape(receipt) + "\"," +
            "\"progress_log\":\"" + JsonEscape(progress) + "\"," +
            "\"claim_limit\":\"NO_CAD_PASS_CREDIT\"" +
            "}";
        using (FileStream stream = new FileStream(
            watchdogPath,
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

    [STAThread]
    private static int Main(string[] args)
    {
        AppDomain.CurrentDomain.AssemblyResolve += ResolveSolidWorksInterop;

        if (args.Length != 1 ||
            !String.Equals(
                args[0],
                AuthorizationToken,
                StringComparison.Ordinal))
        {
            Console.Error.WriteLine(
                "NOT RUN. Fresh explicit visible-launch authorization is required.");
            Console.Error.WriteLine(
                "After the user manually starts exactly one empty, responsive " +
                "SolidWorks 2024 SP5 session, invoke with:");
            Console.Error.WriteLine(
                Path.GetFileName(
                    Process.GetCurrentProcess().MainModule.FileName) +
                " " + AuthorizationToken);
            Console.Error.WriteLine(
                "This runner attaches only; it never starts SolidWorks.");
            return 64;
        }

        string baseDirectory = Path.GetFullPath(
            AppDomain.CurrentDomain.BaseDirectory);
        string source = Path.Combine(
            baseDirectory,
            "B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT");
        string runId =
            DateTime.UtcNow.ToString("yyyyMMddTHHmmssfffZ") +
            "_P" + Process.GetCurrentProcess().Id;
        string disposable = Path.Combine(
            baseDirectory,
            "B51R1_MASTER_SKELETON_V2_INSERT_CSYS_DIAGNOSTIC_COPY_" +
            runId + ".SLDPRT");
        string receipt = Path.Combine(
            baseDirectory,
            "B51R1_INSERT_COORDINATE_SYSTEM_DIAGNOSTIC_" +
            runId + ".json");
        string progress = Path.Combine(
            baseDirectory,
            "B51R1_INSERT_COORDINATE_SYSTEM_DIAGNOSTIC_" +
            runId + "_PROGRESS.log");
        string watchdog = Path.Combine(
            baseDirectory,
            "B51R1_INSERT_COORDINATE_SYSTEM_DIAGNOSTIC_" +
            runId + "_WATCHDOG_FAIL_CLOSED.json");

        Console.WriteLine("ATTACH_ONLY_DIAGNOSTIC");
        Console.WriteLine("Protected Stage A: " + source);
        Console.WriteLine("Disposable copy: " + disposable);
        Console.WriteLine("Receipt: " + receipt);
        Console.WriteLine("Progress: " + progress);

        int workerExitCode = 2;
        Exception workerException = null;
        Thread worker = new Thread(
            new ThreadStart(
            delegate
            {
                try
                {
                    workerExitCode =
                        InsertCoordinateSystemSingleDiagnostic.Run(
                            source,
                            disposable,
                            receipt,
                            progress);
                }
                catch (Exception ex)
                {
                    workerException = ex;
                    workerExitCode = 2;
                }
            }));
        worker.Name = "B51R1_InsertCoordinateSystem_STA_Worker";
        worker.IsBackground = true;
        worker.SetApartmentState(ApartmentState.STA);
        worker.Start();

        if (!worker.Join(WatchdogTimeoutMilliseconds))
        {
            try
            {
                File.AppendAllText(
                    progress,
                    DateTime.UtcNow.ToString("o") +
                    " | FAIL_CLOSED_WATCHDOG | WORKER_TIMEOUT_" +
                    WatchdogTimeoutMilliseconds + "_MS" +
                    System.Environment.NewLine,
                    new UTF8Encoding(false));
                WriteWatchdogFailClosed(
                    watchdog,
                    receipt,
                    progress);
            }
            catch (Exception watchdogException)
            {
                Console.Error.WriteLine(
                    "FAIL_CLOSED_WATCHDOG_EVIDENCE_ERROR | " +
                    watchdogException.GetType().FullName +
                    " | " + watchdogException.Message);
            }
            Console.Error.WriteLine(
                "FAIL_CLOSED_WORKER_TIMEOUT. The runner will terminate itself; " +
                "it will not terminate SolidWorks.");
            System.Environment.Exit(124);
            return 124;
        }

        if (workerException != null)
        {
            Console.Error.WriteLine(
                "FAIL_CLOSED_RUNNER | " +
                workerException.GetType().FullName +
                " | " + workerException.Message);
            return 2;
        }

        Console.WriteLine(
            workerExitCode == 0
                ? "PASS_SINGLE_DISPOSABLE_COPY_DIAGNOSTIC"
                : "FAIL_CLOSED_SEE_RECEIPT_AND_PROGRESS");
        return workerExitCode;
    }
}
