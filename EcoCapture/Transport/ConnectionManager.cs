using System.Collections.Concurrent;
using System.Diagnostics;
using System.Text;
using System.Text.Json;
using EcoCapture.Core;

namespace EcoCapture.Transport;

public sealed record ConnectionInfo(string State, string Message, string Port, int Connections, long Samples, int BadFrames, string Firmware);

public sealed class ConnectionManager : IDisposable
{
    public static double Now => Stopwatch.GetTimestamp() / (double)Stopwatch.Frequency;
    private readonly IWireFactory _factory;
    private readonly CancellationTokenSource _cancel = new();
    private readonly AutoResetEvent _wake = new(false);
    private readonly ConcurrentQueue<CommandRequest> _commands = new();
    private Task? _worker;
    private int _reconnect, _paused, _disposed;
    private TelemetryFrame? _latest;
    private ConnectionInfo _info = new("waiting", "EcoLoggerのUSB接続を待っています", "", 0, 0, 0, "");
    public TelemetryFrame? Latest => Volatile.Read(ref _latest);
    public ConnectionInfo Info => Volatile.Read(ref _info);
    public IReadOnlyDictionary<string, string> Status => Volatile.Read(ref _status);
    private IReadOnlyDictionary<string, string> _status = new Dictionary<string,string>();
    public ConnectionManager(IWireFactory factory) { _factory = factory; }
    public void Start() => _worker ??= Task.Run(Run);
    public void Retry() { Interlocked.Exchange(ref _reconnect, 1); _wake.Set(); }
    public void Pause(bool paused) { Interlocked.Exchange(ref _paused, paused ? 1 : 0); Retry(); }
    public async Task<JsonElement> QueryAsync(string command, object? value, CancellationToken cancellation = default)
    {
        if (Volatile.Read(ref _disposed) != 0) throw new ObjectDisposedException(nameof(ConnectionManager));
        if (Info.State != "connected") throw new IOException("EcoLoggerが接続されていません");
        var request = new CommandRequest(command,
            JsonSerializer.Serialize(new Dictionary<string,object?> { [command] = value }));
        _commands.Enqueue(request); _wake.Set();
        using var registration = cancellation.Register(request.Cancel);
        return await request.Completion.Task.WaitAsync(TimeSpan.FromSeconds(8),cancellation).ConfigureAwait(false);
    }
    private void Set(string state, string text, string port = "") => Volatile.Write(ref _info, Info with { State = state, Message = text, Port = port });
    private void Run()
    {
        var failures = 0;
        while (!_cancel.IsCancellationRequested)
        {
            Interlocked.Exchange(ref _reconnect, 0);
            if (Volatile.Read(ref _paused) != 0) { Set("paused", "USB接続を休止中"); _wake.WaitOne(500); continue; }
            Volatile.Write(ref _latest, null);
            Volatile.Write(ref _status, new Dictionary<string,string>());
            try
            {
                var candidates = _factory.FindDevices().ToArray();
                if (candidates.Length == 0) { Set("waiting", "EcoLoggerのUSB接続を待っています"); _wake.WaitOne(1000); continue; }
                foreach (var port in candidates)
                {
                    if (_cancel.IsCancellationRequested || Volatile.Read(ref _paused) != 0) break;
                    try
                    {
                        Set("connecting", "EcoLoggerを確認しています", port);
                        using var wire = _factory.Open(port);
                        Pump(wire);
                        failures = 0;
                        break;
                    }
                    catch (Exception e) when (e is IOException or System.ComponentModel.Win32Exception or TimeoutException or InvalidOperationException)
                    { Set("retrying", ErrorText(e), port); failures++; }
                }
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException or System.Security.SecurityException)
            { Set("retrying", "USBを列挙できません: " + e.Message); failures++; }
            Volatile.Write(ref _latest, null);
            if (!_cancel.IsCancellationRequested) _wake.WaitOne(Math.Min(3000, 500 + failures * 500));
        }
        Set("stopped", "接続終了");
    }
    private static string ErrorText(Exception e) => e is System.ComponentModel.Win32Exception w && w.NativeErrorCode == 5
        ? "USBが使用中です。RaceCaptureを終了すると自動接続します"
        : e.Message.Contains("USB権限") ? "USBアクセス権を確認してください（dialout / udev）"
        : e is TimeoutException ? "応答停止 · USBを開き直しています" : "USB切断 · 再接続待ち";

