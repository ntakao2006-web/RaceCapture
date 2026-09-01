using System.Text.Json;

namespace EcoCapture.Core;

public sealed record SensorDefinition(string Id, string Label, string Unit, string Source,
    double Min, double Max, int Precision, string Note = "");
public sealed record VehicleProfile(string Id, string Name, string Detail, int RpmMax, string[] DefaultSensors);

public static class Catalog
{
    public static readonly VehicleProfile[] Vehicles = {
        new("cub", "スーパーカブ / リトルカブ", "空冷単気筒 · 外付けセンサの受信値を表示", 10000,
            new[]{"GPSSpeed","Lat","Lon","RPM","OilTemp","CHT","BatteryVolt","GForceX","VertAccel","Roll","Altitude","Distance"}),
        new("roadster", "マツダ ロードスター", "型式未確定 · CAN変換設定はロガー側のまま", 9000,
            new[]{"GPSSpeed","Lat","Lon","RPM","WaterTemp","OilTemp","OilPress","Throttle","BatteryVolt","GForceX","GForceY","VertAccel"}),
        new("lx", "レクサス LX", "型式・年式未確定 · CAN変換設定はロガー側のまま", 7000,
            new[]{"GPSSpeed","Lat","Lon","RPM","WaterTemp","OilTemp","EngineLoad","Throttle","BatteryVolt","Pitch","Roll","VertAccel"}),
        new("none", "車載CAN接続なし", "GNSS / IMUのみ · 車載CAN項目を標準表示から除外", 10000,
            new[]{"GPSSpeed","Altitude","Lat","Lon","LongAccel","LatAccel","VertAccel","LevelRoll","LevelPitch"})
    };
    public static VehicleProfile Vehicle(string id) => Vehicles.FirstOrDefault(v => v.Id == id) ?? Vehicles[3];
    public static readonly SensorDefinition[] Sensors = {
        new("GPSSpeed","速度 · GNSS","km/h","GNSS",0,180,1),
        new("Speed","速度 · 車両","km/h","CAN",0,240,1),
        new("RPM","エンジン回転数","rpm","CAN",0,10000,0),
        new("WaterTemp","冷却水温","°C","CAN",-20,130,1),
        new("OilTemp","油温","°C","CAN",0,150,1),
        new("OilPress","油圧","kPa","CAN",0,1000,1),
        new("CHT","シリンダーヘッド温度","°C","CAN",0,250,1),
        new("EGT","排気温度","°C","CAN",0,1000,0),
        new("BatteryVolt","バッテリー電圧","V","CAN",0,18,2),
        new("Throttle","スロットル開度","%","CAN",0,100,1),
        new("EngineLoad","エンジン負荷","%","CAN",0,100,1),
        new("IntakeTemp","吸気温度","°C","CAN",-20,100,1),
        new("AFR","空燃比","AFR","CAN",8,22,2),
        new("GForceX","加速度 X · 重力除去","G","IMU",-2,2,2,"センサ座標です。車体軸ではありません。"),
        new("GForceY","加速度 Y · 重力除去","G","IMU",-2,2,2,"センサ座標です。車体軸ではありません。"),
        new("GForceZ","加速度 Z · 重力除去","G","IMU",-2,2,2),
        new("LongAccel","前後加速度 · 補正","G","IMU",-2,2,2),
        new("LatAccel","左右加速度 · 補正","G","IMU",-2,2,2),
        new("VertAccel","上下加速度 · 補正","G","IMU",-2,2,2),
        new("LevelRoll","ロール角 · 水平補正","°","IMU",-90,90,1),
        new("LevelPitch","ピッチ角 · 水平補正","°","IMU",-90,90,1),
        new("Roll","ロール角","°","IMU",-90,90,1),
        new("Pitch","ピッチ角","°","IMU",-90,90,1),
        new("Yaw","方位角 · IMU","°","IMU",0,360,1),
        new("Altitude","標高","m","GNSS",-100,4000,1),
        new("Distance","ラップ距離 · ロガー","km","GNSS",0,100,2),
        new("Lat","緯度","°","GNSS",-90,90,7),
        new("Lon","経度","°","GNSS",-180,180,7)
    };
    public static readonly SensorDefinition[] Diagnostics = {
        new("GPSFix","GNSS 測位状態","","GNSS",0,5,0),
        new("GPSSats","使用衛星数","基","GNSS",0,64,0),
        new("GPSHAcc","水平位置精度","m","GNSS",0,100,2),
        new("GPSVAcc","標高精度","m","GNSS",0,200,2),
        new("GNSSHz","GNSS 更新頻度","Hz","GNSS",0,25,1),
        new("GNSSAge","GNSS データ年齢","ms","GNSS",0,3000,0),
        new("GNSSLink","GNSS 通信","","GNSS",0,1,0),
        new("UTCValid","UTC 時刻有効","","GNSS",0,1,0),
        new("GNSSCNoTop4","GNSS 上位4衛星 C/N₀","dBHz","GNSS",0,60,1),
        new("GNSSRetry","GNSS 再設定回数","回","GNSS",0,100,0),
        new("IMULink","IMU 通信","","IMU",0,1,0),
        new("IMUHz","IMU 更新頻度","Hz","IMU",0,100,1),
        new("IMUCal","IMU 校正値","","IMU",0,255,0),
        new("IMUErr","IMU 内部エラー","","IMU",0,255,0),
        new("IMUTemp","IMU 温度","°C","IMU",-40,125,0),
        new("CpuTemp","CPU 温度","°C","SYSTEM",0,100,1),
        new("SDPass","SD 利用可能","","SYSTEM",0,1,0),
        new("LogDrops","SD 記録欠落","件","SYSTEM",0,1000,0),
        new("CAN1Rx","車載CAN 受信累計","件","CAN",0,1e9,0),
        new("CAN2Rx","センサCAN 受信累計","件","CAN",0,1e9,0),
        new("CANDrops","CAN 記録欠落","件","CAN",0,1000,0)
    };
}

