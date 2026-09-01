namespace EcoCapture.Core;

/// <summary>Explicit, synthetic demonstration data. Never enabled by connection failures.</summary>
public sealed class DemoSource
{
    private readonly double _start;
    public DemoSource(double now) { _start = now; }
    public TelemetryFrame Frame(double now)
    {
        var t = now - _start; var a = t / 40;
        var position = Geo.Move(36.1517, 139.9196, 220 * Math.Sin(a), 340 * Math.Cos(a));
        var v = new Dictionary<string,double> {
            ["GPSSpeed"] = 48 + 13 * Math.Sin(a * 3), ["Speed"] = 49 + 13 * Math.Sin(a * 3),
            ["RPM"] = 4200 + 1600 * Math.Sin(a * 3), ["OilTemp"] = 83.6 + Math.Sin(t / 20),
            ["WaterTemp"] = 88.2, ["OilPress"] = 340 + 30 * Math.Sin(a), ["CHT"] = 126.4,
            ["EGT"] = 640, ["BatteryVolt"] = 13.82, ["Throttle"] = 35 + 20 * Math.Sin(a * 3),
            ["EngineLoad"] = 48, ["IntakeTemp"] = 28, ["AFR"] = 14.1, ["AFRValid"] = 1,
            ["GForceX"] = .14 * Math.Sin(t / 2), ["GForceY"] = .23 * Math.Cos(t / 3), ["GForceZ"] = .02,
            ["LongAccel"] = .14 * Math.Sin(t / 2), ["LatAccel"] = .23 * Math.Cos(t / 3), ["VertAccel"] = .02 * Math.Sin(t),
            ["GyroX"] = 0, ["GyroY"] = 0, ["GyroZ"] = -1.43, ["Yaw"] = Geo.Wrap360(a / Geo.Rad),
            ["Roll"] = 7.8 * Math.Cos(t / 3), ["Pitch"] = 2.1 * Math.Sin(t / 4), ["Altitude"] = 28.4,
            ["LevelRoll"] = 7.8 * Math.Cos(t / 3), ["LevelPitch"] = 2.1 * Math.Sin(t / 4),
            ["Lat"] = position.Lat, ["Lon"] = position.Lon, ["GPSFix"] = 3, ["GPSHAcc"] = 1.2,
            ["GNSSAge"] = 28, ["GPSTow"] = Math.Floor(t * 10) * 100, ["GPSSats"] = 18,
            ["GNSSHz"] = 10, ["GNSSLink"] = 1, ["UTCValid"] = 1, ["GNSSCNoTop4"] = 42.8,
            ["GNSSRetry"] = 0, ["IMULink"] = 1, ["IMUHz"] = 100, ["IMUCal"] = 255,
            ["IMUErr"] = 0, ["IMUTemp"] = 31, ["CpuTemp"] = 43.2, ["SDPass"] = 1,
            ["LogDrops"] = 0, ["CAN1Rx"] = Math.Floor(t * 60), ["CAN2Rx"] = 0, ["CANDrops"] = 0,
            ["Distance"] = t / 3600 * 48
        };
        return new(now, (ulong)(t * 1e6), 1, v);
    }
}
