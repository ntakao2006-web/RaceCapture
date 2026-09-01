using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace EcoCapture.Core;

public static class LiveShareUrl
{
    private static readonly Regex ChannelPattern = new("^[a-z0-9_-]{24,48}$", RegexOptions.CultureInvariant);
    public static string NewChannel() => Convert.ToHexString(RandomNumberGenerator.GetBytes(16)).ToLowerInvariant();
    public static bool ValidChannel(string? value) => value != null && ChannelPattern.IsMatch(value);
    public static bool ValidDatabase(string? value)
    {
        if (!Uri.TryCreate(value, UriKind.Absolute, out var uri)) return false;
        if (uri.Scheme == Uri.UriSchemeHttp && uri.IsLoopback) return true;
        return uri.Scheme == Uri.UriSchemeHttps &&
            (uri.Host.EndsWith(".firebaseio.com",StringComparison.OrdinalIgnoreCase) ||
             uri.Host.EndsWith(".firebasedatabase.app",StringComparison.OrdinalIgnoreCase));
    }
    public static bool ValidViewer(string? value)
    {
        if (!Uri.TryCreate(value, UriKind.Absolute, out var uri)) return false;
        return uri.Scheme == Uri.UriSchemeHttps || uri.Scheme == Uri.UriSchemeHttp && uri.IsLoopback;
    }
    public static string Viewer(string viewerUrl,string databaseUrl,string channel) =>
        $"{viewerUrl.TrimEnd('/')}?id={Uri.EscapeDataString(channel)}&db={Uri.EscapeDataString(databaseUrl.TrimEnd('/'))}";
}

public sealed record LiveShareStatus(string State,string Message,int Queued,DateTimeOffset? LastSent)
{
    public static LiveShareStatus Off => new("off","無効",0,null);
}
public sealed record LivePoint(long T, ulong DeviceUs, IReadOnlyDictionary<string,double> D);

