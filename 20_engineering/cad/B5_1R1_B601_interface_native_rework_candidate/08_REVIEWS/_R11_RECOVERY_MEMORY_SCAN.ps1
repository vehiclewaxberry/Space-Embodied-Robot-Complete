param([int[]]$TargetProcessId)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$source = @'
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;

public static class R11RecoveryMemoryScanner
{
    private const uint PROCESS_VM_READ = 0x0010;
    private const uint PROCESS_QUERY_INFORMATION = 0x0400;
    private const uint MEM_COMMIT = 0x1000;
    private const uint PAGE_GUARD = 0x100;
    private const uint PAGE_NOACCESS = 0x01;
    private const int ChunkSize = 1024 * 1024;
    private const int ChunkOverlap = 512;
    private const int CandidateLookBehind = 4096;

    [StructLayout(LayoutKind.Sequential)]
    private struct MEMORY_BASIC_INFORMATION
    {
        public IntPtr BaseAddress;
        public IntPtr AllocationBase;
        public uint AllocationProtect;
        public UIntPtr RegionSize;
        public uint State;
        public uint Protect;
        public uint Type;
    }

    private sealed class Spec
    {
        public string Name;
        public string Needle;
        public int Length;
        public string Sha256;
        public int AsciiOccurrences;
        public int UnicodeOccurrences;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(uint desiredAccess, bool inheritHandle, int processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool ReadProcessMemory(
        IntPtr process,
        IntPtr baseAddress,
        [Out] byte[] buffer,
        UIntPtr size,
        out UIntPtr bytesRead);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern UIntPtr VirtualQueryEx(
        IntPtr process,
        IntPtr address,
        out MEMORY_BASIC_INFORMATION buffer,
        UIntPtr length);

    [DllImport("kernel32.dll")]
    private static extern bool CloseHandle(IntPtr handle);

    public static string[] ScanProcess(int processId, string outputDirectory)
    {
        Spec[] specs = new Spec[]
        {
            new Spec
            {
                Name = "CREATE_RECEIPT",
                Needle = "B51R1_S05R2_J01_R11_NATIVE_PILOT_CREATE_V1",
                Length = 102463,
                Sha256 = "4578AB3A9405D3EC8EE62F579FAF2416E1CB03B0256676C894E4CC3F39EFCB3E"
            },
            new Spec
            {
                Name = "CREATE_INPUT_LOCK",
                Needle = "B51R1_S05R2_J01_R11_CREATE_INPUT_LOCK_V1",
                Length = 43594,
                Sha256 = "03C33896B4DEDCE28C39EF94108E097B1D6A59C7C198A36E34BEDF80F9ECD1C1"
            }
        };

        var messages = new List<string>();
        var seen = new HashSet<string>(StringComparer.Ordinal);
        IntPtr process = OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, false, processId);
        if (process == IntPtr.Zero)
        {
            messages.Add("OPEN_FAILED|pid=" + processId + "|win32=" + Marshal.GetLastWin32Error());
            return messages.ToArray();
        }

        long regions = 0;
        long bytesReadTotal = 0;
        int hits = 0;
        try
        {
            long address = 0;
            UIntPtr mbiSize = (UIntPtr)Marshal.SizeOf(typeof(MEMORY_BASIC_INFORMATION));
            while (true)
            {
                MEMORY_BASIC_INFORMATION mbi;
                UIntPtr queried = VirtualQueryEx(process, new IntPtr(address), out mbi, mbiSize);
                if (queried == UIntPtr.Zero)
                    break;

                long regionBase = mbi.BaseAddress.ToInt64();
                long regionSize = unchecked((long)mbi.RegionSize.ToUInt64());
                long next = regionBase + regionSize;
                if (next <= address || regionSize <= 0)
                    break;

                if (IsReadable(mbi))
                {
                    regions++;
                    ScanRegion(process, processId, regionBase, regionSize, specs, seen, outputDirectory, messages, ref bytesReadTotal, ref hits);
                }
                address = next;
            }
        }
        finally
        {
            CloseHandle(process);
        }

        foreach (Spec spec in specs)
        {
            messages.Add(
                "OCCURRENCES|pid=" + processId +
                "|name=" + spec.Name +
                "|ascii=" + spec.AsciiOccurrences +
                "|utf16=" + spec.UnicodeOccurrences);
        }
        messages.Add(
            "SCAN_COMPLETE|pid=" + processId +
            "|regions=" + regions +
            "|bytes_read=" + bytesReadTotal +
            "|verified_hits=" + hits);
        return messages.ToArray();
    }

