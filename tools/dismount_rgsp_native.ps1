#requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
Add-Type @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class RgspVolumeIo {
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  public static extern IntPtr CreateFile(string name, uint access, uint share, IntPtr sec,
      uint creation, uint flags, IntPtr template);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool DeviceIoControl(IntPtr h, uint code, IntPtr inbuf, uint inlen,
      IntPtr outbuf, uint outlen, out uint returned, IntPtr overlapped);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool CloseHandle(IntPtr h);
  public const uint GenericRead=0x80000000, GenericWrite=0x40000000;
  public const uint ShareRead=1, ShareWrite=2, OpenExisting=3;
  public const uint FsctlLock=0x00090018, FsctlDismount=0x00090020;
  public static void Dismount(string path) {
    IntPtr h=CreateFile(path, GenericRead|GenericWrite, ShareRead|ShareWrite,
      IntPtr.Zero, OpenExisting, 0, IntPtr.Zero);
    if (h == new IntPtr(-1)) throw new Win32Exception(Marshal.GetLastWin32Error(), path);
    try {
      uint n;
      if (!DeviceIoControl(h, FsctlLock, IntPtr.Zero, 0, IntPtr.Zero, 0, out n, IntPtr.Zero))
        throw new Win32Exception(Marshal.GetLastWin32Error(), "FSCTL_LOCK_VOLUME "+path);
      if (!DeviceIoControl(h, FsctlDismount, IntPtr.Zero, 0, IntPtr.Zero, 0, out n, IntPtr.Zero))
        throw new Win32Exception(Marshal.GetLastWin32Error(), "FSCTL_DISMOUNT_VOLUME "+path);
    } finally { CloseHandle(h); }
  }
}
'@
$parts = @(Get-Partition -DiskNumber 3 | Sort-Object PartitionNumber)
foreach ($part in $parts) {
  foreach ($path in @($part.AccessPaths)) {
    if ($path -match '^\\\\\?\\Volume\{[0-9a-fA-F-]{36}\}\\$') {
      [RgspVolumeIo]::Dismount($path)
      Write-Host "DISMOUNTED $path"
    }
  }
}
