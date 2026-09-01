using Microsoft.Win32;
using Microsoft.Win32.SafeHandles;
using System.ComponentModel;
using System.Runtime.InteropServices;

namespace EcoCapture.Transport;

public interface IWire : IDisposable
{
    string Name { get; }
    int Read(byte[] buffer);
    void Write(byte[] bytes);
}
public interface IWireFactory
{
    IEnumerable<string> FindDevices();
    IWire Open(string device);
}

public sealed class WindowsUsbFactory : IWireFactory
{
    public IEnumerable<string> FindDevices()
    {
        if (!OperatingSystem.IsWindows()) return Array.Empty<string>();
        var result = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        using var active = Registry.LocalMachine.OpenSubKey(@"HARDWARE\DEVICEMAP\SERIALCOMM");
        var ports = new HashSet<string>();
        foreach (var name in active?.GetValueNames() ?? Array.Empty<string>())
            if (active!.GetValue(name) is string port) ports.Add(port);
        using var usb = Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Enum\USB");
        foreach (var id in usb?.GetSubKeyNames() ?? Array.Empty<string>())
        {
            // Never probe the CH9102 programming UART: opening it could reset the logger.
            if (!id.StartsWith("VID_303A&PID_4001", StringComparison.OrdinalIgnoreCase)) continue;
            using var devices = usb!.OpenSubKey(id);
            foreach (var instance in devices?.GetSubKeyNames() ?? Array.Empty<string>())
            {
                using var parameters = devices!.OpenSubKey(instance + @"\Device Parameters");
                if (parameters?.GetValue("PortName") is string port && ports.Contains(port)) result.Add(port);
            }
        }
        return result.OrderBy(p => p, StringComparer.OrdinalIgnoreCase).ToArray();
    }
    public IWire Open(string device) => new WindowsUsbWire(device);
}

/// <summary>Dedicated synchronous worker + bounded Win32 timeouts; handle always owned by one connection attempt.</summary>
public sealed class WindowsUsbWire : IWire
{
    public string Name { get; }
    private readonly SafeFileHandle _handle;
    public WindowsUsbWire(string port)
    {
        Name = port;
        _handle = CreateFile(@"\\.\" + port, 0xc0000000, 0, IntPtr.Zero, 3, 0, IntPtr.Zero);
        if (_handle.IsInvalid) { var error = Marshal.GetLastWin32Error(); _handle.Dispose(); throw new Win32Exception(error); }
        try
        {
            var dcb = new Dcb { Length = (uint)Marshal.SizeOf<Dcb>() };
            Check(GetCommState(_handle, ref dcb));
            dcb.BaudRate = 115200; dcb.ByteSize = 8; dcb.Parity = 0; dcb.StopBits = 0;
            dcb.Flags = 1u | (1u << 4); // binary, DTR enabled; RTS/flow control disabled.
            Check(SetCommState(_handle, ref dcb));
            var timeouts = new CommTimeouts { ReadInterval = uint.MaxValue, ReadMultiplier = uint.MaxValue, ReadConstant = 50, WriteConstant = 500 };
            Check(SetCommTimeouts(_handle, ref timeouts));
            Check(PurgeComm(_handle, 0x0c));
        }
        catch { _handle.Dispose(); throw; }
    }
    public int Read(byte[] buffer) { Check(ReadFile(_handle, buffer, (uint)buffer.Length, out var count, IntPtr.Zero)); return (int)count; }
    public void Write(byte[] bytes)
    {
        Check(WriteFile(_handle, bytes, (uint)bytes.Length, out var count, IntPtr.Zero));
        if (count != bytes.Length) throw new IOException("USB write incomplete");
    }
    public void Dispose() => _handle.Dispose();
    private static void Check(bool ok) { if (!ok) throw new Win32Exception(Marshal.GetLastWin32Error()); }
    [StructLayout(LayoutKind.Sequential)] private struct Dcb
    {
        public uint Length, BaudRate, Flags; public ushort Reserved, XonLimit, XoffLimit;
        public byte ByteSize, Parity, StopBits; public sbyte XonChar, XoffChar, ErrorChar, EofChar, EvtChar; public ushort Reserved1;
    }
    [StructLayout(LayoutKind.Sequential)] private struct CommTimeouts { public uint ReadInterval, ReadMultiplier, ReadConstant, WriteMultiplier, WriteConstant; }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] private static extern SafeFileHandle CreateFile(string name, uint access, uint share, IntPtr security, uint creation, uint flags, IntPtr template);
    [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool GetCommState(SafeFileHandle handle, ref Dcb dcb);
    [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool SetCommState(SafeFileHandle handle, ref Dcb dcb);
    [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool SetCommTimeouts(SafeFileHandle handle, ref CommTimeouts timeouts);
    [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool PurgeComm(SafeFileHandle handle, uint flags);
    [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool ReadFile(SafeFileHandle handle, byte[] buffer, uint count, out uint read, IntPtr overlapped);
    [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool WriteFile(SafeFileHandle handle, byte[] buffer, uint count, out uint written, IntPtr overlapped);
}
