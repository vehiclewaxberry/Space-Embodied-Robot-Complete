using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Threading;

internal static class B51R1SingleCsColdReopenRunner
{
    private const string AuthorizationToken =
        "--authorized-single-cs-cold-reopen-once";
    private const int WatchdogMilliseconds = 150000;
    private const string SldWorksInteropPath =
        @"F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll";
    private const string SwConstInteropPath =
        @"F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.swconst.dll";

    private static Assembly ResolveAssembly(object sender, ResolveEventArgs args)
    {
        AssemblyName requested = new AssemblyName(args.Name);
        if (String.Equals(
            requested.Name,
            "SolidWorks.Interop.sldworks",
            StringComparison.OrdinalIgnoreCase) &&
            File.Exists(SldWorksInteropPath))
        {
            return Assembly.LoadFrom(SldWorksInteropPath);
        }
        if (String.Equals(
            requested.Name,
            "SolidWorks.Interop.swconst",
            StringComparison.OrdinalIgnoreCase) &&
            File.Exists(SwConstInteropPath))
        {
            return Assembly.LoadFrom(SwConstInteropPath);
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
                "NOT RUN. Exact single-CS cold-reopen authorization token required.");
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
            "B51R1_SingleCsColdReopen.Core.dll");
        if (!File.Exists(corePath))
        {
            Console.Error.WriteLine(
                "FAIL_CLOSED. Strong-typed cold-reopen core is missing.");
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
                        "B51R1.NativeCadDiagnostics.SingleCsColdReopen",
                        true);
                    MethodInfo run = type.GetMethod(
                        "Run",
                        BindingFlags.Public | BindingFlags.Static);
                    workerCode = Convert.ToInt32(run.Invoke(null, null));
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
        worker.Name = "B51R1_SingleCsColdReopen_STA";
        worker.IsBackground = true;
        worker.SetApartmentState(ApartmentState.STA);
        worker.Start();

        if (!worker.Join(WatchdogMilliseconds))
        {
            Console.Error.WriteLine(
                "FAIL_CLOSED_COLD_REOPEN_WATCHDOG_TIMEOUT; " +
                "runner self-termination only; SolidWorks is not terminated.");
            Environment.Exit(124);
            return 124;
        }
        if (workerError != null)
        {
            Console.Error.WriteLine(
                "FAIL_CLOSED_COLD_REOPEN_RUNNER | " +
                workerError.GetType().FullName + " | " +
                workerError.Message);
            return 2;
        }

        Console.WriteLine(
            workerCode == 0
                ? "SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS"
                : "FAIL_CLOSED_SINGLE_CS_COLD_REOPEN_SEE_EVIDENCE");
        return workerCode;
    }
}
