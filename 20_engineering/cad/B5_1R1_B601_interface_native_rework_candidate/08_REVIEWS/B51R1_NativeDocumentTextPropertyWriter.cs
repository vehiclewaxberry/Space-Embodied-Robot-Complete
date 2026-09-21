using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using SolidWorks.Interop.sldworks;

public sealed class B51R1DocumentTextPropertyResult
{
    public string Name { get; internal set; }
    public string Value { get; internal set; }
    public string Action { get; internal set; }
    public int FieldType { get; internal set; }
    public int Get6Result { get; internal set; }
    public int? Add3Result { get; internal set; }
    public bool WasResolved { get; internal set; }
    public bool Linked { get; internal set; }
    public int ConfigurationDuplicateCount { get; internal set; }
}

public static class B51R1NativeDocumentTextPropertyWriter
{
    private const int CustomInfoText = 30;
    private const int CustomPropertyOnlyIfNew = 0;
    private const int CustomInfoAddResultAddedOrChanged = 0;
    private const int CustomInfoGetResultNotPresent = 1;
    private const int CustomInfoGetResultResolvedValue = 2;

    private static readonly Regex ValidName = new Regex(
        "^[A-Z][A-Z0-9_]*$",
        RegexOptions.CultureInvariant);

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static void ReleaseCom(object value)
    {
        if (value == null || !Marshal.IsComObject(value)) return;
        try { Marshal.FinalReleaseComObject(value); }
        catch { }
    }

    private static int CountConfigurationDuplicates(
        ModelDoc2 model,
        ModelDocExtension extension,
        string name)
    {
        Array rawConfigurations = model.GetConfigurationNames() as Array;
        Require(rawConfigurations != null, "Configuration names are unavailable");
        int duplicateCount = 0;
        foreach (object rawConfiguration in rawConfigurations)
        {
            string configurationName = Convert.ToString(rawConfiguration);
            CustomPropertyManager manager = null;
            try
            {
                manager = extension.get_CustomPropertyManager(configurationName);
                Require(manager != null,
                    "Configuration property manager is unavailable: " + configurationName);
                Array rawNames = manager.GetNames() as Array;
                if (rawNames == null) continue;
                foreach (object rawName in rawNames)
                {
                    if (String.Equals(
                        Convert.ToString(rawName), name, StringComparison.Ordinal))
                        duplicateCount++;
                }
            }
            finally
            {
                ReleaseCom(manager);
            }
        }
        return duplicateCount;
    }

    private static B51R1DocumentTextPropertyResult ReadExact(
        CustomPropertyManager manager,
        string name,
        string expectedValue,
        string action,
        int? add3Result,
        int configurationDuplicateCount)
    {
        string raw;
        string resolved;
        bool wasResolved;
        bool linked;
        int get6Result = manager.Get6(
            name, false, out raw, out resolved, out wasResolved, out linked);
        Require(get6Result == CustomInfoGetResultResolvedValue,
            "Property " + name + " Get6 result=" + get6Result + "; expected 2");
        int fieldType = manager.GetType2(name);
        Require(fieldType == CustomInfoText,
            "Property " + name + " type=" + fieldType + "; expected text=30");
        Require(wasResolved, "Property " + name + " was not freshly resolved");
        Require(!linked, "Property " + name + " contains a linked expression");
        Require(String.Equals(raw, expectedValue, StringComparison.Ordinal),
            "Property " + name + " raw value mismatch");
        Require(String.Equals(resolved, expectedValue, StringComparison.Ordinal),
            "Property " + name + " resolved value mismatch");
        return new B51R1DocumentTextPropertyResult
        {
            Name = name,
            Value = expectedValue,
            Action = action,
            FieldType = fieldType,
            Get6Result = get6Result,
            Add3Result = add3Result,
            WasResolved = wasResolved,
            Linked = linked,
            ConfigurationDuplicateCount = configurationDuplicateCount
        };
    }

    public static B51R1DocumentTextPropertyResult EnsureDocumentTextProperty(
        ModelDoc2 model,
        string name,
        string exactExpectedValue)
    {
        Require(model != null, "ModelDoc2 is required");
        Require(!String.IsNullOrWhiteSpace(name) &&
            String.Equals(name, name.Trim(), StringComparison.Ordinal) &&
            ValidName.IsMatch(name),
            "Property name must be exact uppercase ASCII snake case without whitespace");
        Require(exactExpectedValue != null,
            "Exact expected property value must not be null");

        ModelDocExtension extension = null;
        CustomPropertyManager documentManager = null;
        try
        {
            extension = model.Extension;
            Require(extension != null, "ModelDocExtension is unavailable");
            int configurationDuplicateCount =
                CountConfigurationDuplicates(model, extension, name);
            Require(configurationDuplicateCount == 0,
                "Property " + name + " exists at configuration level");

            documentManager = extension.get_CustomPropertyManager("");
            Require(documentManager != null,
                "Document-level CustomPropertyManager is unavailable");
            string raw;
            string resolved;
            bool wasResolved;
            bool linked;
            int get6Result = documentManager.Get6(
                name, false, out raw, out resolved, out wasResolved, out linked);

            if (get6Result == CustomInfoGetResultNotPresent)
            {
                int add3Result = documentManager.Add3(
                    name,
                    CustomInfoText,
                    exactExpectedValue,
                    CustomPropertyOnlyIfNew);
                Require(add3Result == CustomInfoAddResultAddedOrChanged,
                    "Add3 only-if-new failed for " + name + " with result=" + add3Result);
                return ReadExact(
                    documentManager,
                    name,
                    exactExpectedValue,
                    "ADDED_ONLY_IF_NEW",
                    add3Result,
                    configurationDuplicateCount);
            }

            Require(get6Result == CustomInfoGetResultResolvedValue,
                "Property " + name + " has unsupported Get6 state=" + get6Result);
            return ReadExact(
                documentManager,
                name,
                exactExpectedValue,
                "NO_OP_EXACT_MATCH",
                null,
                configurationDuplicateCount);
        }
        finally
        {
            ReleaseCom(documentManager);
            ReleaseCom(extension);
        }
    }
}
