using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;

public static class B51R1S02R8StrongTypedNormalCleanup
{
    [STAThread]
    public static int Run(int expectedProcessId)
    {
        SldWorks app = null;
        ModelDoc2 model = null;
        try
        {
            app = (SldWorks)Marshal.GetActiveObject("SldWorks.Application");
            if (app.GetProcessID() != expectedProcessId)
                throw new InvalidOperationException("ROT process ID mismatch");
            model = app.ActiveDoc as ModelDoc2;
            if (model != null)
            {
                if (!model.IsOpenedReadOnly())
                    throw new InvalidOperationException("Active document is not read-only");
                app.CloseDoc(model.GetTitle());
                Marshal.FinalReleaseComObject(model);
                model = null;
            }
            if (app.GetDocumentCount() != 0 || app.ActiveDoc != null)
                throw new InvalidOperationException("Session is not empty after CloseDoc");
            app.ExitApp();
            Marshal.FinalReleaseComObject(app);
            app = null;
            using (Process process = Process.GetProcessById(expectedProcessId))
            {
                if (!process.WaitForExit(30000))
                    throw new InvalidOperationException("Normal ExitApp timed out");
            }
            return 0;
        }
        catch
        {
            if (model != null) try { Marshal.FinalReleaseComObject(model); } catch { }
            if (app != null) try { Marshal.FinalReleaseComObject(app); } catch { }
            return 1;
        }
    }
}
