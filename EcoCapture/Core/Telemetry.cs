using System.Text;
using System.Text.Json;

namespace EcoCapture.Core;

public sealed record ChannelMeta(string Name, string Unit, double Min, double Max, int Precision, int Rate);

public sealed record TelemetryFrame(double ReceivedAt, ulong DeviceUs, uint Schema,
    IReadOnlyDictionary<string, double> Values)
{
    public double? Get(string name) => Values.TryGetValue(name, out var v) && double.IsFinite(v) ? v : null;
    public bool Fresh(double now) => now >= ReceivedAt && now - ReceivedAt <= 1.25;
}

/// <summary>One bounded UTF-8 JSON line at a time. Never grows indefinitely on a damaged stream.</summary>
public sealed class LineFramer
{
    public const int MaxBytes = 65536;
    private readonly byte[] _bytes = new byte[MaxBytes];
    private int _length;
    private bool _discard;
    public int DroppedLines { get; private set; }
    public void Reset() { _length = 0; _discard = false; }
    public void Push(ReadOnlySpan<byte> bytes, Action<string> line)
    {
        foreach (var b in bytes)
        {
            if (b == 10)
            {
                if (!_discard && _length > 0)
                    line(Encoding.UTF8.GetString(_bytes, 0, _length).TrimEnd('\r'));
                _length = 0; _discard = false;
            }
            else if (!_discard)
            {
                if (_length == MaxBytes) { _discard = true; _length = 0; DroppedLines++; }
                else _bytes[_length++] = b;
            }
        }
    }
}

/// <summary>RaceCapture sparse samples: valid values followed by ceil(channel-count / 32) bitmaps.</summary>
public sealed class RcpDecoder
{
    public IReadOnlyList<ChannelMeta> Metadata { get; private set; } = Array.Empty<ChannelMeta>();
    private uint? _schema;
    public void Reset() { Metadata = Array.Empty<ChannelMeta>(); _schema = null; }
    public void SetMetadata(JsonElement array)
    {
        if (array.ValueKind != JsonValueKind.Array || array.GetArrayLength() is < 1 or > 128)
            throw new FormatException("Invalid channel metadata size");
        var result = new List<ChannelMeta>();
        var names = new HashSet<string>(StringComparer.Ordinal);
        foreach (var e in array.EnumerateArray())
        {
            var name = e.GetProperty("nm").GetString() ?? "";
            if (name.Length is < 1 or > 64 || !names.Add(name)) throw new FormatException("Invalid channel name");
            result.Add(new(name, e.TryGetProperty("ut", out var u) ? u.GetString() ?? "" : "",
                Number(e, "min", 0), Number(e, "max", 100), (int)Math.Clamp(Number(e, "prec", 1), 0, 7),
                (int)Math.Clamp(Number(e, "sr", 10), 1, 1000)));
        }
        Metadata = result;
    }
    private static double Number(JsonElement e, string key, double fallback) =>
        e.TryGetProperty(key, out var v) && v.TryGetDouble(out var d) && double.IsFinite(d) ? d : fallback;

    public TelemetryFrame Decode(JsonElement sample, double receivedAt)
    {
        var hasMeta = sample.TryGetProperty("meta", out var meta);
        var schema = sample.TryGetProperty("schema", out var s) ? s.GetUInt32() : 0;
        if (!hasMeta && _schema.HasValue && _schema.Value != schema)
            throw new FormatException("Schema changed without metadata");
        if (hasMeta) SetMetadata(meta);
        var count = Metadata.Count;
        if (count == 0) throw new FormatException("Sample before metadata");
        var data = sample.GetProperty("d");
        if (data.ValueKind != JsonValueKind.Array) throw new FormatException("Invalid sample data");
        var masks = (count + 31) / 32;
        var valueCount = data.GetArrayLength() - masks;
        if (valueCount < 0 || valueCount > count) throw new FormatException("Invalid sample length");
        var flags = new uint[masks];
        var expected = 0;
        for (var i = 0; i < masks; i++)
        {
            flags[i] = data[valueCount + i].GetUInt32();
            expected += System.Numerics.BitOperations.PopCount(flags[i]);
        }
        if (count % 32 != 0 && (flags[^1] >> (count % 32)) != 0) throw new FormatException("Bitmap beyond schema");
        if (expected != valueCount) throw new FormatException("Bitmap/value mismatch");
        var values = new Dictionary<string, double>(StringComparer.Ordinal);
        var cursor = 0;
        for (var i = 0; i < count; i++)
            if ((flags[i / 32] & (1u << (i % 32))) != 0)
            {
                var v = data[cursor++].GetDouble();
                if (!double.IsFinite(v)) throw new FormatException("Non-finite sample");
                values.Add(Metadata[i].Name, v);
            }
        // Missing channels are intentionally absent: never hold a disconnected sensor's old value.
        _schema = schema;
        var deviceUs = sample.TryGetProperty("monotonic_us", out var t) ? t.GetUInt64() :
            (sample.TryGetProperty("t", out var ms) ? ms.GetUInt64() * 1000 : 0);
        return new(receivedAt, deviceUs, schema, values);
    }
}
