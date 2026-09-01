using System.Globalization;
using System.Text.Json;

namespace EcoCapture.Core;

public sealed record LevelCalibration(double RollZero, double PitchZero, double[] Matrix)
{
    public object ToProtocol() => new { enabled=true, rollZeroDeg=RollZero, pitchZeroDeg=PitchZero, matrixSensorToVehicle=Matrix };
}

public static class LevelCalibrationMath
{
    public static LevelCalibration Capture(IEnumerable<TelemetryFrame> source, string forwardAxis, string upAxis)
    {
        var frames=source.Where(f=>f.Get("IMULink")==1).ToArray();
        if(frames.Length<12) throw new InvalidOperationException("静止データが不足しています。");
        var gravity=Average(frames,"GravityX","GravityY","GravityZ");
        var norm=gravity.Length();
        if(!double.IsFinite(norm)||norm is <8 or >11.8) throw new InvalidOperationException("重力値を確認できません。");
        if(frames.Any(f=>Magnitude(f,"GForceX","GForceY","GForceZ")>.18 || Magnitude(f,"GyroX","GyroY","GyroZ")>5))
            throw new InvalidOperationException("車体を停止させて、動かさずに実行してください。");
        var up=gravity/norm; var desiredUp=Axis(upAxis);
        if(Dot(up,desiredUp)<0) up=-up;
        var desiredForward=Axis(forwardAxis);
        var forward=desiredForward-up*Dot(desiredForward,up);
        if(forward.Length()<.2) throw new InvalidOperationException("前方軸と上方軸は直交する組み合わせを選んでください。");
        forward=forward/forward.Length();
        var right=Cross(up,forward); right=right/right.Length();
        var roll=CircularMean(frames.Select(f=>f.Get("Roll")).Where(v=>v.HasValue).Select(v=>v!.Value));
        var pitch=CircularMean(frames.Select(f=>f.Get("Pitch")).Where(v=>v.HasValue).Select(v=>v!.Value));
        return new(roll,pitch,new[]{forward.X,forward.Y,forward.Z,right.X,right.Y,right.Z,up.X,up.Y,up.Z});
    }
    private static V Average(TelemetryFrame[] f,string x,string y,string z)=>new(f.Average(a=>a.Get(x)??double.NaN),f.Average(a=>a.Get(y)??double.NaN),f.Average(a=>a.Get(z)??double.NaN));
    private static double Magnitude(TelemetryFrame f,string x,string y,string z)
    { var v=new V(f.Get(x)??0,f.Get(y)??0,f.Get(z)??0); return v.Length(); }
    private static double CircularMean(IEnumerable<double> values)
    { var a=values.ToArray(); if(a.Length==0) throw new InvalidOperationException("姿勢角を確認できません。"); return Math.Atan2(a.Average(v=>Math.Sin(v*Math.PI/180)),a.Average(v=>Math.Cos(v*Math.PI/180)))*180/Math.PI; }
    private static V Axis(string s)=>s switch { "+X"=>new(1,0,0),"-X"=>new(-1,0,0),"+Y"=>new(0,1,0),"-Y"=>new(0,-1,0),"+Z"=>new(0,0,1),"-Z"=>new(0,0,-1),_=>new(1,0,0) };
    private static double Dot(V a,V b)=>a.X*b.X+a.Y*b.Y+a.Z*b.Z;
    private static V Cross(V a,V b)=>new(a.Y*b.Z-a.Z*b.Y,a.Z*b.X-a.X*b.Z,a.X*b.Y-a.Y*b.X);
    private readonly record struct V(double X,double Y,double Z)
    { public double Length()=>Math.Sqrt(X*X+Y*Y+Z*Z); public static V operator /(V a,double b)=>new(a.X/b,a.Y/b,a.Z/b); public static V operator *(V a,double b)=>new(a.X*b,a.Y*b,a.Z*b); public static V operator -(V a,V b)=>new(a.X-b.X,a.Y-b.Y,a.Z-b.Z); public static V operator -(V a)=>new(-a.X,-a.Y,-a.Z); }
}

public sealed record RoutePoint(double East, double North, double Seconds, double SpeedKmh,
    double LongAccel, double LatAccel, double TotalAccel, double Accuracy);
