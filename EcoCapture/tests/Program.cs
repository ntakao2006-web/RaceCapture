using EcoCapture.Core;
using EcoCapture.Transport;
using System.Collections.Concurrent;
using System.Text;
using System.Text.Json;
using System.Runtime.InteropServices;

static class Program
{
    static int checks;
    static void Check(bool result,string message) { checks++; if(!result) throw new Exception("FAIL: "+message); }
    static void Near(double a,double b,double tolerance,string message) => Check(Math.Abs(a-b)<=tolerance,message+$" ({a} vs {b})");
    static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();
    static void Reject(Action operation,string message) { try { operation(); } catch(FormatException) { Check(true,message); return; } throw new Exception("FAIL: "+message); }
    static TelemetryFrame Frame(double at,double lat=35,double lon=139,double speed=36,double gyro=0) => new(at,(ulong)(at*1e6),1,new Dictionary<string,double> {
        ["Lat"]=lat,["Lon"]=lon,["GPSFix"]=3,["GPSHAcc"]=1,["GNSSAge"]=0,["GPSTow"]=at*1000,["GPSSpeed"]=speed,
        ["IMULink"]=1,["IMUErr"]=0,["GyroZ"]=gyro,["GForceX"]=0 });
    static async Task<int> Main(string[] args)
    {
        try
        {
            if(args.Contains("--bench")) return await Bench(args);
            ProtocolTests(); SettingsTests(); NavigationTests(); LapTests(); SolveTests(); await ConnectionTests(); LinuxTests();
            Console.WriteLine($"PASS: {checks} checks (protocol, settings, navigation, laps, solve, calibration, reconnect lifecycle)"); return 0;
        }
        catch(Exception e) { Console.Error.WriteLine(e); return 1; }
    }
    static void ProtocolTests()
    {
        var framer=new LineFramer(); var lines=new List<string>();
        framer.Push(Encoding.UTF8.GetBytes("{\"a\":"),lines.Add); framer.Push(Encoding.UTF8.GetBytes("1}\r\n{\"b\":2}\n"),lines.Add);
        Check(lines.SequenceEqual(new[]{"{\"a\":1}","{\"b\":2}"}),"fragmentation and CRLF");
        framer.Push(new byte[LineFramer.MaxBytes+30],lines.Add); framer.Push(Encoding.UTF8.GetBytes("\n{}\n"),lines.Add);
        Check(framer.DroppedLines==1&&lines.Last()=="{}","bounded overflow resynchronizes");
        var decoder=new RcpDecoder();
        var meta=Enumerable.Range(0,75).Select(i=>new{nm="C"+i,ut="",min=0,max=100,prec=1,sr=10});
        decoder.SetMetadata(Json(JsonSerializer.Serialize(meta)));
        var f=decoder.Decode(Json("{\"schema\":1,\"monotonic_us\":500,\"d\":[12,23,34,45,2147483649,1,1024]}"),10);
        Check(f.Values.Count==4&&f.Get("C0")==12&&f.Get("C31")==23&&f.Get("C32")==34&&f.Get("C74")==45,"75 channel sparse unsigned bitmaps");
        var missing=decoder.Decode(Json("{\"schema\":1,\"d\":[0,0,0]}"),10.1);
        Check(missing.Get("C0")==null,"missing values are not retained");
        Check(f.Fresh(11)&&!f.Fresh(12),"stale data invalidation");
        Reject(()=>decoder.Decode(Json("{\"schema\":2,\"d\":[0,0,0]}"),11),"schema change requires metadata");
        Reject(()=>decoder.Decode(Json("{\"schema\":1,\"d\":[1,0,0]}"),11),"bitmap/value mismatch rejected");
        Reject(()=>decoder.Decode(Json("{\"schema\":1,\"d\":[1,0,0,2048]}"),11),"out of schema bitmap rejected");
        decoder.Reset(); Reject(()=>decoder.Decode(Json("{\"d\":[0]}"),1),"reconnect requires new metadata");
    }
    static void SettingsTests()
    {
        var s=new AppSettings { Vehicle="cub",CanEnabled=true }; Check(s.CurrentSensors()["CHT"].Visible,"Cub CHT default");
        s.CurrentSensors()["CHT"].Visible=false; s.Vehicle="roadster";
        Check(s.CurrentSensors()["WaterTemp"].Visible&&!s.CurrentSensors()["CHT"].Visible,"Roadster profile");
        s.Vehicle="cub"; Check(!s.CurrentSensors()["CHT"].Visible,"profile edits isolated and retained");
        s.Vehicle="lx"; Check(s.CurrentSensors()["EngineLoad"].Visible,"LX profile");
        s.Vehicle="none"; s.Validate(); Check(!s.CanEnabled&&Catalog.Sensors.Where(x=>s.CurrentSensors()[x.Id].Visible).All(x=>x.Source!="CAN"),"no CAN mode");
        Check(s.CurrentSensors()["VertAccel"].Visible&&s.CurrentSensors()["Lat"].Visible&&s.CurrentSensors()["Lon"].Visible&&s.CurrentSensors().Count(x=>x.Value.Visible)==9,"no CAN includes coordinates and corrected vertical acceleration");
        var old=new AppSettings{Version=1,Vehicle="none",Profiles=new(){{"none",new(){{"VertAccel",new(){Visible=false}}}}}}; old.Validate();
        Check(old.Version==3&&old.CurrentSensors()["VertAccel"].Visible&&old.CurrentSensors()["Lat"].Visible&&old.CurrentSensors()["Lon"].Visible,"0.2 settings migrate vertical acceleration and coordinates into view");
        s.ImuAid=true; s.ForwardAxis="+Z"; s.UpAxis="-Z"; s.Validate(); Check(!s.ImuAid,"invalid mount axes disable fusion");
        var directory=Path.Combine(Path.GetTempPath(),"EcoCaptureTests",Guid.NewGuid().ToString("N")); Directory.CreateDirectory(directory);
        var path=Path.Combine(directory,"settings.json"); SettingsStore.Save(path,s); var restored=SettingsStore.Load(path,out var warning);
        Check(restored.Vehicle=="none"&&!restored.CanEnabled&&warning==null,"atomic settings roundtrip");
        File.WriteAllText(path,"broken"); restored=SettingsStore.Load(path,out warning);
        Check(warning!=null&&File.ReadAllText(path)=="broken","corrupt settings retained");
        s.Vehicle="unknown"; s.CanEnabled=true; s.Validate(); Check(s.Vehicle=="none"&&!s.CanEnabled,"unknown profile falls back to no CAN");
    }
    static void NavigationTests()
    {
        var p=Geo.Move(35,139,500,1000); var offset=Geo.Offset(35,139,p.Lat,p.Lon);
        Near(offset.East,500,.01,"east projection"); Near(offset.North,1000,.01,"north projection");
        var zoom=Geo.ZoomForSpan(35,2000,600); var mpp=Geo.MetersPerPixel(35,zoom); var scale=600/2000d*mpp;
        Near(600/scale*mpp,2000,.0001,"exact 2km map span");
        var estimator=new PositionEstimator(); var settings=new AppSettings();
        estimator.Update(Frame(10),settings); Check(estimator.Current?.Mode=="GNSS","default GNSS only");
        var f=new TelemetryFrame(10.5,10500000,1,new Dictionary<string,double>{{"IMULink",1},{"IMUErr",0},{"GyroZ",0},{"GForceX",0}});
        estimator.Update(f,settings); Check(estimator.Current?.UpdatedAt==10,"no unconfirmed inertial prediction");
        settings.ImuAid=true; estimator.Reset(); estimator.Update(Frame(20),settings); var next=Geo.Move(35,139,0,10); estimator.Update(Frame(21,next.Lat,next.Lon),settings);
        estimator.Update(f with{ReceivedAt=21.2,DeviceUs=21200000},settings);
        Check(estimator.Current?.Estimated==true&&estimator.Current.Latitude>next.Lat,"bounded gyro coasting");
        estimator.Update(f with{ReceivedAt=24.2,DeviceUs=24200000},settings);
        Check(!estimator.Usable(24.2),"IMU prediction expires after 3 seconds");
        estimator.Update(Frame(1),settings); Check(estimator.Current?.GnssAt==1,"logger reboot resets estimator");
        estimator.Reset(); estimator.Update(Frame(30,speed:18),settings);
        for(var i=1;i<=8;i++) { var p2=Geo.Move(35,139,.5*i,0); estimator.Update(Frame(30+i*.1,p2.Lat,p2.Lon,18),settings); }
        Check(estimator.Current?.Mode=="GNSS + IMU","10Hz low speed movement establishes course");
        Near(estimator.Current!.Bearing,90,.01,"low speed course points east");
        estimator.Reset(); estimator.Update(Frame(50,speed:0),settings);
        Near(estimator.Current!.Bearing,0,.01,"reset cannot retain heading from demo or prior connection");
    }
    static void LapTests()
    {
        var line=new StartLine{Enabled=true,Latitude=35,Longitude=139,Bearing=0,WidthMeters=30,MinimumLapSeconds=5};
        var a=Geo.Move(35,139,0,-5); var b=Geo.Move(35,139,0,5);
        var race=new RaceSession(); race.Start(0); race.UpdateGnss(Frame(10,a.Lat,a.Lon),line);
        Check(race.UpdateGnss(Frame(10.5,b.Lat,b.Lon),line),"forward line crossing"); Near(race.Laps[0].Seconds,10.25,.001,"crossing time interpolation");
        race.UpdateGnss(Frame(11,a.Lat,a.Lon),line); Check(!race.UpdateGnss(Frame(11.5,b.Lat,b.Lon),line),"minimum lap guard");
        race.BreakPositionContinuity(); race.UpdateGnss(Frame(20,b.Lat,b.Lon),line); Check(!race.UpdateGnss(Frame(20.5,a.Lat,a.Lon),line),"wrong direction ignored");
        race.BreakPositionContinuity(); race.UpdateGnss(Frame(30,a.Lat,a.Lon),line); Check(!race.UpdateGnss(Frame(32,b.Lat,b.Lon),line),"USB/GNSS gap cannot fabricate lap");
        var c=Geo.Move(35,139,30,-5); var d=Geo.Move(35,139,30,5); race.BreakPositionContinuity(); race.UpdateGnss(Frame(40,c.Lat,c.Lon),line);
        Check(!race.UpdateGnss(Frame(40.5,d.Lat,d.Lon),line),"outside line width ignored");
        race.BreakPositionContinuity(); Near(race.Elapsed(45),45,.001,"total time continues during disconnect");
        race.Stop(50); Near(race.Elapsed(100),50,.001,"stop freezes timer");
        Near(race.CurrentLap(100),39.75,.001,"stop preserves unfinished lap display");
        Check(RaceSession.FormatTime(3661.123)=="1:01:01.123","hour rollover");
        race.Start(0,true); race.UpdateGnss(Frame(2,a.Lat,a.Lon),line); race.UpdateGnss(Frame(2.5,b.Lat,b.Lon),line);
        Check(!race.AwaitingStartLine&&race.Laps.Count==0,"first automatic crossing starts lap instead of recording partial lap");
        race.UpdateGnss(Frame(10,a.Lat,a.Lon),line); race.UpdateGnss(Frame(10.5,b.Lat,b.Lon),line);
        Check(race.Laps.Count==1,"second automatic crossing finishes lap"); Near(race.Laps[0].Seconds,8,.001,"automatic start-to-finish time");
    }
    static void SolveTests()
    {
        var frames=Enumerable.Range(0,20).Select(i=>new TelemetryFrame(i/10d,(ulong)i,1,new Dictionary<string,double>{{"IMULink",1},{"GravityX",0},{"GravityY",0},{"GravityZ",9.81},{"GForceX",0},{"GForceY",0},{"GForceZ",0},{"GyroX",0},{"GyroY",0},{"GyroZ",0},{"Roll",3},{"Pitch",-2}}));
        var cal=LevelCalibrationMath.Capture(frames,"+X","+Z"); Near(cal.Matrix[0],1,1e-6,"level forward axis"); Near(cal.Matrix[8],1,1e-6,"level up axis"); Near(cal.RollZero,3,1e-6,"level roll zero");
        var dir=Path.Combine(Path.GetTempPath(),"EcoCaptureRoute",Guid.NewGuid().ToString("N"));Directory.CreateDirectory(dir);var path=Path.Combine(dir,"drive.csv");
        File.WriteAllText(path,"monotonic_us,Lat,Lon,GPSFix,GPSHAcc,GPSTow,GPSSpeed,LongAccel,LatAccel,VertAccel\n0,35,139,3,1,1,36,.1,.2,.3\n100000,35,139,3,1,1,36,.1,.2,.3\n1000000,35.0001,139.0001,3,1,2,54,.2,.3,.4\n");
        var route=RouteParser.Load(path); Check(route.Points.Count==2,"route deduplicates held GNSS values"); Near(route.Summary.AverageSpeedKmh,45,.01,"route average speed"); Check(route.Summary.DistanceKm>0,"route distance");
        var ordered=LogTransfer.OrderedPrimaryLogs(new[]{new RemoteLog("old.csv",100,999,false,2),new RemoteLog("new.csv",100,1,false,8),new RemoteLog("active.csv",100,2,true,9),new RemoteLog("new_can.csv",10,1,false,10)});
        Check(ordered.Select(x=>x.Name).SequenceEqual(new[]{"new.csv","old.csv","active.csv"}),"Solve selects newest closed log by SD directory order");
    }
    static void LinuxTests()
    {
        var root=Path.Combine(Path.GetTempPath(),"EcoCaptureSysfs",Guid.NewGuid().ToString("N"));
        var intf=Directory.CreateDirectory(Path.Combine(root,"device","interface"));
        File.WriteAllText(Path.Combine(root,"device","idVendor"),"303a\n"); File.WriteAllText(Path.Combine(root,"device","idProduct"),"4001\n");
        Check(LinuxUsbFactory.MatchesEcoLogger(intf),"Linux sysfs identity");
        File.WriteAllText(Path.Combine(root,"device","idVendor"),"1a86");
        Check(!LinuxUsbFactory.MatchesEcoLogger(intf),"Linux rejects programming UART");
        if(!OperatingSystem.IsLinux()) return;
        var path=new StringBuilder(256);
        Check(openpty(out var master,out var slave,path,IntPtr.Zero,IntPtr.Zero)==0,"Linux PTY created");
        try
        {
            using var wire=new LinuxUsbWire(path.ToString(),false);
            var tx=Encoding.ASCII.GetBytes("{\"test\":1}\r\n");
            Check(write(master,tx,(nuint)tx.Length)==tx.Length,"PTY peer write");
            var buffer=new byte[100]; var count=wire.Read(buffer); Check(Encoding.ASCII.GetString(buffer,0,count)==Encoding.ASCII.GetString(tx),"Linux termios read");
            wire.Write(tx); count=(int)read(master,buffer,(nuint)buffer.Length); Check(count==tx.Length,"Linux poll/write");
            close(master); master=-1;
            try { wire.Read(buffer); throw new Exception("Did not detect PTY detach"); } catch(IOException) { Check(true,"Linux HUP detection"); }
        }
        finally { if(master>=0) close(master); close(slave); }
    }
    [DllImport("libutil.so.1",SetLastError=true)] static extern int openpty(out int master,out int slave,StringBuilder name,IntPtr termios,IntPtr winsize);
    [DllImport("libc")] static extern int close(int fd);
    [DllImport("libc")] static extern nint read(int fd,byte[] buffer,nuint count);
    [DllImport("libc")] static extern nint write(int fd,byte[] buffer,nuint count);
    static async Task ConnectionTests()
    {
        var factory=new FakeFactory(); using var manager=new ConnectionManager(factory); manager.Start();
        await Until(()=>manager.Info.Samples>=4,4000); Check(manager.Info.State=="connected","handshake and stream");
        factory.Freeze=true; await Until(()=>manager.Info.Connections>=2,6000);
        Check(factory.Disposed>=1&&manager.Info.State=="connected","repeated stale snapshot forces live reconnect");
        factory.Drop=true; await Until(()=>manager.Info.Connections>=2,6000);
        await Until(()=>manager.Info.Connections>=3,6000);
        Check(factory.Disposed>=2,"failed wire disposed before reopen");
        Check(manager.Latest?.Get("GPSSpeed")==42,"fresh metadata after reconnect");
        var logs=await manager.QueryAsync("listLogs",new{offset=0}); Check(logs.GetProperty("files").GetArrayLength()==1,"command response interleaves with telemetry");
        manager.Pause(true); await Until(()=>manager.Info.State=="paused",2500);
        Check(manager.Latest==null&&factory.Disposed>=3,"pause clears values and releases handle");
        manager.Pause(false); await Until(()=>manager.Info.Connections>=4,4000);
        Check(factory.Writes.All(x=>!x.Contains("flashCfg")&&!x.Contains("setLoggerCfg")&&!x.Contains("\"log\"")),"no logger/SD/CAN mutation");
        Check(factory.Writes.Any(x=>x.Contains("\"rate\":10")),"stream capped at 10Hz");
        manager.Dispose(); Check(factory.Disposed==factory.Opened,"all handles released");
    }
    static async Task Until(Func<bool> condition,int ms)
    { var end=ConnectionManager.Now+ms/1000d; while(!condition()&&ConnectionManager.Now<end) await Task.Delay(20); Check(condition(),"bounded async wait"); }
    static async Task<int> Bench(string[] args)
    {
        var seconds=30d; var i=Array.IndexOf(args,"--seconds"); if(i>=0) seconds=double.Parse(args[i+1],System.Globalization.CultureInfo.InvariantCulture);
        var output=args[Array.IndexOf(args,"--output")+1];
        using var manager=new ConnectionManager(new WindowsUsbFactory()); manager.Start();
        var start=ConnectionManager.Now; TelemetryFrame? prior=null; var samples=0; var gaps=new List<double>(); var states=new List<object>(); var lastState="";
        var required=0; var firstTime=0d; var lastTime=0d;
        while(ConnectionManager.Now-start<seconds)
        {
            var info=manager.Info;
            if(info.State!=lastState) { states.Add(new{seconds=ConnectionManager.Now-start,info.State,info.Message,info.Port}); lastState=info.State; Console.WriteLine($"{ConnectionManager.Now-start:F2}s {info.State}: {info.Message} {info.Port}"); }
            var f=manager.Latest;
            if(f!=null&&!ReferenceEquals(f,prior))
            { if(prior!=null) gaps.Add(f.ReceivedAt-prior.ReceivedAt); prior=f; samples++; if(firstTime==0) firstTime=f.ReceivedAt; lastTime=f.ReceivedAt;
                if(f.Get("IMULink")==1&&f.Get("IMUErr")==0&&f.Get("SDPass")==1) required++; }
            await Task.Delay(10);
        }
        var report=new{samples,healthySamples=required,durationSeconds=seconds,sampleWindowSeconds=lastTime-firstTime,info=manager.Info,
            minimumInterval=gaps.Count>0?gaps.Min():0,maximumInterval=gaps.Count>0?gaps.Max():0,status=manager.Status,states,
            finalValues=prior?.Values.Where(x=>new[]{"GPSSats","GPSFix","IMULink","IMUErr","IMUHz","GNSSHz","SDPass","LogDrops"}.Contains(x.Key)).ToDictionary(x=>x.Key,x=>x.Value)};
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(output))!); File.WriteAllText(output,JsonSerializer.Serialize(report,new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine($"samples={samples}, healthy={required}, connections={manager.Info.Connections}"); return samples>=seconds*5&&required==samples?0:1;
    }
    sealed class FakeFactory : IWireFactory
    {
        public volatile bool Drop,Freeze; public int Opened,Disposed; public long DeviceUs; public ConcurrentBag<string> Writes=new();
        public IEnumerable<string> FindDevices()=>new[]{"FAKE"};
        public IWire Open(string device) { Opened++; return new FakeWire(this); }
    }
    sealed class FakeWire(FakeFactory factory) : IWire
    {
        readonly Queue<byte> data=new(); bool stream,disposed; double next; bool meta=true;
        public string Name=>"FAKE";
        void Queue(string json) { foreach(var b in Encoding.UTF8.GetBytes(json+"\r\n")) data.Enqueue(b); }
        void Sample()
        { if(!factory.Freeze) factory.DeviceUs+=100000; Queue("{\"s\":{\"schema\":1,\"monotonic_us\":"+factory.DeviceUs+",\"d\":[42,1]"+(meta?",\"meta\":[{\"nm\":\"GPSSpeed\",\"ut\":\"km/h\",\"min\":0,\"max\":200,\"prec\":1,\"sr\":10}]":"")+"}}"); meta=false; }
        public int Read(byte[] bytes)
        {
            if(factory.Drop) { factory.Drop=false; throw new IOException("detached"); }
            if(stream&&ConnectionManager.Now>=next) { Sample(); next=ConnectionManager.Now+.1; }
            var n=0; while(data.Count>0&&n<Math.Min(bytes.Length,17)) bytes[n++]=data.Dequeue();
            if(n==0) Thread.Sleep(5); return n;
        }
        public void Write(byte[] bytes)
        {
            var text=Encoding.UTF8.GetString(bytes); factory.Writes.Add(text);
            if(text.Contains("getVer")) Queue("{\"ver\":{\"fname\":\"logger_v1 test\",\"git_info\":\"test\"}}");
            if(text.Contains("getCapabilities")) Queue("{\"capabilities\":{\"flags\":[\"telemstream\"]}}");
            if(text.Contains("\"s\"")) { meta=true; Sample(); }
            if(text.Contains("setTelemetry")) { stream=!text.Contains("\"rate\":0"); meta=true; }
            if(text.Contains("listLogs")) Queue("{\"logs\":{\"files\":[{\"name\":\"drive.csv\",\"bytes\":10}],\"next\":null}}");
        }
        public void Dispose() { if(!disposed) { disposed=true; factory.Freeze=false; factory.Disposed++; } }
    }
}
