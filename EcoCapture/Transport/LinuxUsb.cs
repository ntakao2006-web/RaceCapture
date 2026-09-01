using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace EcoCapture.Transport;

public static class PlatformWireFactory
{
    public static IWireFactory Create() => OperatingSystem.IsWindows() ? new WindowsUsbFactory() :
        OperatingSystem.IsLinux() ? new LinuxUsbFactory() : new UnavailableWireFactory();
    private sealed class UnavailableWireFactory : IWireFactory
    { public IEnumerable<string> FindDevices()=>Array.Empty<string>(); public IWire Open(string device)=>throw new IOException("Unsupported OS"); }
}

/// <summary>Raspberry Pi / ROCK: match USB identity in sysfs; never scan arbitrary serial/programming ports.</summary>
public sealed class LinuxUsbFactory : IWireFactory
{
    public IEnumerable<string> FindDevices()
    {
        if(!OperatingSystem.IsLinux() || !Directory.Exists("/sys/class/tty")) return Array.Empty<string>();
        var result=new List<string>();
        foreach(var tty in Directory.EnumerateDirectories("/sys/class/tty","ttyACM*"))
        {
            var device=new DirectoryInfo(Path.Combine(tty,"device"));
            var physical=device.ResolveLinkTarget(true) as DirectoryInfo;
            if(physical!=null && MatchesEcoLogger(physical)) result.Add("/dev/"+Path.GetFileName(tty));
        }
        return result.OrderBy(x=>x,StringComparer.Ordinal).ToArray();
    }
    public static bool MatchesEcoLogger(DirectoryInfo physical)
    {
        for(var depth=0;physical!=null&&depth<8;physical=physical.Parent!,depth++)
        {
            var vendor=Path.Combine(physical.FullName,"idVendor"); var product=Path.Combine(physical.FullName,"idProduct");
            if(File.Exists(vendor)&&File.Exists(product))
                return File.ReadAllText(vendor).Trim().Equals("303a",StringComparison.OrdinalIgnoreCase)&&
                    File.ReadAllText(product).Trim().Equals("4001",StringComparison.OrdinalIgnoreCase);
        }
        return false;
    }
    public IWire Open(string device)=>new LinuxUsbWire(device);
}

/// <summary>glibc termios/poll for Linux x86_64 and AArch64. No Windows DLL or shell process on the receive path.</summary>
public sealed class LinuxUsbWire : IWire
{
    private readonly SafeFd _fd;
    public string Name{get;}
    public LinuxUsbWire(string path,bool configureModem=true)
    {
        Name=path;
        var fd=open(path,2|0x100|0x800|0x80000); // RDWR, NOCTTY, NONBLOCK, CLOEXEC
        if(fd<0) throw Error("open"); _fd=new SafeFd(fd);
        try
        {
            var term=new Termios { Cc=new byte[32] };
            Check(tcgetattr(_fd,ref term),"tcgetattr"); cfmakeraw(ref term);
            term.Cflag=(term.Cflag&~(0x30u|0x40u|0x100u|0x80000000u))|0x30u|0x80u|0x800u|0x400u;
            Check(cfsetispeed(ref term,0x1002),"cfsetispeed"); Check(cfsetospeed(ref term,0x1002),"cfsetospeed");
            term.Cc[5]=0; term.Cc[6]=0; // VTIME / VMIN; bounded poll owns the deadline.
            Check(tcsetattr(_fd,0,ref term),"tcsetattr"); Check(tcflush(_fd,2),"tcflush");
            if(configureModem) { var dtr=2; Check(ioctl(_fd,0x5416,ref dtr),"DTR"); }
        }
        catch { _fd.Dispose(); throw; }
    }
    public int Read(byte[] buffer)
    {
        if(!Wait(1,50)) return 0;
        var count=read(_fd,buffer,(nuint)buffer.Length);
        if(count<0) { var e=Marshal.GetLastWin32Error(); if(e is 4 or 11) return 0; throw Error("read",e); }
        if(count==0) throw new IOException("EcoLogger USB disconnected");
        return (int)count;
    }
    public void Write(byte[] bytes)
    {
        var deadline=ConnectionManager.Now+.5; var offset=0;
        while(offset<bytes.Length)
        {
            if(ConnectionManager.Now>=deadline) throw new TimeoutException("USB write timeout");
            if(!Wait(4,50)) continue;
            var remaining=offset==0?bytes:bytes.AsSpan(offset).ToArray();
            var count=write(_fd,remaining,(nuint)remaining.Length);
            if(count<0) { var e=Marshal.GetLastWin32Error(); if(e is 4 or 11) continue; throw Error("write",e); }
            offset+=(int)count;
        }
    }
    private bool Wait(short events,int timeout)
    {
        var p=new PollFd{Fd=(int)_fd.DangerousGetHandle(),Events=events};
        var n=poll(ref p,1,timeout);
        if(n<0) { var e=Marshal.GetLastWin32Error(); if(e==4) return false; throw Error("poll",e); }
        if((p.Revents&0x38)!=0) throw new IOException("EcoLogger USB disconnected");
        return n>0&&(p.Revents&events)!=0;
    }
    public void Dispose()=>_fd.Dispose();
    private static void Check(int result,string operation) { if(result<0) throw Error(operation); }
    private static IOException Error(string operation,int? error=null)
    {
        var e=error??Marshal.GetLastWin32Error();
        return new IOException(e==13?"USB権限がありません。dialoutグループまたはudevルールを確認してください。":$"USB {operation}: errno {e}");
    }
    private sealed class SafeFd : SafeHandleMinusOneIsInvalid
    {
        public SafeFd(int fd):base(true){SetHandle(fd);}
        protected override bool ReleaseHandle()=>close((int)handle)==0;
    }
    [StructLayout(LayoutKind.Sequential)] private struct PollFd { public int Fd; public short Events,Revents; }
    [StructLayout(LayoutKind.Sequential)] private struct Termios
    { public uint Iflag,Oflag,Cflag,Lflag; public byte Line; [MarshalAs(UnmanagedType.ByValArray,SizeConst=32)] public byte[] Cc; public uint Ispeed,Ospeed; }
    [DllImport("libc",SetLastError=true)] private static extern int open(string path,int flags);
    [DllImport("libc",SetLastError=true)] private static extern int close(int fd);
    [DllImport("libc",SetLastError=true)] private static extern int tcgetattr(SafeFd fd,ref Termios termios);
    [DllImport("libc",SetLastError=true)] private static extern int tcsetattr(SafeFd fd,int actions,ref Termios termios);
    [DllImport("libc")] private static extern void cfmakeraw(ref Termios termios);
    [DllImport("libc",SetLastError=true)] private static extern int cfsetispeed(ref Termios termios,uint speed);
    [DllImport("libc",SetLastError=true)] private static extern int cfsetospeed(ref Termios termios,uint speed);
    [DllImport("libc",SetLastError=true)] private static extern int tcflush(SafeFd fd,int queue);
    [DllImport("libc",SetLastError=true)] private static extern int ioctl(SafeFd fd,nuint request,ref int bits);
    [DllImport("libc",SetLastError=true)] private static extern int poll(ref PollFd fds,nuint count,int timeout);
    [DllImport("libc",SetLastError=true)] private static extern nint read(SafeFd fd,byte[] buffer,nuint size);
    [DllImport("libc",SetLastError=true)] private static extern nint write(SafeFd fd,byte[] buffer,nuint size);
}
