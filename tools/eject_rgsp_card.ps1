#requires -RunAsAdministrator
[CmdletBinding()]
param(
    [int]$DiskNumber = 3,
    [string]$SerialNumber = '000000001539'
)

$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class RgspMediaEject {
    public const uint GENERIC_READ = 0x80000000;
    public const uint GENERIC_WRITE = 0x40000000;
    public const uint FILE_SHARE_READ = 0x00000001;
    public const uint FILE_SHARE_WRITE = 0x00000002;
    public const uint OPEN_EXISTING = 3;
    public const uint IOCTL_STORAGE_EJECT_MEDIA = 0x002D4808;
    public static readonly IntPtr INVALID_HANDLE_VALUE = new IntPtr(-1);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr CreateFile(
        string name, uint access, uint share, IntPtr security,
        uint creation, uint flags, IntPtr template);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool DeviceIoControl(
        IntPtr device, uint code, IntPtr input, uint inputSize,
        IntPtr output, uint outputSize, out uint returned, IntPtr overlapped);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool CloseHandle(IntPtr handle);
}
'@

$disk = Get-Disk -Number $DiskNumber
if ($disk.SerialNumber.Trim() -ne $SerialNumber) {
    throw "Disk identity mismatch: expected $SerialNumber, got $($disk.SerialNumber)"
}
$device = "\\.\PhysicalDrive$DiskNumber"
$handle = [RgspMediaEject]::CreateFile(
    $device,
    [RgspMediaEject]::GENERIC_READ -bor [RgspMediaEject]::GENERIC_WRITE,
    [RgspMediaEject]::FILE_SHARE_READ -bor [RgspMediaEject]::FILE_SHARE_WRITE,
    [IntPtr]::Zero,
    [RgspMediaEject]::OPEN_EXISTING,
    0,
    [IntPtr]::Zero)
if ($handle -eq [RgspMediaEject]::INVALID_HANDLE_VALUE) {
    throw "Unable to open ${device}: $([ComponentModel.Win32Exception]::new([Runtime.InteropServices.Marshal]::GetLastWin32Error()).Message)"
}
try {
    [uint32]$returned = 0
    $ok = [RgspMediaEject]::DeviceIoControl(
        $handle,
        [RgspMediaEject]::IOCTL_STORAGE_EJECT_MEDIA,
        [IntPtr]::Zero, 0,
        [IntPtr]::Zero, 0,
        [ref]$returned,
        [IntPtr]::Zero)
    if (-not $ok) {
        $errorCode = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        throw "Eject request failed for ${device}: $([ComponentModel.Win32Exception]::new($errorCode).Message)"
    }
    Write-Output "EJECT_REQUEST_SENT disk=$DiskNumber serial=$SerialNumber"
} finally {
    [void][RgspMediaEject]::CloseHandle($handle)
}
