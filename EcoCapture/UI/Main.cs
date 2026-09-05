using Godot;
using EcoCapture.Core;
using EcoCapture.Transport;
using System.Globalization;
using System.Text;
using System.Text.Json;

namespace EcoCapture.UI;

public partial class Main : Control
{
    private AppSettings _settings = new();
    private ConnectionManager _connection = null!;
    private LiveShareClient _liveShare = null!;
    private readonly PositionEstimator _position = new();
    private RaceSession _race = new();
    private string _sessionVehicle = "none";
    private bool _sessionDemo;
    private DemoSource? _demo;
    private TelemetryFrame? _frame, _processed;
    private string _data = "", _settingsPath = "", _page = "home", _notice = "";
    private Label _connectionLabel = null!, _footer = null!, _vehicleLabel = null!, _health = null!;
    private Label _lapTime = null!, _raceSpeed = null!, _raceRpm = null!, _raceLap = null!, _totalTime = null!, _bestTime = null!, _lastTime = null!, _lapHistory = null!;
    private Label _mapInfo = null!, _mapState = null!, _mapTiles = null!;
    private Button _raceStart = null!, _demoButton = null!;
    private ProgressBar _rpmBar = null!;
    private Control _rpmCard = null!;
    private MapView _map = null!;
    private Control _content = null!;
    private VBoxContainer _indicate = null!;
    private VBoxContainer _sensorGroups = null!;
    private readonly List<GridContainer> _sensorGrids = new();
    private readonly Dictionary<string, Control> _pages = new();
    private readonly Dictionary<string, Button> _nav = new();
    private readonly List<MetricTile> _metrics = new();
    private readonly Dictionary<string, Label> _diagnostics = new();
    private Label _diagnosticExtra = null!;
    private TabContainer _indicateTabs = null!;
    private double _updateAt, _sessionSaveAt;
    private bool _hadFresh, _indicateDirty;
    private string? _smokeDirectory;
    private string? _hardwareDirectory;
    private bool _hardwareReconnectOnly;
    private bool _exiting;
    private static readonly CultureInfo Invariant = CultureInfo.InvariantCulture;

