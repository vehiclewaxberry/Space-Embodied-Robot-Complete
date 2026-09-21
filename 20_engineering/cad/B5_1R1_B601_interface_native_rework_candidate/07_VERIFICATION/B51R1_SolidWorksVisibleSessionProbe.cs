using System;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;

public static class B51R1SolidWorksVisibleSessionProbe
{
    [STAThread]
    public static int Run()
    {
        try
        {
            object active = Marshal.GetActiveObject("SldWorks.Application");
            var swApp = (SldWorks)active;
            Console.WriteLine("BOUND=true");
            Console.WriteLine("REVISION=" + swApp.RevisionNumber());
            Console.WriteLine("VISIBLE=" + swApp.Visible);
            Console.WriteLine("DOCUMENT_COUNT=" + swApp.GetDocumentCount());
            ModelDoc2 activeDoc = (ModelDoc2)swApp.ActiveDoc;
            Console.WriteLine("ACTIVE_DOC=" + (activeDoc == null ? "NULL" : activeDoc.GetPathName()));
            Marshal.FinalReleaseComObject(swApp);
            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("ERROR_TYPE=" + ex.GetType().FullName);
            try
            {
                Console.Error.WriteLine("ERROR_MESSAGE=" + ex.Message);
            }
            catch
            {
                Console.Error.WriteLine("ERROR_MESSAGE=<unavailable>");
            }
            Console.Error.WriteLine("ERROR_HRESULT=0x" + ex.HResult.ToString("X8"));
            return 1;
        }
    }
}