    private static bool IsReadable(MEMORY_BASIC_INFORMATION mbi)
    {
        if (mbi.State != MEM_COMMIT)
            return false;
        if ((mbi.Protect & PAGE_GUARD) != 0)
            return false;
        if ((mbi.Protect & 0xff) == PAGE_NOACCESS)
            return false;
        return true;
    }

    private static void ScanRegion(
        IntPtr process,
        int processId,
        long regionBase,
        long regionSize,
        Spec[] specs,
        HashSet<string> seen,
        string outputDirectory,
        List<string> messages,
        ref long bytesReadTotal,
        ref int hits)
    {
        long offset = 0;
        while (offset < regionSize)
        {
            int requested = (int)Math.Min(ChunkSize, regionSize - offset);
            byte[] buffer = new byte[requested];
            UIntPtr bytesRead;
            bool ok = ReadProcessMemory(
                process,
                new IntPtr(regionBase + offset),
                buffer,
                (UIntPtr)requested,
                out bytesRead);
            int count = ok ? checked((int)bytesRead.ToUInt64()) : 0;
            if (count > 0)
            {
                bytesReadTotal += count;
                foreach (Spec spec in specs)
                {
                    byte[] asciiNeedle = Encoding.ASCII.GetBytes(spec.Needle);
                    foreach (int match in FindAll(buffer, count, asciiNeedle))
                    {
                        long matchAddress = regionBase + offset + match;
                        string key = "A:" + matchAddress;
                        if (seen.Add(key))
                        {
                            spec.AsciiOccurrences++;
                            byte[] candidate = TryAsciiCandidate(process, regionBase, regionSize, matchAddress, spec);
                            if (candidate != null)
                                SaveHit(processId, spec, matchAddress, "ascii", candidate, outputDirectory, messages, ref hits);
                        }
                    }

                    byte[] unicodeNeedle = Encoding.Unicode.GetBytes(spec.Needle);
                    foreach (int match in FindAll(buffer, count, unicodeNeedle))
                    {
                        long matchAddress = regionBase + offset + match;
                        string key = "U:" + matchAddress;
                        if (seen.Add(key))
                        {
                            spec.UnicodeOccurrences++;
                            byte[] candidate = TryUnicodeCandidate(process, regionBase, regionSize, matchAddress, spec);
                            if (candidate != null)
                                SaveHit(processId, spec, matchAddress, "utf16", candidate, outputDirectory, messages, ref hits);
                        }
                    }
                }
            }

            if (requested <= ChunkOverlap)
                break;
            offset += requested - ChunkOverlap;
        }
    }

    private static IEnumerable<int> FindAll(byte[] haystack, int count, byte[] needle)
    {
        if (needle.Length == 0 || count < needle.Length)
            yield break;

        int[] skip = new int[256];
        for (int i = 0; i < skip.Length; i++)
            skip[i] = needle.Length;
        for (int i = 0; i < needle.Length - 1; i++)
            skip[needle[i]] = needle.Length - 1 - i;

        int cursor = needle.Length - 1;
        while (cursor < count)
        {
            int haystackIndex = cursor;
            int needleIndex = needle.Length - 1;
            while (needleIndex >= 0 && haystack[haystackIndex] == needle[needleIndex])
            {
                haystackIndex--;
                needleIndex--;
            }
            if (needleIndex < 0)
            {
                yield return haystackIndex + 1;
                cursor++;
            }
            else
            {
                cursor += skip[haystack[cursor]];
            }
        }
    }