public sealed class SensorPreference
{
    public bool Visible { get; set; }
    public bool Bar { get; set; }
    public int Precision { get; set; } = -1;
    public double? WarningAbove { get; set; }
}
public sealed class StartLine
{
    public bool Enabled { get; set; }
    public double Latitude { get; set; }
    public double Longitude { get; set; }
    public double Bearing { get; set; }
    public double WidthMeters { get; set; } = 30;
    public double MinimumLapSeconds { get; set; } = 15;
}
public sealed class LiveShareSettings
{
    public bool Enabled { get; set; }
    public string ServerUrl { get; set; } = "";
    public string ViewerUrl { get; set; } = "";
    public string Channel { get; set; } = LiveShareUrl.NewChannel();
}
public sealed class AppSettings
{
    public int Version { get; set; } = 5;
    public string Vehicle { get; set; } = "none";
    public double MapSpanKm { get; set; } = 1;
    public bool MapPale { get; set; } = true;
    public int Columns { get; set; } = 3;
    public bool GnssEnabled { get; set; } = true;
    public bool ImuEnabled { get; set; } = true;
    public bool CanEnabled { get; set; }
    public bool ImuAid { get; set; }
    public string ForwardAxis { get; set; } = "+X";
    public string UpAxis { get; set; } = "+Z";
    public StartLine StartLine { get; set; } = new();
    public LiveShareSettings LiveShare { get; set; } = new();
    public Dictionary<string, Dictionary<string, SensorPreference>> Profiles { get; set; } = new();
    public Dictionary<string, SensorPreference> CurrentSensors()
    {
        if (!Profiles.TryGetValue(Vehicle, out var prefs))
            Profiles[Vehicle] = prefs = new();
        var defaults = Catalog.Vehicle(Vehicle).DefaultSensors;
        foreach (var s in Catalog.Sensors)
            if (!prefs.ContainsKey(s.Id)) prefs[s.Id] = new() { Visible = defaults.Contains(s.Id) };
        return prefs;
    }
    public bool SourceEnabled(string source) => source switch { "GNSS" => GnssEnabled, "IMU" => ImuEnabled, "CAN" => CanEnabled, _ => true };
    public void Validate()
    {
        if (Version < 2)
        {
            foreach (var profile in Profiles?.Values.Where(p=>p!=null) ?? Enumerable.Empty<Dictionary<string,SensorPreference>>())
                if (profile.TryGetValue("VertAccel",out var vertical)) vertical.Visible=true;
            Version=2;
        }
        if (Version < 3)
        {
            foreach (var profile in Profiles?.Values.Where(p=>p!=null) ?? Enumerable.Empty<Dictionary<string,SensorPreference>>())
                foreach (var id in new[]{"Lat","Lon"})
                    if (profile.TryGetValue(id,out var coordinate)) coordinate.Visible=true;
            Version=3;
        }
        Vehicle = Catalog.Vehicle(Vehicle).Id;
        if (Vehicle == "none") CanEnabled = false;
        if (!new[]{0.5,1d,2d,4d,8d}.Contains(MapSpanKm)) MapSpanKm = 1;
        Columns = Math.Clamp(Columns, 1, 3);
        var axes = new[]{"+X","-X","+Y","-Y","+Z","-Z"};
        if (!axes.Contains(ForwardAxis)) ForwardAxis = "+X";
        if (!axes.Contains(UpAxis)) UpAxis = "+Z";
        if (ForwardAxis[1] == UpAxis[1]) ImuAid = false;
        StartLine ??= new();
        if (!Geo.Valid(StartLine.Latitude, StartLine.Longitude)) StartLine = new();
        StartLine.Bearing = double.IsFinite(StartLine.Bearing) ? Geo.Wrap360(StartLine.Bearing) : 0;
        StartLine.WidthMeters = double.IsFinite(StartLine.WidthMeters) ? Math.Clamp(StartLine.WidthMeters, 5, 200) : 30;
        StartLine.MinimumLapSeconds = double.IsFinite(StartLine.MinimumLapSeconds) ? Math.Clamp(StartLine.MinimumLapSeconds, 5, 3600) : 15;
        LiveShare ??= new();
        LiveShare.ServerUrl = LiveShareService.Configured ? LiveShareService.DatabaseUrl : (LiveShare.ServerUrl ?? "").Trim().TrimEnd('/');
        LiveShare.ViewerUrl = LiveShareService.Configured ? LiveShareService.ViewerUrl : (LiveShare.ViewerUrl ?? "").Trim().TrimEnd('/');
        LiveShare.Channel = (LiveShare.Channel ?? "").Trim().ToLowerInvariant();
        if (!LiveShareUrl.ValidChannel(LiveShare.Channel)) LiveShare.Channel = LiveShareUrl.NewChannel();
        if (Version < 5) Version = 5;
        Profiles ??= new();
        foreach (var p in Profiles.Values.Where(p => p != null))
            foreach (var s in p.Values.Where(s => s != null))
            { s.Precision = Math.Clamp(s.Precision, -1, 7); if (s.WarningAbove.HasValue && !double.IsFinite(s.WarningAbove.Value)) s.WarningAbove = null; }
        foreach (var key in Profiles.Keys.ToArray())
            if (Profiles[key] == null || Profiles[key].Any(p => p.Value == null)) Profiles.Remove(key);
        CurrentSensors();
    }
}

public static class SettingsStore
{
    private static readonly JsonSerializerOptions Options = new() { WriteIndented = true };
    public static AppSettings Load(string path, out string? warning)
    {
        warning = null;
        if (!File.Exists(path)) return new();
        try { var s = JsonSerializer.Deserialize<AppSettings>(File.ReadAllText(path)) ?? new(); s.Validate(); return s; }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException or JsonException or ArgumentException or NullReferenceException)
        { warning = "設定を読めないため初期値で起動しました。元ファイルは保持しています。"; return new(); }
    }
    public static void Save(string path, AppSettings settings)
    {
        settings.Validate();
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var tmp = path + ".tmp";
        File.WriteAllText(tmp, JsonSerializer.Serialize(settings, Options));
        File.Move(tmp, path, true);
    }
}
