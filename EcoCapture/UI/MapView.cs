using Godot;
using EcoCapture.Core;
using System.Collections.Concurrent;
using System.Net.Http;

namespace EcoCapture.UI;

public partial class MapView : Control
{
    private readonly string _cache;
    private readonly System.Net.Http.HttpClient _http;
    private readonly SemaphoreSlim _slots = new(2);
    private readonly CancellationTokenSource _cancel = new();
    private readonly Dictionary<string, ImageTexture> _tiles = new();
    private readonly HashSet<string> _pending = new();
    private readonly Dictionary<string, double> _failed = new();
    private readonly ConcurrentQueue<(string Key, byte[]? Data)> _ready = new();
    private readonly LinkedList<string> _lru = new();
    private Position? _position;
    private bool _valid;
    private double _span = 1;
    private bool _pale = true;
    private double _lastRefresh;
    public string TileStatus { get; private set; } = "測位待ち";
    public MapView(string cache,HttpMessageHandler? handler=null)
    {
        _http=handler==null?new():new(handler); _http.Timeout=TimeSpan.FromSeconds(8);
        _cache = cache; ClipContents = true; CustomMinimumSize = new(620,380);
        Material = new ShaderMaterial { Shader = new Shader { Code = "shader_type canvas_item; void fragment(){ float g=dot(COLOR.rgb,vec3(0.299,0.587,0.114)); COLOR=vec4(vec3(g),COLOR.a); }" } };
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("EcoCapture/0.1 (EcoLogger display)");
    }
    public void SetPosition(Position? position, bool valid, double span, bool pale)
    { _position = position; _valid = valid; _span = span; _pale = pale; QueueRedraw(); }
    public override void _Process(double delta)
    {
        while (_ready.TryDequeue(out var tile))
        {
            _pending.Remove(tile.Key);
            if (tile.Data == null) { _failed[tile.Key] = Transport.ConnectionManager.Now; continue; }
            using var img = new Image();
            if (img.LoadPngFromBuffer(tile.Data) != Error.Ok) { _failed[tile.Key] = Transport.ConnectionManager.Now; continue; }
            _tiles[tile.Key] = ImageTexture.CreateFromImage(img); _lru.AddLast(tile.Key);
            while (_lru.Count > 72)
            { var key = _lru.First!.Value; _lru.RemoveFirst(); if (_tiles.Remove(key, out var tex)) tex.Dispose(); }
            QueueRedraw();
        }
        if (IsVisibleInTree() && Transport.ConnectionManager.Now - _lastRefresh > .25)
        {
            _lastRefresh = Transport.ConnectionManager.Now;
            foreach(var key in _failed.Where(p=>_lastRefresh-p.Value>30).Select(p=>p.Key).ToArray()) _failed.Remove(key);
            QueueRedraw();
        }
    }
    public override void _Draw()
    {
        DrawRect(new Rect2(Vector2.Zero, Size), new Color("dce5e7"));
        var font = ThemeDB.FallbackFont;
        if (_position == null)
        {
            for (var x = 0; x < Size.X; x += 40) DrawLine(new(x,0), new(x,Size.Y), new Color("bacad0"));
            for (var y = 0; y < Size.Y; y += 40) DrawLine(new(0,y), new(Size.X,y), new Color("bacad0"));
            TileStatus = "測位待ち"; return;
        }
        var zoom = Geo.ZoomForSpan(_position.Latitude, _span * 1000, Size.X);
        var center = Geo.Tile(_position.Latitude, _position.Longitude, zoom);
        var meters = Geo.MetersPerPixel(_position.Latitude, zoom);
        var scale = Size.X / (_span * 1000) * meters;
        var side = (float)(256 * scale);
        var minX = (int)Math.Floor(center.X - Size.X / (2 * side));
        var maxX = (int)Math.Floor(center.X + Size.X / (2 * side));
        var minY = (int)Math.Floor(center.Y - Size.Y / (2 * side));
        var maxY = (int)Math.Floor(center.Y + Size.Y / (2 * side));
        var available = 0; var total = 0;
        for (var y = minY; y <= maxY; y++)
        for (var x = minX; x <= maxX; x++)
        {
            if (y < 0 || y >= 1 << zoom) continue;
            var wrappedX = (x % (1 << zoom) + (1 << zoom)) % (1 << zoom);
            var key = $"{(_pale ? "pale" : "std")}/{zoom}/{wrappedX}/{y}";
            var rect = new Rect2(new Vector2((float)((x - center.X) * side + Size.X / 2), (float)((y - center.Y) * side + Size.Y / 2)), new(side + .6f, side + .6f));
            total++;
            if (_tiles.TryGetValue(key, out var texture)) { DrawTextureRect(texture, rect, false); available++; }
            else { DrawRect(rect, new Color("c7d5d8"), false, 1); Request(key); }
        }
        TileStatus = available == total ? "地図表示中" : _pending.Count > 0 ? $"地図取得中 {available}/{total}" : "未取得の範囲があります";
        var marker = Size / 2;
        var color = _valid ? Colors.Black : new Color("707070");
        var accuracy = (float)Math.Clamp(_position.AccuracyMeters / (_span * 1000) * Size.X, 5, Size.X / 3);
        DrawCircle(marker, accuracy, new Color(color, .15f));
        DrawCircle(marker, 21, new Color(1,1,1,.92f));
        // Position only: a stationary GNSS fix does not establish vehicle heading.
        DrawCircle(marker, 9, color);
        DrawRect(new Rect2(14,14,36,40), new Color(1,1,1,.9f));
        DrawString(font, new Vector2(23,42), "N", HorizontalAlignment.Left, -1, 22, new Color("163429"));
        var scaleMeters = _span * 1000 / 4;
        var scaleWidth = Size.X / 4;
        DrawRect(new Rect2(14,Size.Y-56,scaleWidth+22,44), new Color(1,1,1,.9f));
        DrawLine(new(24,Size.Y-23), new(24+scaleWidth,Size.Y-23), new Color("163429"), 3);
        DrawString(font,new(24,Size.Y-32),$"{scaleMeters:0} m",HorizontalAlignment.Left,-1,17,new Color("163429"));
        if (!_valid) DrawRect(new Rect2(Vector2.Zero,Size),new Color(.1f,.15f,.2f,.16f));
    }
    private void Request(string key)
    {
        if (!IsVisibleInTree() || _pending.Count >= 24 || _pending.Contains(key) ||
            _failed.TryGetValue(key, out var failed) && Transport.ConnectionManager.Now - failed < 30) return;
        _pending.Add(key);
        _ = Task.Run(async () =>
        {
            byte[]? bytes = null;
            var locked = false;
            var path = Path.Combine(_cache, key.Replace('/', Path.DirectorySeparatorChar) + ".png");
            try
            {
                await _slots.WaitAsync(_cancel.Token); locked = true;
                if (File.Exists(path) && DateTime.UtcNow - File.GetLastWriteTimeUtc(path) < TimeSpan.FromDays(7)) bytes = await File.ReadAllBytesAsync(path, _cancel.Token);
                else
                {
                    using var response = await _http.GetAsync("https://cyberjapandata.gsi.go.jp/xyz/" + key + ".png", _cancel.Token);
                    if (response.IsSuccessStatusCode)
                    {
                        bytes = await response.Content.ReadAsByteArrayAsync(_cancel.Token);
                        if (bytes.Length > 2_000_000) bytes = null;
                        if (bytes != null) { Directory.CreateDirectory(Path.GetDirectoryName(path)!); await File.WriteAllBytesAsync(path,bytes,_cancel.Token); }
                    }
                    else if (File.Exists(path)) bytes = await File.ReadAllBytesAsync(path,_cancel.Token);
                }
            }
            catch (Exception e) when (e is HttpRequestException or IOException or UnauthorizedAccessException or OperationCanceledException)
            {
                // An expired cached tile is still useful when the network is unavailable.
                if(bytes==null&&!_cancel.IsCancellationRequested)
                    try { if(File.Exists(path)) bytes=await File.ReadAllBytesAsync(path,_cancel.Token); }
                    catch(Exception fallback) when(fallback is IOException or UnauthorizedAccessException or OperationCanceledException) { }
            }
            finally { if (locked) _slots.Release(); _ready.Enqueue((key,bytes)); }
        });
    }
    public override void _ExitTree()
    { _cancel.Cancel(); _http.Dispose(); foreach (var t in _tiles.Values) t.Dispose(); }
    public static void TrimCache(string directory)
    {
        if (!Directory.Exists(directory)) return;
        try
        {
            var files = new DirectoryInfo(directory).EnumerateFiles("*.png",SearchOption.AllDirectories).OrderByDescending(f => f.LastWriteTimeUtc).ToArray();
            long total = 0;
            foreach (var f in files) { total += f.Length; if (total > 128L * 1024 * 1024) f.Delete(); }
        }
        catch (Exception e) when(e is IOException or UnauthorizedAccessException) { }
    }
}
