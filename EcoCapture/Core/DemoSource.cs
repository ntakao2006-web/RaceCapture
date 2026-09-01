namespace EcoCapture.Core;

/// <summary>Explicit, synthetic demonstration data. Never enabled by connection failures.</summary>
public sealed class DemoSource
{
    private readonly double _start;
    public DemoSource(double now) { _start = now; }
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
        var v = new Dictionary<string,double> {
            ["GPSSpeed"] = speed, ["Speed"] = speed,
            ["RPM"] = 4200 + 1600 * Math.Sin(phase), ["OilTemp"] = 83.6 + Math.Sin(t / 20),
            ["WaterTemp"] = 88.2, ["OilPress"] = 340 + 30 * Math.Sin(angle), ["CHT"] = 126.4,
            ["EGT"] = 640, ["BatteryVolt"] = 13.82, ["Throttle"] = 35 + 20 * Math.Sin(phase),
            ["EngineLoad"] = 48, ["IntakeTemp"] = 28, ["AFR"] = 14.1, ["AFRValid"] = 1,
            ["GForceX"] = longAccel, ["GForceY"] = latAccel, ["GForceZ"] = .02,
            ["LongAccel"] = longAccel, ["LatAccel"] = latAccel, ["VertAccel"] = .02 * Math.Sin(t),
            ["GyroX"] = 0, ["GyroY"] = 0, ["GyroZ"] = -speedMps / radius / Geo.Rad, ["Yaw"] = Geo.Wrap360(angle / Geo.Rad + 90),
            ["Roll"] = 7.8 * Math.Cos(t / 3), ["Pitch"] = 2.1 * Math.Sin(t / 4), ["Altitude"] = 28.4,
            ["LevelRoll"] = 7.8 * Math.Cos(t / 3), ["LevelPitch"] = 2.1 * Math.Sin(t / 4),
            ["Lat"] = position.Lat, ["Lon"] = position.Lon, ["GPSFix"] = 3, ["GPSHAcc"] = 1.2,
            ["GNSSAge"] = 28, ["GPSTow"] = Math.Floor(t * 10) * 100, ["GPSSats"] = 18,
            ["GNSSHz"] = 10, ["GNSSLink"] = 1, ["UTCValid"] = 1, ["GNSSCNoTop4"] = 42.8,
            ["GNSSRetry"] = 0, ["IMULink"] = 1, ["IMUHz"] = 100, ["IMUCal"] = 255,
            ["IMUErr"] = 0, ["IMUTemp"] = 31, ["CpuTemp"] = 43.2, ["SDPass"] = 1,
            ["LogDrops"] = 0, ["CAN1Rx"] = Math.Floor(t * 60), ["CAN2Rx"] = 0, ["CANDrops"] = 0,
            ["Distance"] = travel / 1000
        };
        return new(now, (ulong)(t * 1e6), 1, v);
    }
}
