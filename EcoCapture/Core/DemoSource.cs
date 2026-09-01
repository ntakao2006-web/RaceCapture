namespace EcoCapture.Core;

/// <summary>Explicit, synthetic demonstration data. Never enabled by connection failures.</summary>
public sealed class DemoSource
{
    public const uint LoggerSchema = 83;
    public static readonly string[] LoggerChannels = {
        "RPM","Speed","WaterTemp","OilPress","Lat","Lon","GPSSpeed","Altitude",
        "GPSHAcc","GPSSats","GPSFix","GNSSHz","UTCValid","AccelX","AccelY","AccelZ",
        "GyroX","GyroY","GyroZ","Yaw","Pitch","Roll","GForceX","GForceY",
        "GForceZ","GravityX","GravityY","GravityZ","IMUTemp","IMUCal","IMULink","IMUErr",
        "IMUHz","GNSSLink","LapCount","LapTime","PredTime","ElapsedTime","CurrentLap","Distance",
        "SessionTime","Throttle","EngineLoad","IntakeTemp","BatteryVolt","OilTemp","CHT","EGT",
        "AFRRaw","AFR","AFRValid","CANGPIO","WheelHz","CpuTemp","SDPass","LogDrops",
        "CAN1Rx","CAN2Rx","CANDrops","LuaOK","GPSTow","GPSUTC","GPSTAcc","PPSAge",
        "GNSSAcq","GNSSTrack","GNSSCNoMax","GNSSCNoTop4","RFNoise","RFAGC","RFJam","RFCW",
        "GNSSRetry","GNSSAge","GNSSBad","LevelRoll","LevelPitch","LongAccel","LatAccel","VertAccel",
        "GPSVAcc"
    };
    private readonly double _start;
    private readonly long _utcStartMs;
    public DemoSource(double now,DateTimeOffset? utc=null)
    { _start = now; _utcStartMs=(utc??DateTimeOffset.UtcNow).ToUnixTimeMilliseconds(); }
    public TelemetryFrame Frame(double now)
    {
        var t = now - _start; var phase = t * 3 / 40;
        var speed = 48 + 13 * Math.Sin(phase); // km/h
        const double radius = 260, gravity = 9.80665, phaseRate = 3d / 40;
        var travel = 48 / 3.6 * t + 13 / 3.6 / phaseRate * (1 - Math.Cos(phase));
        var angle = travel / radius;
        var speedMps = speed / 3.6;
        var longAccel = 13 / 3.6 * phaseRate * Math.Cos(phase) / gravity;
        var latAccel = speedMps * speedMps / radius / gravity;
        var position = Geo.Move(36.1517, 139.9196, radius * Math.Sin(angle), radius * Math.Cos(angle));
        var roll = 7.8 * Math.Cos(t / 3); var pitch = 2.1 * Math.Sin(t / 4);
        var rollRad=roll*Geo.Rad; var pitchRad=pitch*Geo.Rad;
        var gravityX=-gravity*Math.Sin(pitchRad); var gravityY=gravity*Math.Sin(rollRad)*Math.Cos(pitchRad);
        var gravityZ=gravity*Math.Cos(rollRad)*Math.Cos(pitchRad);
        var vertAccel=.02*Math.Sin(t); var circumference=2*Math.PI*radius;
        var lapCount=Math.Floor(travel/circumference); var lapDistance=travel-lapCount*circumference;
        var utcMs=_utcStartMs+(long)Math.Max(0,t*1000); var gpsTow=((utcMs-315964800000L)%604800000L+604800000L)%604800000L;
        var v = new Dictionary<string,double>(StringComparer.Ordinal) {
            ["GPSSpeed"] = speed, ["Speed"] = speed,
            ["RPM"] = 4200 + 1600 * Math.Sin(phase), ["OilTemp"] = 83.6 + Math.Sin(t / 20),
            ["WaterTemp"] = 88.2, ["OilPress"] = 340 + 30 * Math.Sin(angle), ["CHT"] = 126.4,
            ["EGT"] = 640, ["BatteryVolt"] = 13.82, ["Throttle"] = 35 + 20 * Math.Sin(phase),
            ["EngineLoad"] = 48, ["IntakeTemp"] = 28, ["AFRRaw"] = 14.1, ["AFR"] = 14.1, ["AFRValid"] = 1,
            ["AccelX"] = gravityX+longAccel*gravity, ["AccelY"] = gravityY+latAccel*gravity, ["AccelZ"] = gravityZ+vertAccel*gravity,
            ["GravityX"] = gravityX, ["GravityY"] = gravityY, ["GravityZ"] = gravityZ,
            ["GForceX"] = longAccel, ["GForceY"] = latAccel, ["GForceZ"] = vertAccel,
            ["LongAccel"] = longAccel, ["LatAccel"] = latAccel, ["VertAccel"] = vertAccel,
            ["GyroX"] = 0, ["GyroY"] = 0, ["GyroZ"] = -speedMps / radius / Geo.Rad, ["Yaw"] = Geo.Wrap360(angle / Geo.Rad + 90),
            ["Roll"] = roll, ["Pitch"] = pitch, ["Altitude"] = 28.4,
            ["LevelRoll"] = roll, ["LevelPitch"] = pitch,
            ["Lat"] = position.Lat, ["Lon"] = position.Lon, ["GPSFix"] = 3, ["GPSHAcc"] = 1.2,
            ["GPSVAcc"] = 1.8, ["GNSSAge"] = 28, ["GPSTow"] = gpsTow, ["GPSUTC"] = utcMs/1000d,
            ["GPSTAcc"] = 20, ["PPSAge"] = (t*1000)%1000, ["GPSSats"] = 18,
            ["GNSSHz"] = 10, ["GNSSLink"] = 1, ["UTCValid"] = 1, ["GNSSCNoTop4"] = 42.8,
            ["GNSSAcq"] = 24, ["GNSSTrack"] = 22, ["GNSSCNoMax"] = 46, ["RFNoise"] = 70,
            ["RFAGC"] = 30, ["RFJam"] = 0, ["RFCW"] = 7, ["GNSSRetry"] = 0, ["GNSSBad"] = 0,
            ["IMULink"] = 1, ["IMUHz"] = 100, ["IMUCal"] = 255,
            ["IMUErr"] = 0, ["IMUTemp"] = 31, ["CpuTemp"] = 43.2, ["SDPass"] = 1,
            ["LogDrops"] = 0, ["CAN1Rx"] = Math.Floor(t * 60), ["CAN2Rx"] = 0, ["CANDrops"] = 0,
            ["LuaOK"] = 1, ["CANGPIO"] = 0, ["WheelHz"] = speedMps/(2*Math.PI*.3),
            ["LapCount"] = lapCount, ["CurrentLap"] = lapCount+1, ["LapTime"] = circumference/(48/3.6)/60,
            ["ElapsedTime"] = t/60, ["PredTime"] = .04*Math.Sin(phase), ["SessionTime"] = t/60,
            ["Distance"] = lapDistance / 1000
        };
        return new(now, (ulong)Math.Max(0,t * 1e6), LoggerSchema, v);
    }
}