    public override void _Ready()
    {
        Engine.MaxFps = 30;
        OS.LowProcessorUsageMode = true;
        DisplayServer.WindowSetMinSize(new Vector2I(1000,680));
        var args = OS.GetCmdlineUserArgs();
        _smokeDirectory = Argument(args,"--smoke-dir");
        _hardwareDirectory = Argument(args,"--hardware-test-dir");
        _hardwareReconnectOnly = args.Contains("--reconnect-test-only");
        _data = Argument(args,"--data-dir") ?? (_hardwareDirectory != null ? Path.Combine(_hardwareDirectory,"profile") : _smokeDirectory != null ? Path.Combine(_smokeDirectory,"profile") :
            Path.Combine(System.Environment.GetFolderPath(System.Environment.SpecialFolder.ApplicationData),"EcoCapture"));
        Directory.CreateDirectory(_data); _settingsPath = Path.Combine(_data,"settings.json");
        _settings = SettingsStore.Load(_settingsPath,out var warning); _notice = warning ?? "";
        if (_hardwareDirectory!=null) { _settings.Vehicle="none"; _settings.CanEnabled=false; }
        _settings.Validate();
        _liveShare=new(); _liveShare.Configure(_settings.LiveShare);
        var font = new FontVariation { BaseFont = GD.Load<FontFile>("res://assets/NotoSansJP.ttf"),
            VariationOpentype = new Godot.Collections.Dictionary { [TextServerManager.GetPrimaryInterface().NameToTag("wght")] = 450f } };
        Theme = new Theme { DefaultFont = font, DefaultFontSize = 19 };
        var root = Ui.VBox(12); root.SetAnchorsAndOffsetsPreset(LayoutPreset.FullRect); AddChild(root);
        root.OffsetLeft = 24; root.OffsetRight = -24; root.OffsetTop = 18; root.OffsetBottom = -14;
        var header = Ui.HBox(14); root.AddChild(header);
        var brand = Ui.Button("EcoCapture",() => ShowPage("home")); brand.Flat=true; brand.AddThemeFontSizeOverride("font_size",27); header.AddChild(brand);
        header.AddChild(Ui.Spacer());
        _connectionLabel = Ui.Label("USB接続待ち",17,Ui.Amber); header.AddChild(_connectionLabel);
        _connectionLabel.TextOverrunBehavior=TextServer.OverrunBehavior.TrimEllipsis;
        _connectionLabel.HorizontalAlignment=HorizontalAlignment.Right;
        _connectionLabel.SizeFlagsHorizontal=SizeFlags.ExpandFill; _connectionLabel.CustomMinimumSize=new(220,0);
        var retry = Ui.Button("再接続",() => { _connection.Retry(); _notice="USB接続を開き直します。SD記録は継続します。"; }); header.AddChild(retry);
        var nav = Ui.HBox(8); root.AddChild(nav);
        foreach (var item in new[]{("indicate","Indicate"),("race","Race"),("maps","Maps"),("solve","Solve"),("settings","Settings")})
        {
            var key = item.Item1; var b = Ui.Button(item.Item2,() => ShowPage(key));
            b.SizeFlagsHorizontal = SizeFlags.ExpandFill; nav.AddChild(b); _nav[key] = b;
        }
        _content = new Control(); Ui.Expand(_content); root.AddChild(_content);
        BuildHome(); BuildIndicate(); BuildRace(); BuildMap(); BuildSolve(); BuildSettings();
        _footer = Ui.Label("",13,Ui.Muted); _footer.TextOverrunBehavior=TextServer.OverrunBehavior.TrimEllipsis; root.AddChild(_footer);
        _connection = new(PlatformWireFactory.Create());
        if (args.Contains("--demo") || _smokeDirectory != null) { _demo = new(ConnectionManager.Now); _connection.Pause(true); }
        _connection.Start();
        _ = Task.Run(() => MapView.TrimCache(Path.Combine(_data,"map-cache")));
        ShowPage(Argument(args,"--screen") ?? "home");
        GetTree().AutoAcceptQuit = false;
        if (_smokeDirectory != null) CallDeferred(MethodName.RunSmoke);
        else if (_hardwareDirectory != null) CallDeferred(MethodName.RunHardwareTest);
    }
    private static string? Argument(string[] args, string key)
    { var i = Array.IndexOf(args,key); return i >= 0 && i + 1 < args.Length ? args[i+1] : null; }
    private void AddPage(string name, Control page)
    { page.SetAnchorsAndOffsetsPreset(LayoutPreset.FullRect); _content.AddChild(page); _pages[name]=page; }
    private void ShowPage(string name)
    {
        if (!_pages.ContainsKey(name)) name="home";
        _page=name;
        foreach(var p in _pages) p.Value.Visible=p.Key==name;
        foreach(var n in _nav) n.Value.AddThemeStyleboxOverride("normal",Ui.Box(n.Key==name?new Color("242424"):Colors.Black,0,12,n.Key==name?Colors.White:Ui.Border));
        if (name=="indicate" && _indicateDirty) RebuildSensors();
        if (name=="settings") RefreshLevelCalibration();
        if (name=="solve") RefreshSolveLogs();
    }
    private void BuildHome()
    {
        var v=Ui.VBox(22); AddPage("home",v);
        v.AddChild(Ui.Label("画面を選択してください",25));
        _vehicleLabel=Ui.Label("",19,Ui.Muted); v.AddChild(_vehicleLabel);
        var grid=new GridContainer { Columns=3 }; grid.AddThemeConstantOverride("h_separation",18); grid.AddThemeConstantOverride("v_separation",18); Ui.Expand(grid); v.AddChild(grid);
        foreach(var card in new[]{("indicate","Indicate","センサ値の一覧","センサの状態は別タブに表示"),
            ("race","Race","ラップ計測","タイム・速度・エンジン回転数"),
            ("maps","Maps","現在位置","中心固定の地図表示"),
            ("solve","Solve","走行データ解析","経路・速度・加速度"),
            ("settings","Settings","設定","車体・センサ・地図・接続")})
        {
            var key=card.Item1; var content=Ui.VBox(10); content.AddChild(Ui.Label(card.Item2,24,Ui.Accent));
            content.AddChild(Ui.Label(card.Item3,24)); content.AddChild(Ui.Label(card.Item4,16,Ui.Muted));
            var panel=Ui.Card(content,24); Ui.Expand(panel); grid.AddChild(panel);
            panel.MouseDefaultCursorShape=CursorShape.PointingHand;
            panel.GuiInput += e => { if (e is InputEventMouseButton { Pressed:true,ButtonIndex:MouseButton.Left }) ShowPage(key); };
            content.MouseFilter=MouseFilterEnum.Ignore;
            foreach(var child in content.GetChildren().OfType<Control>()) child.MouseFilter=MouseFilterEnum.Ignore;
        }
        var bottom=Ui.HBox(16); v.AddChild(bottom); bottom.AddChild(Ui.Spacer());
        bottom.AddChild(Ui.Button("UX250hデモ",StartUxDemo));
        _demoButton=Ui.Button("デモで試す",ToggleDemo); bottom.AddChild(_demoButton);
    }
    private void BuildIndicate()
    {
        _indicate=Ui.VBox(10); AddPage("indicate",_indicate);
        var title=Ui.HBox(); _indicate.AddChild(title); title.AddChild(Ui.Label("Indicate",28)); title.AddChild(Ui.Spacer());
        title.AddChild(Ui.Button("表示項目を変更",()=>ShowPage("settings")));
        _health=Ui.Label("",15,Ui.Muted); _indicate.AddChild(_health);
        _indicateTabs=new TabContainer(); Ui.Expand(_indicateTabs); _indicate.AddChild(_indicateTabs);
        var scroll=new ScrollContainer { Name="センサ値",HorizontalScrollMode=ScrollContainer.ScrollMode.Disabled }; _indicateTabs.AddChild(scroll);
        _sensorGroups=Ui.VBox(14); _sensorGroups.SizeFlagsHorizontal=SizeFlags.ExpandFill; scroll.AddChild(_sensorGroups);
        var statusScroll=new ScrollContainer { Name="センサ状態",HorizontalScrollMode=ScrollContainer.ScrollMode.Disabled }; _indicateTabs.AddChild(statusScroll);
        var status=Ui.VBox(6); status.SizeFlagsHorizontal=SizeFlags.ExpandFill; statusScroll.AddChild(status);
        foreach(var s in Catalog.Diagnostics)
        {
            var row=Ui.HBox(); var label=Ui.Label(s.Label,18); label.SizeFlagsHorizontal=SizeFlags.ExpandFill; row.AddChild(label);
            row.AddChild(Ui.Label(s.Source,13,Ui.Muted)); var value=Ui.Label("--",19); value.CustomMinimumSize=new(190,0); value.HorizontalAlignment=HorizontalAlignment.Right; row.AddChild(value);
            _diagnostics[s.Id]=value; status.AddChild(Ui.Card(row,10));
        }
        _diagnosticExtra=Ui.Label("",15,Ui.Muted); status.AddChild(_diagnosticExtra);
        RebuildSensors();
    }
    private void RebuildSensors()
    {
        foreach(var node in _sensorGroups.GetChildren()) { _sensorGroups.RemoveChild(node); node.QueueFree(); }
        _metrics.Clear(); _sensorGrids.Clear();
        var prefs=_settings.CurrentSensors();
        var selected=VisibleSensors();
        foreach(var group in selected.GroupBy(s=>s.Source))
        {
            _sensorGroups.AddChild(Ui.Label(group.Key=="CAN"?"車載CAN":group.Key,17,Ui.Muted));
            var grid=new GridContainer { Columns=_settings.Columns==3&&group.Key=="GNSS"?4:_settings.Columns,SizeFlagsHorizontal=SizeFlags.ExpandFill };
            grid.AddThemeConstantOverride("h_separation",12); grid.AddThemeConstantOverride("v_separation",12);
            _sensorGroups.AddChild(grid); _sensorGrids.Add(grid);
            foreach(var sensor in group)
            {
                var tile=new MetricTile(sensor,prefs[sensor.Id]);
                _metrics.Add(tile); grid.AddChild(tile);
            }
        }
        if (_metrics.Count==0) _sensorGroups.AddChild(Ui.Note("表示するセンサがありません。Settingsで表示項目を選んでください。"));
        _indicateDirty=false;
    }
    private SensorDefinition[] VisibleSensors()
    {
        var prefs=_settings.CurrentSensors();
        return Catalog.Sensors.Where(s=>prefs[s.Id].Visible&&_settings.SourceEnabled(s.Source))
            .OrderBy(s=>_settings.Vehicle=="ux250h" ? s.Source switch { "CAN"=>0,"GNSS"=>1,"IMU"=>2,_=>3 }
                : s.Source switch { "GNSS"=>0,"IMU"=>1,"CAN"=>2,_=>3 }).ToArray();
    }
    private void BuildRace()
    {
        var v=Ui.VBox(12); AddPage("race",v);
        var heading=Ui.HBox(); v.AddChild(heading); heading.AddChild(Ui.Label("Race",28)); heading.AddChild(Ui.Spacer());
        _raceStart=Ui.Button("計測開始",ToggleRace,true); heading.AddChild(_raceStart);
        heading.AddChild(Ui.Button("手動ラップ",()=> { if (_race.Mark(ConnectionManager.Now)) SaveRace(); }));
        var upper=Ui.HBox(14); Ui.Expand(upper); v.AddChild(upper);
        var timing=Ui.VBox(6); _raceLap=Ui.Label("LAP 01   /   待機中",19,Ui.Accent); timing.AddChild(_raceLap);
        _lapTime=Ui.Label("00:00.000",76); _lapTime.SizeFlagsVertical=SizeFlags.ExpandFill; timing.AddChild(_lapTime);
        timing.AddChild(Ui.Label("CURRENT LAP",14,Ui.Muted)); var timeCard=Ui.Card(timing,24); Ui.Expand(timeCard); timeCard.SizeFlagsStretchRatio=1.6f; upper.AddChild(timeCard);
        var speed=Ui.VBox(4); speed.AddChild(Ui.Label("速度 · GNSS優先",19)); _raceSpeed=Ui.Label("--",80); _raceSpeed.SizeFlagsVertical=SizeFlags.ExpandFill; speed.AddChild(_raceSpeed); speed.AddChild(Ui.Label("km/h",19,Ui.Muted));
        var speedCard=Ui.Card(speed,24); Ui.Expand(speedCard); upper.AddChild(speedCard);
        var rpm=Ui.VBox(8); var rpmHead=Ui.HBox(); rpm.AddChild(rpmHead); rpmHead.AddChild(Ui.Label("エンジン回転数",19)); rpmHead.AddChild(Ui.Spacer()); _raceRpm=Ui.Label("-- rpm",33); rpmHead.AddChild(_raceRpm);
        _rpmBar=Ui.Bar(0,Catalog.Vehicle(_settings.Vehicle).RpmMax); _rpmBar.CustomMinimumSize=new(0,18); rpm.AddChild(_rpmBar);
        _rpmCard=Ui.Card(rpm,18); v.AddChild(_rpmCard);
        var times=Ui.HBox(14); v.AddChild(times);
        _totalTime=TimeCard(times,"TOTAL  トータル","00:00.000"); _bestTime=TimeCard(times,"BEST  ベスト","--:--.---"); _lastTime=TimeCard(times,"LAST  前回","--:--.---");
        _lapHistory=Ui.Label("計測を開始してください。自動ラップにはSettingsでスタートラインを設定します。",16,Ui.Muted); v.AddChild(_lapHistory);
    }
    private static Label TimeCard(HBoxContainer row,string title,string initial)
    { var v=Ui.VBox(6); v.AddChild(Ui.Label(title,15,Ui.Muted)); var label=Ui.Label(initial,32); v.AddChild(label); var p=Ui.Card(v,16); p.SizeFlagsHorizontal=SizeFlags.ExpandFill; row.AddChild(p); return label; }
    private void BuildMap()
    {
        var v=Ui.VBox(10); AddPage("maps",v);
        var heading=Ui.HBox(); heading.AddChild(Ui.Label("Maps",28)); heading.AddChild(Ui.Spacer()); heading.AddChild(Ui.Button("地図の設定",()=>ShowPage("settings"))); v.AddChild(heading);
        var row=Ui.HBox(24); Ui.Expand(row); v.AddChild(row);
        var aspect=new AspectRatioContainer { Ratio=1.6f,StretchMode=AspectRatioContainer.StretchModeEnum.Fit,SizeFlagsHorizontal=SizeFlags.ExpandFill,SizeFlagsVertical=SizeFlags.ExpandFill };
        row.AddChild(aspect); _map=new MapView(Path.Combine(_data,"map-cache")); aspect.AddChild(_map);
        var detailsScroll=new ScrollContainer { CustomMinimumSize=new(270,0),HorizontalScrollMode=ScrollContainer.ScrollMode.Disabled,SizeFlagsVertical=SizeFlags.ExpandFill };
        row.AddChild(detailsScroll);
        var details=Ui.VBox(10); details.SizeFlagsHorizontal=SizeFlags.ExpandFill; detailsScroll.AddChild(details);
        _mapState=Ui.Label("測位待ち",24,Ui.Accent); details.AddChild(_mapState);
        _mapInfo=Ui.Label("",18); details.AddChild(_mapInfo);
        _mapTiles=Ui.Label("",14,Ui.Muted); _mapTiles.AutowrapMode=TextServer.AutowrapMode.WordSmart; details.AddChild(_mapTiles);
    }
    public override void _Process(double delta)
    {
        if (_connection==null || _exiting) return;
        var now=ConnectionManager.Now;
        if (now>=_updateAt)
        {
            _updateAt=now+.1;
            _frame=_demo?.Frame(now,_settings.Vehicle) ?? _connection.Latest;
            var fresh=_frame?.Fresh(now)==true;
            if (!fresh) { _race.BreakPositionContinuity(); _hadFresh=false; }
            if (fresh && !ReferenceEquals(_frame,_processed))
            {
                if (!_hadFresh) _position.Reset();
                _position.Update(_frame!,_settings);
                if (_settings.GnssEnabled && _race.UpdateGnss(_frame!,_settings.StartLine)) SaveRace();
                _liveShare.Offer(_frame!,_settings.Vehicle,_demo!=null);
                _processed=_frame; _hadFresh=true;
            }
            UpdateUi(now);
        }
        if (_page=="race") UpdateRace(now);
        if (_race.Running && now-_sessionSaveAt>5) { SaveRace(); _sessionSaveAt=now; }
    }
    private void UpdateUi(double now)
    {
        var info=_connection.Info;
        var demo=_demo!=null;
        _connectionLabel.Text=demo?"DEMO · 模擬データ":info.Message+(info.Port.Length>0?" · "+info.Port:"");
        _connectionLabel.AddThemeColorOverride("font_color",demo?Ui.Amber:info.State=="connected"?Ui.Accent:Ui.Amber);
        _demoButton.Text=demo?"デモを終了してUSBへ":"デモで試す";
        _vehicleLabel.Text=Catalog.Vehicle(_settings.Vehicle).Name+"  /  "+(_settings.Vehicle=="none"?"GNSS + IMU":"EcoLogger専用");
        var footer=(demo?"DEMO：実測値ではありません。  ":"")+(_notice.Length>0?_notice:"1–5：画面切替  /  Esc：ホーム  /  F11：全画面")+"    EcoCapture 0.3.6";
        _footer.Text=footer;
        if (_page=="indicate")
        {
            if (_indicateDirty) RebuildSensors();
            _health.Text=Catalog.Vehicle(_settings.Vehicle).Name+" / "+(_settings.CanEnabled?
                VehicleDiagnostics.Summary(_connection.Status,_frame,now,demo,info.State=="connected"):
                _frame?.Fresh(now)==true?"受信中":"未接続 · 欠測値は --");
            _health.AutowrapMode=TextServer.AutowrapMode.WordSmart;
            var visible=VisibleSensors();
            for(var i=0;i<_metrics.Count;i++) _metrics[i].UpdateValue(_frame,now,_settings.SourceEnabled(visible[i].Source));
            foreach(var s in Catalog.Diagnostics)
            {
                var value=_frame?.Fresh(now)==true?_frame.Get(s.Id):null;
                _diagnostics[s.Id].Text=value.HasValue?DiagnosticValue(s,value.Value):"--";
                _diagnostics[s.Id].AddThemeColorOverride("font_color",(s.Id is "IMUErr" or "LogDrops" or "CANDrops")&&value>0?Ui.Amber:Ui.Text);
            }
            _diagnosticExtra.Text=$"USB接続回数 {info.Connections}  /  受信 {info.Samples}  /  不正フレーム {info.BadFrames}\n{info.Firmware}\n"+
                string.Join("   ",_connection.Status.Where(x=>x.Key is "logging.active" or "logging.rows" or "usbDrops" or "sdErrors").Select(x=>$"{x.Key}: {x.Value}"));
        }
        if (_page=="maps")
        {
            var pos=_position.Current; var usable=_position.Usable(now)&&_frame?.Fresh(now)==true&&_settings.GnssEnabled;
            _map.SetPosition(pos,usable,_settings.MapSpanKm,_settings.MapPale);
            _mapState.Text=pos==null?"測位待ち":!usable?"位置更新停止":pos.Mode;
            _mapState.AddThemeColorOverride("font_color",!usable||pos?.Estimated==true?Ui.Amber:Ui.Accent);
            _mapInfo.Text=$"横幅  {_settings.MapSpanKm:0.0} km\n"+
                (pos==null?"緯度  --\n経度  --\n\n精度目安  --":$"緯度  {pos.Latitude:F7}\n経度  {pos.Longitude:F7}\n\n精度目安  {pos.AccuracyMeters:F1} m\n速度  {pos.SpeedMps*3.6:F1} km/h\nGNSSから {Math.Max(0,now-pos.GnssAt):F1} 秒");
            _mapTiles.Text=_map.TileStatus;
        }
        if (_page=="solve"&&info.State=="connected"&&info.Connections!=_solveConnectionSeen) RefreshSolveLogs();
        RefreshConnectionSettings();
        RefreshLiveShareSettings();
        RefreshVehicleAcquisition();
    }
    private static string DiagnosticValue(SensorDefinition s,double value) => s.Id switch
    {
        "GPSFix"=>value>=3?"3D測位":value==2?"2D測位":"未測位",
        "IMULink" or "GNSSLink"=>value==1?"接続":"未接続",
        "SDPass"=>value==1?"利用可能":"利用不可",
        "UTCValid"=>value==1?"有効":"未確定",
        "IMUCal"=>$"{value:0}  /  SYS {((int)value>>6)&3} G {((int)value>>4)&3} A {((int)value>>2)&3} M {(int)value&3}",
        _=>value.ToString("F"+s.Precision,Invariant)+(s.Unit.Length>0?" "+s.Unit:"")
    };
    private double? Value(string id,double now,string source) => _settings.SourceEnabled(source)&&_frame?.Fresh(now)==true?_frame.Get(id):null;
    private void UpdateRace(double now)
    {
        _raceStart.Text=_race.Running?"計測停止":"計測開始";
        _raceLap.Text=$"LAP {_race.Laps.Count+1:00}   /   "+(_race.Running?(_race.AwaitingStartLine?"最初のライン通過待ち":_settings.StartLine.Enabled?"自動ライン + 手動":"手動ラップ") : "待機中");
        _lapTime.Text=RaceSession.FormatTime(_race.CurrentLap(now));
        _totalTime.Text=RaceSession.FormatTime(_race.Elapsed(now)); _bestTime.Text=RaceSession.FormatTime(_race.Best);
        _lastTime.Text=RaceSession.FormatTime(_race.Laps.LastOrDefault()?.Seconds);
        var speed=Value("GPSSpeed",now,"GNSS")??Value("Speed",now,"CAN");
        var rpm=Value("RPM",now,"CAN"); _raceSpeed.Text=speed?.ToString("F1",Invariant)??"--";
        _rpmCard.Visible=_settings.CanEnabled;
        _raceRpm.Text=rpm.HasValue?$"{rpm:0} rpm":_settings.CanEnabled?"-- rpm":"車載CAN接続なし";
        _rpmBar.MaxValue=Catalog.Vehicle(_settings.Vehicle).RpmMax; _rpmBar.Value=rpm??0;
        _lapHistory.Text=_race.Laps.Count==0?"まだラップはありません。計測停止時に結果をPCへ保存します。":
            string.Join("    ",_race.Laps.TakeLast(3).Select(l=>$"LAP {l.Number:00}  {RaceSession.FormatTime(l.Seconds)}  [{l.Source}]"));
    }
    private void ToggleRace()
    {
        var now=ConnectionManager.Now;
        if (_race.Running) { _race.Stop(now); if(SaveRace()) _notice="計測結果を保存しました。EcoLoggerのSD記録は継続しています。"; }
        else { StartRace(now,_settings.StartLine.Enabled); _notice=_demo!=null?"デモの計測です。実測の結果とは別に保存します。":"計測を開始しました。走行中の設定操作は避けてください。"; }
        _settingsTabs.SetTabDisabled(3,_race.Running);
        UpdateRace(now);
    }
    private void StartRace(double now,bool automatic=false)
    { _sessionVehicle=_settings.Vehicle; _sessionDemo=_demo!=null; _race.Start(now,automatic); }
    private bool SaveRace()
    {
        if (_race.StartedAt<0) return true;
        try
        {
            var dir=Path.Combine(_data,_sessionDemo?"demo-sessions":"sessions"); Directory.CreateDirectory(dir);
            var stem=_race.StartedUtc.ToString("yyyyMMdd_HHmmss_fff",Invariant);
            var report=new { vehicle=_sessionVehicle,demo=_sessionDemo,started=_race.StartedUtc,running=_race.Running,
                elapsedSeconds=_race.Elapsed(ConnectionManager.Now),laps=_race.Laps };
            var target=Path.Combine(dir,stem+".json"); File.WriteAllText(target+".tmp",JsonSerializer.Serialize(report,new JsonSerializerOptions{WriteIndented=true})); File.Move(target+".tmp",target,true);
            var csv=new StringBuilder("lap,seconds,total_seconds,source\r\n");
            foreach(var l in _race.Laps) csv.AppendLine(FormattableString.Invariant($"{l.Number},{l.Seconds:F3},{l.TotalSeconds:F3},{l.Source}"));
            File.WriteAllText(Path.Combine(dir,stem+".csv"),csv.ToString(),new UTF8Encoding(true));
            return true;
        }
        catch(Exception e) when(e is IOException or UnauthorizedAccessException) { _notice="計測結果を保存できません: "+e.Message; return false; }
    }
    private void ToggleDemo()
    {
        if (_race.Running) { _notice="デモを切り替える前に計測を停止してください。"; return; }
        if(!SaveRace()) return;
        _race=new();
        _demo=_demo==null?new(ConnectionManager.Now):null; _connection.Pause(_demo!=null);
        _position.Reset(); _frame=_processed=null; _hadFresh=false; _notice="";
    }
    private void SaveSettings()
    {
        try { SettingsStore.Save(_settingsPath,_settings); _liveShare.Configure(_settings.LiveShare); _indicateDirty=true; }
        catch(Exception e) when(e is IOException or UnauthorizedAccessException) { _notice="設定を保存できません: "+e.Message; }
    }
    public override void _UnhandledKeyInput(InputEvent e)
    {
        if (e is not InputEventKey {Pressed:true,Echo:false} key) return;
        if (GetViewport().GuiGetFocusOwner() is LineEdit or TextEdit) return;
        switch(key.Keycode)
        {
            case Key.Key1:ShowPage("indicate");break; case Key.Key2:ShowPage("race");break;
            case Key.Key3:ShowPage("maps");break; case Key.Key4:ShowPage("solve");break; case Key.Key5:ShowPage("settings");break; case Key.Escape:ShowPage("home");break;
            case Key.F11: DisplayServer.WindowSetMode(DisplayServer.WindowGetMode()==DisplayServer.WindowMode.Fullscreen?DisplayServer.WindowMode.Windowed:DisplayServer.WindowMode.Fullscreen);break;
        }
    }
    public override void _Notification(int what)
    { if(what==NotificationWMCloseRequest) { _race.Stop(ConnectionManager.Now); SaveRace(); _exiting=true; _liveShare?.Dispose(); _connection?.Dispose(); GetTree().Quit(); } }
    public override void _ExitTree() { if(!_exiting) { _liveShare?.Dispose(); _connection?.Dispose(); } }
    private async void RunSmoke()
    {
        try
        {
            Directory.CreateDirectory(_smokeDirectory!);
            StartUxDemo();
            foreach(var page in new[]{"home","indicate","diagnostics","race","maps","solve","settings"})
            {
                ShowPage(page=="diagnostics"?"indicate":page);
                if(page=="diagnostics") _indicateTabs.CurrentTab=1;
                if(page=="race") { StartRace(ConnectionManager.Now-93.42); _race.Mark(ConnectionManager.Now-24.21); }
                await ToSignal(GetTree().CreateTimer(page=="maps"?4:1),SceneTreeTimer.SignalName.Timeout);
                await ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
                using var img=GetViewport().GetTexture().GetImage(); img.SavePng(Path.Combine(_smokeDirectory!,page+".png"));
            }
            var routePoints=Enumerable.Range(0,180).Select(i=> { var a=i*Math.PI/90; return new RoutePoint(Math.Cos(a)*180+Math.Cos(a*3)*25,Math.Sin(a)*105,i*.5,55+Math.Sin(a)*25,Math.Sin(a)*.35,Math.Cos(a)*.45,.5,1.2); }).ToArray();
            _routeView.SetData(new RouteData { SourcePath="demo.csv",Points=routePoints,Summary=new(90,1.2,55,80,180) }); _solveSelect.Visible=false; _solveRoute.Visible=true; ShowPage("solve");
            var overlayPath=Path.Combine(_smokeDirectory!,"course-overlay.svg"); File.WriteAllText(overlayPath,"<svg xmlns='http://www.w3.org/2000/svg' width='640' height='360'><g fill='none' stroke='white' stroke-width='5'><rect x='30' y='30' width='580' height='300'/><path d='M50 260 C180 30 460 30 590 260'/><path d='M50 100 C190 320 450 320 590 100'/></g></svg>"); _routeView.AddLayer(overlayPath); _routeView.Layers[0].Opacity=.35f;
            await ToSignal(GetTree().CreateTimer(.5),SceneTreeTimer.SignalName.Timeout); _routeView.PreviewPoint(35); await ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
            using(var solveImage=GetViewport().GetTexture().GetImage()) solveImage.SavePng(Path.Combine(_smokeDirectory!,"solve-route.png"));
            ShowPage("settings"); _settingsTabs.CurrentTab=2; await ToSignal(GetTree().CreateTimer(.4),SceneTreeTimer.SignalName.Timeout); await ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
            using(var calibrationImage=GetViewport().GetTexture().GetImage()) calibrationImage.SavePng(Path.Combine(_smokeDirectory!,"settings-calibration.png"));
            _settingsTabs.CurrentTab=5; await ToSignal(GetTree().CreateTimer(.4),SceneTreeTimer.SignalName.Timeout); await ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
            using(var liveImage=GetViewport().GetTexture().GetImage()) liveImage.SavePng(Path.Combine(_smokeDirectory!,"settings-live-share.png"));
            _settingsTabs.CurrentTab=6; await ToSignal(GetTree().CreateTimer(.4),SceneTreeTimer.SignalName.Timeout); await ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
            using(var acquisitionImage=GetViewport().GetTexture().GetImage()) acquisitionImage.SavePng(Path.Combine(_smokeDirectory!,"settings-vehicle.png"));
            if(!_uxAcquire.Disabled||!_obdStop.Disabled) throw new Exception("Demo must never send vehicle commands");
            _race.Stop(ConnectionManager.Now);
            _vehicleSelector.Selected=3; _vehicleSelector.EmitSignal(OptionButton.SignalName.ItemSelected,3L);
            if(_settings.Vehicle!="none"||_settings.CanEnabled) throw new Exception("No-CAN UI selection failed");
            foreach(var page in new[]{"indicate","race"})
            {
                ShowPage(page); _indicateTabs.CurrentTab=0;
                await ToSignal(GetTree().CreateTimer(.5),SceneTreeTimer.SignalName.Timeout);
                await ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
                using var img=GetViewport().GetTexture().GetImage(); img.SavePng(Path.Combine(_smokeDirectory!,"no-can-"+page+".png"));
            }
            var saved=SettingsStore.Load(_settingsPath,out var loadWarning);
            if(saved.Vehicle!="none"||saved.CanEnabled||loadWarning!=null) throw new Exception("No-CAN persistence failed");
            File.WriteAllText(Path.Combine(_smokeDirectory!,"ui-smoke.json"),JsonSerializer.Serialize(new{passed=true,pages=13,noCanPersisted=true,liveShareTab=true,vehicleCommandsDisabledInDemo=true,tiles=_map.TileStatus}));
            GetTree().Quit();
        }
        catch(Exception e) { GD.PushError(e.ToString()); GetTree().Quit(1); }
    }
}