    private static byte[] TryAsciiCandidate(IntPtr process, long regionBase, long regionSize, long matchAddress, Spec spec)
    {
        long regionEnd = regionBase + regionSize;
        long windowStart = Math.Max(regionBase, matchAddress - CandidateLookBehind);
        long desired = (matchAddress - windowStart) + spec.Length;
        if (windowStart + desired > regionEnd || desired > int.MaxValue)
            return null;

        byte[] window = ReadExact(process, windowStart, (int)desired);
        if (window == null)
            return null;
        int matchOffset = checked((int)(matchAddress - windowStart));
        int candidates = 0;
        for (int start = matchOffset; start >= 0 && candidates < 4; start--)
        {
            if (window[start] != (byte)'{')
                continue;
            candidates++;
            if (start + spec.Length <= window.Length && Hash(window, start, spec.Length) == spec.Sha256)
            {
                byte[] result = new byte[spec.Length];
                Buffer.BlockCopy(window, start, result, 0, spec.Length);
                return result;
            }
        }
        return null;
    }

    private static byte[] TryUnicodeCandidate(IntPtr process, long regionBase, long regionSize, long matchAddress, Spec spec)
    {
        long regionEnd = regionBase + regionSize;
        long windowStart = Math.Max(regionBase, matchAddress - (CandidateLookBehind * 2L));
        if (((matchAddress - windowStart) & 1L) != 0)
            windowStart++;
        long desired = (matchAddress - windowStart) + ((long)spec.Length * 2L);
        if (windowStart + desired > regionEnd || desired > int.MaxValue)
            return null;

        byte[] window = ReadExact(process, windowStart, (int)desired);
        if (window == null)
            return null;
        string text = Encoding.Unicode.GetString(window);
        int matchChar = checked((int)((matchAddress - windowStart) / 2L));
        int candidates = 0;
        for (int start = matchChar; start >= 0 && candidates < 4; start--)
        {
            if (text[start] != '{')
                continue;
            candidates++;
            if (start + spec.Length > text.Length)
                continue;
            byte[] encoded = new UTF8Encoding(false).GetBytes(text.Substring(start, spec.Length));
            if (encoded.Length == spec.Length && Hash(encoded, 0, encoded.Length) == spec.Sha256)
                return encoded;
        }
        return null;
    }

    private static byte[] ReadExact(IntPtr process, long address, int length)
    {
        byte[] buffer = new byte[length];
        UIntPtr bytesRead;
        bool ok = ReadProcessMemory(process, new IntPtr(address), buffer, (UIntPtr)length, out bytesRead);
        if (!ok || bytesRead.ToUInt64() != (ulong)length)
            return null;
        return buffer;
    }

    private static string Hash(byte[] bytes, int offset, int count)
    {
        using (SHA256 sha = SHA256.Create())
        {
            byte[] digest = sha.ComputeHash(bytes, offset, count);
            var value = new StringBuilder(digest.Length * 2);
            foreach (byte item in digest)
                value.Append(item.ToString("X2"));
            return value.ToString();
        }
    }

    private static void SaveHit(
        int processId,
        Spec spec,
        long address,
        string encoding,
        byte[] candidate,
        string outputDirectory,
        List<string> messages,
        ref int hits)
    {
        Directory.CreateDirectory(outputDirectory);
        string path = Path.Combine(
            outputDirectory,
            "pid_" + processId + "_" + spec.Name + "_" + encoding + ".verified.bin");
        File.WriteAllBytes(path, candidate);
        hits++;
        messages.Add(
            "VERIFIED_HIT|pid=" + processId +
            "|name=" + spec.Name +
            "|encoding=" + encoding +
            "|address=0x" + address.ToString("X") +
            "|path=" + path);
    }
}
'@

Add-Type -TypeDefinition $source -Language CSharp

$outputDirectory = 'C:\Users\stude\AppData\Local\Temp\R11_MEMORY_FORENSICS'
$processIds = if ($TargetProcessId.Count -gt 0) {
    @($TargetProcessId)
}
else {
    Get-CimInstance Win32_Process |
        Where-Object {
            ($_.Name -eq 'codex.exe') -or
            ($_.Name -eq 'ChatGPT.exe' -and $_.CommandLine -match '--type=renderer')
        } |
        Sort-Object ProcessId |
        Select-Object -ExpandProperty ProcessId
}

foreach ($targetPid in $processIds) {
    [R11RecoveryMemoryScanner]::ScanProcess([int]$targetPid, $outputDirectory)
}
