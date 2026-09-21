using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading;
using B51R1.NativeCadDiagnostics;

internal static class B51R1BlankSingleCsDiagnosticRunner
{
    private const string AuthorizationToken =
        "--authorized-visible-single-cs-once";
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
            "\"schema\":\"SER_B51R1_SINGLE_CS_DIAGNOSTIC_WATCHDOG_V1\"," +
            "\"generated_at_utc\":\"" +
            JsonEscape(DateTime.UtcNow.ToString("o")) + "\"," +
            "\"status\":\"FAIL_CLOSED_WORKER_TIMEOUT\"," +
            "\"timeout_milliseconds\":" +
            WatchdogTimeoutMilliseconds + "," +
            "\"solidworks_process_termination_permitted\":false," +
            "\"runner_self_termination_only\":true," +
            "\"receipt_path\":\"" + JsonEscape(receipt) + "\"," +
            "\"progress_log\":\"" + JsonEscape(progress) + "\"," +
            "\"claim_limit\":\"NO_SINGLE_CS_PASS_CREDIT\"" +
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
                "NOT RUN. The exact one-time authorization token is required.");
            Console.Error.WriteLine(
                "The user must first visibly start exactly one empty, responsive " +
                "SolidWorks 2024 SP5 session.");
            Console.Error.WriteLine(
                "Invoke this attach-only runner with: " +
                Path.GetFileName(
                    Process.GetCurrentProcess().MainModule.FileName) +
                " " + AuthorizationToken);
            Console.Error.WriteLine(
                "This runner never launches or force-terminates SolidWorks.");
            return 64;
        }

        string diagnosticDirectory = Path.GetFullPath(
            AppDomain.CurrentDomain.BaseDirectory);
        string candidateRoot = Path.GetFullPath(
            Path.Combine(diagnosticDirectory, "..", ".."));
        string target = Path.Combine(
            diagnosticDirectory,
            "B51R1_SINGLE_CS_DIAGNOSTIC_COPY.SLDPRT");
        string receipt = Path.Combine(
            candidateRoot,
            "07_VERIFICATION",
            "B51R1_SINGLE_CS_DIAGNOSTIC_FIRST_LAUNCH_RECEIPT.json");
        string progress = Path.Combine(
            candidateRoot,
            "08_REVIEWS",
            "B51R1_SINGLE_CS_DIAGNOSTIC_FIRST_LAUNCH_PROGRESS.log");
        string watchdog = Path.Combine(
            candidateRoot,
            "07_VERIFICATION",
            "B51R1_SINGLE_CS_DIAGNOSTIC_WATCHDOG_FAIL_CLOSED.json");
        string transform = Path.Combine(
            candidateRoot,
            "07_VERIFICATION",
            "B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM_FIRST_LAUNCH.json");

        if (File.Exists(target) ||
            File.Exists(receipt) ||
            File.Exists(progress) ||
            File.Exists(watchdog) ||
            File.Exists(transform))
        {
            Console.Error.WriteLine(
                "NOT RUN. A fixed diagnostic output already exists; overwrite refused.");
            return 65;
        }

        Console.WriteLine("ATTACH_ONLY_BLANK_SINGLE_CS_DIAGNOSTIC");
        Console.WriteLine("Candidate root: " + candidateRoot);
        Console.WriteLine("Target: " + target);
        Console.WriteLine("Receipt: " + receipt);
        Console.WriteLine("Progress: " + progress);
        Console.WriteLine("Transform evidence: " + transform);

        int workerExitCode = 2;
        Exception workerException = null;
        Thread worker = new Thread(
            new ThreadStart(
            delegate
            {
                try
                {
                    workerExitCode = BlankSingleCsDiagnostic.Run(
                        candidateRoot,
                        target,
                        receipt,
                        progress,
                        transform);
                }
                catch (Exception ex)
                {
                    workerException = ex;
                    workerExitCode = 2;
                }
            }));
        worker.Name = "B51R1_BlankSingleCs_STA_Worker";
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
                    Environment.NewLine,
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
                "FAIL_CLOSED_WORKER_TIMEOUT. The runner terminates itself only; " +
                "it does not terminate SolidWorks.");
            Environment.Exit(124);
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
                ? "PASS_FIRST_LAUNCH_COLD_REOPEN_PENDING"
                : "FAIL_CLOSED_SEE_RECEIPT_AND_PROGRESS");
        return workerExitCode;
    }
}
