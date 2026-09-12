#requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
$resultPath = (Resolve-Path '.\out\rgsp-single-card-v2-20260911').Path + '\native-write-result.txt'
Set-Content -LiteralPath $resultPath -Value 'START'
Add-Type @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class RgspRawIo {
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  public static extern IntPtr CreateFile(string name, uint access, uint share, IntPtr sec,
    uint creation, uint flags, IntPtr template);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool SetFilePointerEx(IntPtr h, long distance, out long moved, uint method);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool WriteFile(IntPtr h, byte[] data, uint count, out uint written, IntPtr overlapped);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool ReadFile(IntPtr h, byte[] data, uint count, out uint read, IntPtr overlapped);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool FlushFileBuffers(IntPtr h);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool CloseHandle(IntPtr h);
  public const uint Read=0x80000000, Write=0x40000000, ShareRead=1, ShareWrite=2, Open=3;
  public static void Check(bool ok, string op) {
    if (!ok) throw new Win32Exception(Marshal.GetLastWin32Error(), op);
  }
}
'@
$sourcePath = (Resolve-Path '.\out\rgsp-single-card-20260911\system.raw.img').Path
$data = [IO.File]::ReadAllBytes($sourcePath).AsSpan(0,1MB).ToArray()
$h = [RgspRawIo]::CreateFile('\\.\PhysicalDrive3',[RgspRawIo]::Read -bor [RgspRawIo]::Write,
  [RgspRawIo]::ShareRead -bor [RgspRawIo]::ShareWrite,[IntPtr]::Zero,[RgspRawIo]::Open,0,[IntPtr]::Zero)
if ($h -eq [IntPtr]::new(-1)) { throw [ComponentModel.Win32Exception]::new([Runtime.InteropServices.Marshal]::GetLastWin32Error()) }
try {
  [long]$moved=0
  [RgspRawIo]::Check([RgspRawIo]::SetFilePointerEx($h,222298112L,[ref]$moved,0),'seek')
  [uint32]$written=0
  [RgspRawIo]::Check([RgspRawIo]::WriteFile($h,$data,[uint32]$data.Length,[ref]$written,[IntPtr]::Zero),'write')
  [RgspRawIo]::Check([RgspRawIo]::FlushFileBuffers($h),'flush')
  Set-Content -LiteralPath $resultPath -Value "NATIVE_WRITE_OK bytes=$written"
} catch {
  Set-Content -LiteralPath $resultPath -Value ("NATIVE_WRITE_FAILED " + $_.Exception.ToString())
  throw
} finally { [RgspRawIo]::CloseHandle($h) | Out-Null }
