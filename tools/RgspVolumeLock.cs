using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class RgspVolumeLock
{
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFileW(
        string name, uint access, uint share, IntPtr security,
        uint creation, uint flags, IntPtr template);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool DeviceIoControl(
        SafeFileHandle handle, uint code, IntPtr input, uint inputSize,
        IntPtr output, uint outputSize, out uint returned, IntPtr overlapped);

    public static void Control(SafeFileHandle handle, uint code)
    {
        uint returned;
        if (!DeviceIoControl(handle, code, IntPtr.Zero, 0, IntPtr.Zero, 0,
                             out returned, IntPtr.Zero))
            throw new Win32Exception(Marshal.GetLastWin32Error());
    }

    public static SafeFileHandle LockAndDismount(string path)
    {
        var handle = CreateFileW(path.TrimEnd('\\'), 0xc0000000, 3,
                                 IntPtr.Zero, 3, 0, IntPtr.Zero);
        if (handle.IsInvalid)
        {
            int error = Marshal.GetLastWin32Error();
            handle.Dispose();
            throw new Win32Exception(error);
        }
        try
        {
            Control(handle, 0x00090018); // FSCTL_LOCK_VOLUME
            Control(handle, 0x00090020); // FSCTL_DISMOUNT_VOLUME
            return handle;
        }
        catch
        {
            handle.Dispose();
            throw;
        }
    }
}
