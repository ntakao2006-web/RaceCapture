namespace EcoCapture.Core;

public static class Geo
{
    public const double Radius = 6378137;
    public const double Rad = Math.PI / 180;
    public static bool Valid(double lat, double lon) => double.IsFinite(lat) && double.IsFinite(lon) && Math.Abs(lat) <= 85.05112878 && Math.Abs(lon) <= 180;
    public static double Wrap360(double a) => (a % 360 + 360) % 360;
    public static double AngleDelta(double a, double b) => (b - a + 540) % 360 - 180;
    public static (double East, double North) Offset(double lat0, double lon0, double lat, double lon) =>
        (AngleDelta(lon0, lon) * Rad * Radius * Math.Cos(lat0 * Rad), (lat - lat0) * Rad * Radius);
    public static (double Lat, double Lon) Move(double lat, double lon, double east, double north) =>
        (lat + north / Radius / Rad, ((lon + east / (Radius * Math.Cos(lat * Rad)) / Rad + 540) % 360) - 180);
    public static (double X, double Y) Tile(double lat, double lon, int zoom)
    {
        var n = Math.Pow(2, zoom);
        var r = Math.Clamp(lat, -85.05112878, 85.05112878) * Rad;
        return ((lon + 180) / 360 * n, (1 - Math.Log(Math.Tan(r) + 1 / Math.Cos(r)) / Math.PI) / 2 * n);
    }
    public static double MetersPerPixel(double lat, int zoom) => Math.Cos(lat * Rad) * 2 * Math.PI * Radius / (256 * Math.Pow(2, zoom));
    public static int ZoomForSpan(double lat, double spanMeters, double pixels) =>
        Math.Clamp((int)Math.Round(Math.Log2(Math.Cos(lat * Rad) * 2 * Math.PI * Radius * pixels / (256 * spanMeters))), 5, 18);
}

public sealed record Position(double Latitude, double Longitude, double Bearing, double SpeedMps,
    double AccuracyMeters, double UpdatedAt, double GnssAt, string Mode, bool Estimated);