public sealed record RouteSummary(double DurationSeconds,double DistanceKm,double AverageSpeedKmh,double MaximumSpeedKmh,int Samples);
public sealed class RouteData
{
    public required string SourcePath { get; init; }
    public required IReadOnlyList<RoutePoint> Points { get; init; }
    public required RouteSummary Summary { get; init; }
    public string CorrectionFormula { get; init; }="";
}

public static class RouteParser
{
    public static RouteData Load(string path)
    {
        using var reader=new StreamReader(path);
        var header=reader.ReadLine()?.Split(',')??throw new FormatException("CSVに見出しがありません。");
        var index=header.Select((name,i)=>(name:name.Trim(),i)).GroupBy(x=>x.name,StringComparer.OrdinalIgnoreCase).ToDictionary(g=>g.Key,g=>g.First().i,StringComparer.OrdinalIgnoreCase);
        int I(string n)=>index.TryGetValue(n,out var i)?i:-1;
        int latI=I("Lat"),lonI=I("Lon"),timeI=I("monotonic_us"),towI=I("GPSTow"),speedI=I("GPSSpeed"),fixI=I("GPSFix"),accI=I("GPSHAcc");
        if(latI<0||lonI<0) throw new FormatException("緯度・経度を含むログを選択してください。");
        var longI=I("LongAccel"); if(longI<0) longI=I("GForceX");
        var lateralI=I("LatAccel"); if(lateralI<0) lateralI=I("GForceY");
        var vertI=I("VertAccel"); if(vertI<0) vertI=I("GForceZ");
        var raw=new List<(double lat,double lon,double sec,double speed,double lonG,double latG,double total,double acc)>();
        string? line; double? firstTime=null,lastTow=null; var row=0;
        while((line=reader.ReadLine())!=null)
        {
            row++; if(line.Length==0) continue; var c=line.Split(',');
            double N(int i,double fallback=double.NaN)=>i>=0&&i<c.Length&&double.TryParse(c[i],NumberStyles.Float,CultureInfo.InvariantCulture,out var v)&&double.IsFinite(v)?v:fallback;
            var lat=N(latI); var lon=N(lonI); var fix=N(fixI,3); var acc=N(accI,0); var tow=N(towI);
            if(!Geo.Valid(lat,lon)||fix<2||acc>50||(double.IsFinite(tow)&&lastTow==tow)) continue;
            if(double.IsFinite(tow)) lastTow=tow;
            var time=N(timeI,row*100000d)/1e6; firstTime??=time;
            var lg=N(longI,0); var tg=N(lateralI,0); var vg=N(vertI,0);
            raw.Add((lat,lon,time-firstTime.Value,N(speedI,0),lg,tg,Math.Sqrt(lg*lg+tg*tg+vg*vg),acc));
        }
        if(raw.Count<2) throw new FormatException("有効な走行位置が2点以上ありません。");
        var max=200000; var stride=Math.Max(1,(int)Math.Ceiling(raw.Count/(double)max));
        var origin=raw[0]; var points=new List<RoutePoint>(Math.Min(max,raw.Count)); double distance=0,priorE=0,priorN=0; var speeds=new List<double>();
        for(var i=0;i<raw.Count;i++)
        {
            var r=raw[i]; var o=Geo.Offset(origin.lat,origin.lon,r.lat,r.lon);
            if(i>0) { var segment=Math.Sqrt(Math.Pow(o.East-priorE,2)+Math.Pow(o.North-priorN,2)); if(segment<500) distance+=segment; }
            priorE=o.East; priorN=o.North; if(r.speed>=0&&r.speed<500) speeds.Add(r.speed);
            if(i%stride==0||i==raw.Count-1) points.Add(new(o.East,o.North,r.sec,r.speed,r.lonG,r.latG,r.total,r.acc));
        }
        var formula=""; var meta=Path.ChangeExtension(path,".meta.json");
        try { if(File.Exists(meta)) { using var d=JsonDocument.Parse(File.ReadAllText(meta)); if(d.RootElement.TryGetProperty("imu_level_correction",out var x)&&x.TryGetProperty("formula",out var f)) formula=f.GetString()??""; } } catch(Exception e) when(e is IOException or JsonException) { }
        return new RouteData { SourcePath=path,Points=points,Summary=new(raw[^1].sec,distance/1000,speeds.Count==0?0:speeds.Average(),speeds.Count==0?0:speeds.Max(),raw.Count),CorrectionFormula=formula };
    }
}
