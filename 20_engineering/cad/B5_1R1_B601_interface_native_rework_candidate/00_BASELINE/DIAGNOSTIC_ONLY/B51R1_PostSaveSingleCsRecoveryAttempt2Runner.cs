using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Threading;

internal static class B51R1PostSaveSingleCsRecoveryAttempt2Runner
{
    private const string AuthorizationToken =
        "--authorized-attach-pid-3308-postsave-recovery-attempt2";
    private const int WatchdogMilliseconds = 90000;
    private const string InteropPath =
        @"F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll";

    private static Assembly ResolveAssembly(object sender, ResolveEventArgs args)
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

    [STAThread]
    private static int Main(string[] args)
    {
        if (args.Length != 1 ||
            !String.Equals(
                args[0],
                AuthorizationToken,
                StringComparison.Ordinal))
        {
            Console.Error.WriteLine(
                "NOT RUN. Exact Attempt 2 authorization token required.");
            Console.Error.WriteLine(
                Path.GetFileName(
                    Process.GetCurrentProcess().MainModule.FileName) +
                " " + AuthorizationToken);
            return 64;
        }

        AppDomain.CurrentDomain.AssemblyResolve += ResolveAssembly;
        string directory = Path.GetFullPath(
            AppDomain.CurrentDomain.BaseDirectory);
        string corePath = Path.Combine(
            directory,
            "B51R1_PostSaveSingleCsRecoveryAttempt2.Core.dll");
        if (!File.Exists(corePath))
        {
            Console.Error.WriteLine(
                "FAIL_CLOSED. Strong-typed Attempt 2 core is missing.");
            return 66;
        }

        int workerCode = 2;
        Exception workerError = null;
        Thread worker = new Thread(
            delegate()
            {
                try
                {
                    Assembly core = Assembly.LoadFrom(corePath);
                    Type type = core.GetType(
                        "B51R1.NativeCadDiagnostics.PostSaveSingleCsRecoveryAttempt2",
                        true);
                    MethodInfo run = type.GetMethod(
                        "Run",
                        BindingFlags.Public | BindingFlags.Static);
                    workerCode = Convert.ToInt32(
                        run.Invoke(null, null));
                }
                catch (TargetInvocationException ex)
                {
                    workerError = ex.InnerException ?? ex;
                    workerCode = 2;
                }
                catch (Exception ex)
                {
                    workerError = ex;
                    workerCode = 2;
                }
            });
        worker.Name = "B51R1_PostSaveRecovery_Attempt2_STA";
        worker.IsBackground = true;
        worker.SetApartmentState(ApartmentState.STA);
        worker.Start();

        if (!worker.Join(WatchdogMilliseconds))
        {
            Console.Error.WriteLine(
                "FAIL_CLOSED_ATTEMPT_002_WATCHDOG_TIMEOUT; " +
                "runner self-termination only; SolidWorks is not terminated.");
            Environment.Exit(124);
            return 124;
        }
        if (workerError != null)
        {
            Console.Error.WriteLine(
                "FAIL_CLOSED_ATTEMPT_002_RUNNER | " +
                workerError.GetType().FullName + " | " +
                workerError.Message);
            return 2;
        }

        Console.WriteLine(
            workerCode == 0
                ? "RECOVERED_CLOSE_AND_NORMAL_EXIT_COLD_REOPEN_PENDING"
                : "FAIL_CLOSED_ATTEMPT_002_SEE_NEW_EVIDENCE");
        return workerCode;
    }
}