/// <summary>Short GNSS gaps only. Gyro/linear acceleration assistance requires explicit mount-axis confirmation.</summary>
public sealed class PositionEstimator
{
    public Position? Current { get; private set; }
    private double _lastAt = -1, _lastTow = double.NaN, _lastRawLat, _lastRawLon, _lastRawAt = -1;
    private double _heading, _speed;
    private ulong _deviceUs;
    private bool _haveCourse;
    public void Reset() { Current = null; _lastAt = -1; _lastRawAt = -1; _lastTow = double.NaN; _deviceUs = 0; _haveCourse = false; _heading = 0; _speed = 0; }
    public void Update(TelemetryFrame f, AppSettings settings)
    {
        if (!settings.GnssEnabled) return;
        if (_deviceUs > f.DeviceUs) Reset();
        _deviceUs = f.DeviceUs;
        var dt = _lastAt >= 0 ? Math.Clamp(f.ReceivedAt - _lastAt, 0, .5) : 0;
        _lastAt = f.ReceivedAt;
        var aid = settings.ImuAid && settings.ImuEnabled && f.Get("IMULink") == 1 && f.Get("IMUErr") == 0;
        var gyro = Axis(f, "Gyro", settings.UpAxis);
        var accel = Axis(f, "GForce", settings.ForwardAxis);
        if (aid && _haveCourse && dt > 0 && gyro.HasValue)
            _heading = Geo.Wrap360(_heading - gyro.Value * dt); // ENU right-hand rotation vs clockwise compass bearing.
        var lat = f.Get("Lat"); var lon = f.Get("Lon");
        var hacc = f.Get("GPSHAcc") ?? 100;
        var tow = f.Get("GPSTow") ?? f.DeviceUs / 1000d;
        var valid = lat.HasValue && lon.HasValue && Geo.Valid(lat.Value, lon.Value) &&
            f.Get("GPSFix") >= 2 && (f.Get("GNSSAge") ?? 0) < 1200 && hacc is >= 0 and <= 100;
        if (valid && tow != _lastTow)
        {
            var courseDt = f.ReceivedAt - _lastRawAt;
            var courseUpdated = false;
            if (_lastRawAt >= 0 && courseDt > 0 && courseDt < 3)
            {
                var (east, north) = Geo.Offset(_lastRawLat, _lastRawLon, lat!.Value, lon!.Value);
                var distance = Math.Sqrt(east * east + north * north);
                if (distance > Math.Max(100, courseDt * 100 + hacc * 3)) return;
                if (distance > Math.Max(1, hacc * .15) && f.Get("GPSSpeed") > 5)
                {
                    var course = Geo.Wrap360(Math.Atan2(east, north) / Geo.Rad);
                    _heading = _haveCourse ? Geo.Wrap360(_heading + Geo.AngleDelta(_heading, course) * .35) : course;
                    _haveCourse = true;
                    courseUpdated = true;
                }
            }
            _speed = Math.Clamp((f.Get("GPSSpeed") ?? 0) / 3.6, 0, 100);
            var outLat = lat!.Value; var outLon = lon!.Value;
            if (Current != null && aid && _haveCourse && f.ReceivedAt - Current.GnssAt < 1.5)
            {
                var predicted = Geo.Move(Current.Latitude, Current.Longitude,
                    _speed * Math.Sin(_heading * Geo.Rad) * dt, _speed * Math.Cos(_heading * Geo.Rad) * dt);
                var correction = Geo.Offset(predicted.Lat, predicted.Lon, outLat, outLon);
                (outLat, outLon) = Geo.Move(predicted.Lat, predicted.Lon, correction.East * .7, correction.North * .7);
            }
            Current = new(outLat, outLon, _heading, _speed, Math.Max(.5, hacc), f.ReceivedAt, f.ReceivedAt,
                aid && _haveCourse ? "GNSS + IMU" : "GNSS", false);
            _lastTow = tow;
            // Accumulate displacement across 10 Hz fixes so low-speed motion can establish a course.
            if (_lastRawAt < 0 || courseUpdated || courseDt >= 2)
            { _lastRawLat = lat.Value; _lastRawLon = lon.Value; _lastRawAt = f.ReceivedAt; }
        }
        else if (Current != null && aid && _haveCourse && gyro.HasValue && dt > 0 && f.ReceivedAt - Current.GnssAt <= 3)
        {
            // No long inertial navigation claim: bounded to 3 seconds, with growing uncertainty.
            if (accel.HasValue) _speed = Math.Clamp(_speed + Math.Clamp(accel.Value * 9.80665, -8, 8) * dt, 0, 100);
            var next = Geo.Move(Current.Latitude, Current.Longitude,
                _speed * Math.Sin(_heading * Geo.Rad) * dt, _speed * Math.Cos(_heading * Geo.Rad) * dt);
            Current = Current with { Latitude = next.Lat, Longitude = next.Lon, Bearing = _heading, SpeedMps = _speed,
                UpdatedAt = f.ReceivedAt, AccuracyMeters = Current.AccuracyMeters + dt * 5, Mode = "IMU 短時間補完", Estimated = true };
        }
    }
    private static double? Axis(TelemetryFrame f, string prefix, string axis) =>
        axis.Length == 2 ? f.Get(prefix + axis[1]) * (axis[0] == '-' ? -1 : 1) : null;
    public bool Usable(double now) => Current != null && now - Current.UpdatedAt <= 1.25 && now - Current.GnssAt <= 3;
}