    private void Pump(IWire wire)
    {
        var decoder = new RcpDecoder(); var framer = new LineFramer();
        var bytes = new byte[8192];
        var start = Now; var lastProgress = start; var nextPoll = start; var nextStatus = start + 2;
        var identified = false; var streaming = false; var capabilitySeen = false;
        var invalid = 0; var sampleInConnection = 0; var recoveryRequested = false;
        ulong lastDeviceUs = 0;
        CommandRequest? command = null;
        void Send(string json) => wire.Write(Encoding.UTF8.GetBytes(json + "\r\n"));
        Send("{\"getVer\":null}");
        try
        {
            while (!_cancel.IsCancellationRequested && Volatile.Read(ref _paused) == 0 && Volatile.Read(ref _reconnect) == 0)
            {
                var count = wire.Read(bytes);
                if (count > 0) framer.Push(bytes.AsSpan(0, count), line =>
                {
                    try
                    {
                        using var doc = JsonDocument.Parse(line);
                        var root = doc.RootElement;
                        if (command != null && root.TryGetProperty(command.Expected, out var commandResult))
                        { command.Completion.TrySetResult(commandResult.Clone()); command = null; }
                        if (root.TryGetProperty("ver", out var ver))
                        {
                            var fname = ver.TryGetProperty("fname", out var fn) ? fn.GetString() ?? "" : "";
                            if (!fname.Contains("logger_v1", StringComparison.OrdinalIgnoreCase) && !fname.Contains("EcoLogger", StringComparison.OrdinalIgnoreCase))
                                throw new InvalidOperationException("EcoLogger以外のUSB機器には接続しません");
                            identified = true;
                            Volatile.Write(ref _info, Info with { Firmware = ver.TryGetProperty("git_info", out var g) ? g.GetString() ?? "" : fname });
                            Send("{\"getCapabilities\":null}"); Send("{\"s\":{\"meta\":true}}");
                        }
                        if (!identified) return;
                        if (root.TryGetProperty("capabilities", out var cap))
                        {
                            capabilitySeen = true;
                            streaming = cap.TryGetProperty("flags", out var flags) && flags.EnumerateArray().Any(x => x.GetString() == "telemstream");
                            if (streaming) Send("{\"setTelemetry\":{\"rate\":10,\"transport\":\"serial\"}}");
                        }
                        if (root.TryGetProperty("s", out var sample))
                        {
                            var frame = decoder.Decode(sample, Now);
                            // A CDC connection can survive a logger power event while returning one
                            // cached snapshot repeatedly.  Only advancing logger time proves that live
                            // acquisition has resumed; otherwise the UI must not claim to be connected.
                            var progressed = lastDeviceUs == 0 || frame.DeviceUs == 0 || frame.DeviceUs != lastDeviceUs;
                            if (progressed)
                            {
                                lastDeviceUs = frame.DeviceUs; lastProgress = frame.ReceivedAt; recoveryRequested = false;
                                Volatile.Write(ref _latest, frame);
                                if (sampleInConnection++ == 0) Volatile.Write(ref _info, Info with { Connections = Info.Connections + 1 });
                                Volatile.Write(ref _info, Info with { State = "connected", Message = "EcoLogger 接続中", Port = wire.Name, Samples = Info.Samples + 1 });
                            }
                            invalid = 0;
                        }
                        if (root.TryGetProperty("status", out var status))
                        {
                            var flat = new Dictionary<string,string>(); Flatten(status, "", flat);
                            Volatile.Write(ref _status, flat);
                        }
                    }
                    catch (Exception e) when (e is JsonException or FormatException or KeyNotFoundException or OverflowException)
                    {
                        invalid++;
                        Volatile.Write(ref _info, Info with { BadFrames = Info.BadFrames + 1 });
                        if (invalid == 1 && identified) Send("{\"s\":{\"meta\":true}}");
                    }
                });
                var now = Now;
                if (command == null)
                    while (_commands.TryDequeue(out var queued))
                    {
                        if (queued.Completion.Task.IsCompleted) continue;
                        command=queued; command.SentAt=now; Send(command.Json); break;
                    }
                if(command!=null&&now-command.SentAt>5)
                { command.Completion.TrySetException(new TimeoutException(command.Expected+" timeout")); command=null; }
                if (!identified && now - start > 3) throw new TimeoutException("Identity timeout");
                if (identified && !capabilitySeen && now - start > 1.5) { capabilitySeen = true; streaming = false; }
                if (identified && capabilitySeen && !streaming && now >= nextPoll)
                { Send("{\"s\":{\"meta\":false}}"); nextPoll = now + .1; }
                if (identified && now >= nextStatus) { Send("{\"getStatus\":null}"); nextStatus = now + 3; }
                if (identified && now - lastProgress > .8 && !recoveryRequested)
                {
                    recoveryRequested = true;
                    Set("recovering", "データ更新を再開しています", wire.Name);
                    decoder.Reset();
                    Send("{\"getVer\":null}"); Send("{\"getCapabilities\":null}"); Send("{\"s\":{\"meta\":true}}");
                    if (streaming) Send("{\"setTelemetry\":{\"rate\":10,\"transport\":\"serial\"}}");
                }
                if ((identified && now - lastProgress > 2.5) || invalid >= 8 || framer.DroppedLines >= 2)
                    throw new TimeoutException("Telemetry timeout");
            }
        }
        finally
        {
            command?.Completion.TrySetException(new IOException("USB接続が切れました"));
            while(_commands.TryDequeue(out var queued)) queued.Completion.TrySetException(new IOException("USB接続が切れました"));
            // Closing a connected attempt stops only USB display streaming, never SD recording.
            if (identified && streaming)
                try { Send("{\"setTelemetry\":{\"rate\":0,\"transport\":\"serial\"}}"); } catch { }
            Volatile.Write(ref _latest, null);
        }
    }
    private static void Flatten(JsonElement value, string path, Dictionary<string,string> result)
    {
        if (value.ValueKind == JsonValueKind.Object)
            foreach (var p in value.EnumerateObject()) Flatten(p.Value, path.Length == 0 ? p.Name : path + "." + p.Name, result);
        else if (value.ValueKind != JsonValueKind.Array) result[path] = value.ToString();
    }
    public void Dispose()
    {
        if (Interlocked.Exchange(ref _disposed, 1) != 0) return;
        _cancel.Cancel(); _wake.Set();
        // Reads/writes are bounded; don't strand the COM handle or a worker on exit.
        if (_worker?.Wait(TimeSpan.FromSeconds(2)) != false) { _wake.Dispose(); _cancel.Dispose(); }
    }
    private sealed class CommandRequest
    {
        public readonly string Expected,Json;
        public readonly TaskCompletionSource<JsonElement> Completion = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public double SentAt;
        public CommandRequest(string command,string json)
        { Expected=command switch { "listLogs"=>"logs", "readLog"=>"logData", "getLevelCalibration"=>"levelCalibration", _=>command }; Json=json; }
        public void Cancel()=>Completion.TrySetCanceled();
    }
}