public sealed class LiveShareClient : IDisposable
{
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNamingPolicy=JsonNamingPolicy.CamelCase };
    private static readonly string[] Channels = {
        "Lat","Lon","GPSSpeed","Speed","RPM","LongAccel","LatAccel","VertAccel",
        "LevelRoll","LevelPitch","Roll","Pitch","GPSFix","GPSHAcc","GPSSats",
        "Altitude","BatteryVolt","WaterTemp","OilTemp","OilPress","Throttle","EngineLoad"
    };
    private readonly object _gate = new();
    private readonly HttpClient _http;
    private readonly CancellationTokenSource _stop = new();
    private readonly List<LivePoint> _queue = new();
    private LiveShareSettings _settings = new();
    private LiveShareStatus _status = LiveShareStatus.Off;
    private string _vehicle = "none";
    private bool _demo;
    private long _lastPointMs;
    private DateTimeOffset _nextAttempt = DateTimeOffset.MinValue;
    private string _lastPrunedDay = "";
    private Task? _loop;

    public LiveShareClient(HttpMessageHandler? handler=null,bool autoStart=true)
    {
        _http=handler==null?new HttpClient():new HttpClient(handler);
        _http.Timeout=TimeSpan.FromSeconds(10);
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("EcoCapture/0.3.1");
        if(autoStart) _loop=Task.Run(RunAsync);
    }
    public LiveShareStatus Status { get { lock(_gate) return _status with { Queued=_queue.Count }; } }
    public void Configure(LiveShareSettings value)
    {
        lock(_gate)
        {
            _settings=new() { Enabled=value.Enabled,ServerUrl=(value.ServerUrl??"").Trim().TrimEnd('/'),
                ViewerUrl=(value.ViewerUrl??"").Trim().TrimEnd('/'),Channel=(value.Channel??"").Trim().ToLowerInvariant(),IncludeDemo=value.IncludeDemo };
            if(!_settings.Enabled) _status=LiveShareStatus.Off;
            else if(!Ready(_settings)) _status=new("error","Firebase URLまたは共有URL IDを確認してください。",_queue.Count,_status.LastSent);
            else if(_status.State is "off" or "error") _status=new("waiting","1 Hz送信待ち",_queue.Count,_status.LastSent);
        }
    }
    public void Offer(TelemetryFrame frame,string vehicle,bool demo,DateTimeOffset? utc=null)
    {
        var at=(utc??DateTimeOffset.UtcNow).ToUnixTimeMilliseconds();
        lock(_gate)
        {
            if(!_settings.Enabled||!Ready(_settings)||demo&&!_settings.IncludeDemo||at-_lastPointMs<1000) return;
            var values=new Dictionary<string,double>(StringComparer.Ordinal);
            foreach(var key in Channels) if(frame.Get(key) is double value&&double.IsFinite(value)) values[key]=value;
            if(values.Count==0) return;
            _lastPointMs=at; _vehicle=vehicle; _demo=demo; _queue.Add(new(at,frame.DeviceUs,values));
            if(_queue.Count>3600) _queue.RemoveRange(0,_queue.Count-3600);
            _status=new("waiting","1 Hz送信待ち",_queue.Count,_status.LastSent);
        }
    }
    public async Task<bool> CheckAsync(CancellationToken cancellationToken=default)
    {
        LiveShareSettings settings; lock(_gate) settings=_settings;
        if(!Ready(settings)) { SetStatus("error","設定が不足しています。"); return false; }
        try
        {
            using var response=await _http.GetAsync($"{settings.ServerUrl}/channels/{settings.Channel}/latest.json?shallow=true",cancellationToken);
            if(!response.IsSuccessStatusCode) { SetStatus("error",$"接続できません（HTTP {(int)response.StatusCode}）。ルールも確認してください。"); return false; }
            SetStatus("connected","Firebaseへ接続できました。1 Hzで送信します。"); return true;
        }
        catch(Exception e) when(e is HttpRequestException or TaskCanceledException or IOException)
        { SetStatus("error","接続できません: "+e.Message); return false; }
    }
    public async Task<bool> FlushAsync(CancellationToken cancellationToken=default)
    {
        LiveShareSettings settings; LivePoint point; string vehicle; bool demo;
        lock(_gate)
        {
            settings=_settings; if(!settings.Enabled||!Ready(settings)||_queue.Count==0) return false;
            point=_queue[0]; vehicle=_vehicle; demo=_demo; _status=new("sending","送信中",_queue.Count,_status.LastSent);
        }
        try
        {
            var day=DateTimeOffset.FromUnixTimeMilliseconds(point.T).UtcDateTime.ToString("yyyyMMdd");
            var body=new Dictionary<string,object?> {
                ["latest"]=point,["meta/vehicle"]=vehicle,["meta/demo"]=demo,["meta/updatedAt"]=point.T,
                [$"history/{day}/{point.T}"]=point
            };
            using var request=new HttpRequestMessage(HttpMethod.Patch,$"{settings.ServerUrl}/channels/{settings.Channel}.json?print=silent")
                { Content=new StringContent(JsonSerializer.Serialize(body,JsonOptions),Encoding.UTF8,"application/json") };
            using var response=await _http.SendAsync(request,cancellationToken);
            if(!response.IsSuccessStatusCode)
            {
                var detail=await response.Content.ReadAsStringAsync(cancellationToken);
                SetStatus("error",$"送信失敗（HTTP {(int)response.StatusCode}）"+(detail.Length>0?" "+detail[..Math.Min(80,detail.Length)]:"")); return false;
            }
            lock(_gate)
            {
                if(_queue.Count>0&&_queue[0].T==point.T) _queue.RemoveAt(0);
                _status=new("connected","1 Hzで送信中",_queue.Count,DateTimeOffset.Now);
            }
            if(_lastPrunedDay!=day)
            {
                _lastPrunedDay=day;
                var old=DateTimeOffset.FromUnixTimeMilliseconds(point.T).UtcDateTime.Date.AddDays(-8).ToString("yyyyMMdd");
                try { using var _=await _http.DeleteAsync($"{settings.ServerUrl}/channels/{settings.Channel}/history/{old}.json?print=silent",cancellationToken); }
                catch(Exception e) when(e is HttpRequestException or TaskCanceledException or IOException) { }
            }
            return true;
        }
        catch(Exception e) when(e is HttpRequestException or TaskCanceledException or IOException)
        { SetStatus("error","送信待機: "+e.Message); return false; }
    }
    private async Task RunAsync()
    {
        while(!_stop.IsCancellationRequested)
        {
            try
            {
                LiveShareSettings settings; int queued; lock(_gate) { settings=_settings; queued=_queue.Count; }
                var now=DateTimeOffset.UtcNow;
                if(settings.Enabled&&Ready(settings)&&queued>0&&now>=_nextAttempt)
                {
                    var ok=await FlushAsync(_stop.Token); _nextAttempt=now+TimeSpan.FromSeconds(ok?1:10);
                }
                await Task.Delay(100,_stop.Token);
            }
            catch(OperationCanceledException) when(_stop.IsCancellationRequested) { break; }
        }
    }
    private static bool Ready(LiveShareSettings s)=>LiveShareUrl.ValidDatabase(s.ServerUrl)&&LiveShareUrl.ValidChannel(s.Channel);
    private void SetStatus(string state,string message) { lock(_gate) _status=new(state,message,_queue.Count,_status.LastSent); }
    public void Dispose()
    {
        _stop.Cancel(); try { _loop?.Wait(1500); } catch(AggregateException) { } _http.Dispose(); _stop.Dispose();
    }
}