public sealed record LapResult(int Number, double Seconds, double TotalSeconds, string Source);
public sealed class RaceSession
{
    public bool Running { get; private set; }
    public double StartedAt { get; private set; }
    public DateTimeOffset StartedUtc { get; private set; }
    public bool AwaitingStartLine { get; private set; }
    private double _lapAt, _stoppedAt;
    private (double Lat, double Lon, double At)? _previous;
    public List<LapResult> Laps { get; } = new();
    public double Elapsed(double now) => StartedAt < 0 ? 0 : Math.Max(0, (Running ? now : _stoppedAt) - StartedAt);
    public double CurrentLap(double now) => StartedAt >= 0 && !AwaitingStartLine ? Math.Max(0, (Running ? now : _stoppedAt) - _lapAt) : 0;
    public double? Best => Laps.Count == 0 ? null : Laps.Min(x => x.Seconds);
    public RaceSession() { StartedAt = -1; }
    public void Start(double now, bool automatic = false) { Running = true; AwaitingStartLine = automatic; StartedAt = _lapAt = now; StartedUtc = DateTimeOffset.Now; Laps.Clear(); _previous = null; }
    public void Stop(double now) { if (Running) { _stoppedAt = now; Running = false; _previous = null; } }
    public void BreakPositionContinuity() => _previous = null;
    public bool Mark(double now, string source = "手動")
    {
        if (!Running || now - _lapAt < 1) return false;
        if (AwaitingStartLine) { AwaitingStartLine = false; _lapAt = now; return true; }
        Laps.Add(new(Laps.Count + 1, now - _lapAt, now - StartedAt, source)); _lapAt = now; return true;
    }
    public bool UpdateGnss(TelemetryFrame f, StartLine line)
    {
        if (!Running || !line.Enabled || f.Get("GPSFix") < 2 || f.Get("GPSFix") == null ||
            (f.Get("GNSSAge") ?? 0) > 500 || (f.Get("GPSHAcc") ?? 100) > 25 ||
            f.Get("Lat") is not double lat || f.Get("Lon") is not double lon || !Geo.Valid(lat, lon))
        { _previous = null; return false; }
        var previous = _previous;
        _previous = (lat, lon, f.ReceivedAt);
        if (!previous.HasValue || f.ReceivedAt - previous.Value.At is <= 0 or > 1.0) return false;
        var a = Geo.Offset(line.Latitude, line.Longitude, previous.Value.Lat, previous.Value.Lon);
        var b = Geo.Offset(line.Latitude, line.Longitude, lat, lon);
        var distance = Math.Sqrt(Math.Pow(b.East - a.East, 2) + Math.Pow(b.North - a.North, 2));
        if (distance > Math.Max(30, (f.ReceivedAt - previous.Value.At) * 100)) return false;
        var nx = Math.Sin(line.Bearing * Geo.Rad); var ny = Math.Cos(line.Bearing * Geo.Rad);
        var sa = a.East * nx + a.North * ny; var sb = b.East * nx + b.North * ny;
        if (!(sa < 0 && sb >= 0)) return false;
        var fraction = -sa / (sb - sa);
        var along = (a.East + (b.East - a.East) * fraction) * ny - (a.North + (b.North - a.North) * fraction) * nx;
        var at = previous.Value.At + (f.ReceivedAt - previous.Value.At) * fraction;
        if (Math.Abs(along) > line.WidthMeters / 2 || (!AwaitingStartLine && at - _lapAt < line.MinimumLapSeconds)) return false;
        return Mark(at, "GNSS");
    }
    public static string FormatTime(double? seconds, bool milliseconds = true)
    {
        if (!seconds.HasValue || !double.IsFinite(seconds.Value) || seconds < 0) return "--:--.---";
        var ms = (long)Math.Round(seconds.Value * 1000);
        var h = ms / 3600000; var m = ms / 60000 % 60; var s = ms / 1000 % 60;
        var result = h > 0 ? $"{h}:{m:00}:{s:00}" : $"{m:00}:{s:00}";
        return milliseconds ? result + $".{ms % 1000:000}" : result;
    }
}
