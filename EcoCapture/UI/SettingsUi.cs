using Godot;
using EcoCapture.Core;
using EcoCapture.Transport;

namespace EcoCapture.UI;

public partial class Main
{
    private Label? _connectionDetail;
    private OptionButton _vehicleSelector = null!;
    private TabContainer _settingsTabs = null!;
    private VBoxContainer _sensorSettings = null!;
    private Label _profileDetail = null!;
    private Label _levelCalibration = null!;
    private double _levelQueryAt;
    private CheckButton _canToggle = null!;
    private SpinBox _lineLat = null!, _lineLon = null!, _lineBearing = null!;
    private void BuildSettings()
    {
        var v=Ui.VBox(10); AddPage("settings",v);
        var heading=Ui.HBox(); v.AddChild(heading); heading.AddChild(Ui.Label("Settings",28)); heading.AddChild(Ui.Spacer());
        heading.AddChild(Ui.Label("変更はこのPCに自動保存",15,Ui.Accent));
        var tabs=new TabContainer(); Ui.Expand(tabs); v.AddChild(tabs);
        _settingsTabs=tabs;
        BuildVehicleSettings(SettingsTab(tabs,"車体"));
        BuildDisplaySettings(SettingsTab(tabs,"表示項目"));
        BuildMapSettings(SettingsTab(tabs,"地図とIMU"));
        BuildLapSettings(SettingsTab(tabs,"ラップ計測"));
        BuildConnectionSettings(SettingsTab(tabs,"接続と保存"));
    }
    private static VBoxContainer SettingsTab(TabContainer tabs,string title)
    {
        var scroll=new ScrollContainer { Name=title,HorizontalScrollMode=ScrollContainer.ScrollMode.Disabled };
        tabs.AddChild(scroll); var margin=new MarginContainer { SizeFlagsHorizontal=SizeFlags.ExpandFill };
        foreach(var side in new[]{"left","right","top","bottom"}) margin.AddThemeConstantOverride("margin_"+side,16);
        scroll.AddChild(margin); var v=Ui.VBox(16); v.SizeFlagsHorizontal=SizeFlags.ExpandFill; margin.AddChild(v); return v;
    }
    private void BuildVehicleSettings(VBoxContainer v)
    {
        var row=Ui.HBox(18); v.AddChild(row); row.AddChild(Ui.Label("搭載されている車体",20));
        var vehicles=new OptionButton { CustomMinimumSize=new(400,44) };
        _vehicleSelector=vehicles;
        foreach(var profile in Catalog.Vehicles) vehicles.AddItem(profile.Name);
        vehicles.Selected=Array.FindIndex(Catalog.Vehicles,x=>x.Id==_settings.Vehicle);
        row.AddChild(vehicles);
        row.AddChild(Ui.Button("この車体の表示を初期化",()=> { _settings.Profiles.Remove(_settings.Vehicle); SaveSettings(); RebuildSensorSettings(); }));
        _profileDetail=Ui.Label(Catalog.Vehicle(_settings.Vehicle).Detail,16,Ui.Muted); v.AddChild(_profileDetail);
        var sources=Ui.HBox(18); v.AddChild(sources);
        sources.AddChild(Toggle("GNSSを表示",_settings.GnssEnabled,x=> { _settings.GnssEnabled=x; _position.Reset(); SaveSettings(); RebuildSensorSettings(); }));
        sources.AddChild(Toggle("IMUを表示",_settings.ImuEnabled,x=> { _settings.ImuEnabled=x; SaveSettings(); RebuildSensorSettings(); }));
        _canToggle=Toggle("車載CAN接続あり",_settings.CanEnabled,x=> { _settings.CanEnabled=x; SaveSettings(); RebuildSensorSettings(); });
        _canToggle.Disabled=_settings.Vehicle=="none"; sources.AddChild(_canToggle);
        vehicles.ItemSelected+=index=>
        {
            if(_race.Running) { vehicles.Selected=Array.FindIndex(Catalog.Vehicles,x=>x.Id==_settings.Vehicle); _notice="車体を切り替える前に計測を停止してください。"; return; }
            _settings.Vehicle=Catalog.Vehicles[index].Id; _settings.CanEnabled=_settings.Vehicle!="none";
            _canToggle.SetPressedNoSignal(_settings.CanEnabled); _canToggle.Disabled=_settings.Vehicle=="none";
            _profileDetail.Text=Catalog.Vehicle(_settings.Vehicle).Detail;
            SaveSettings(); RebuildSensorSettings();
        };
    }
    private void BuildDisplaySettings(VBoxContainer v)
    {
        var display=Ui.HBox(); v.AddChild(display); display.AddChild(Ui.Label("Indicateの並び方",19));
        var layout=new OptionButton { CustomMinimumSize=new(250,40) };
        layout.AddItem("タイル · 3列"); layout.AddItem("タイル · 2列"); layout.AddItem("一覧 · 1列");
        layout.Selected=3-_settings.Columns; layout.ItemSelected+=i=> { _settings.Columns=3-(int)i; SaveSettings(); }; display.AddChild(layout);
        var headings=Ui.HBox(10);
        foreach(var item in new[]{("表示する値",368),("表示形式",155),("小数桁",100),("上限警告（任意）",210)})
        { var h=Ui.Label(item.Item1,16,Ui.Muted); h.CustomMinimumSize=new(item.Item2,0); headings.AddChild(h); }
        v.AddChild(headings);
        _sensorSettings=Ui.VBox(6); v.AddChild(_sensorSettings); RebuildSensorSettings();
    }
    private void RebuildSensorSettings()
    {
        foreach(var child in _sensorSettings.GetChildren()) { _sensorSettings.RemoveChild(child); child.QueueFree(); }
        var preferences=_settings.CurrentSensors();
        foreach(var sensor in Catalog.Sensors.Where(s=>_settings.SourceEnabled(s.Source)))
        {
            var pref=preferences[sensor.Id]; var row=Ui.HBox(10);
            var visible=new CheckBox { Text=sensor.Label,ButtonPressed=pref.Visible,CustomMinimumSize=new(300,38) };
            visible.Toggled+=value=> { pref.Visible=value; SaveSettings(); }; row.AddChild(visible);
            var source=Ui.Label(sensor.Source,13,Ui.Muted); source.CustomMinimumSize=new(58,0); row.AddChild(source);
            var style=new OptionButton { CustomMinimumSize=new(155,38) }; style.AddItem("数値 + バー"); style.AddItem("数値のみ"); style.Selected=pref.Bar?0:1;
            style.ItemSelected+=i=> { pref.Bar=i==0; SaveSettings(); }; row.AddChild(style);
            var precision=new OptionButton { CustomMinimumSize=new(100,38) }; precision.AddItem("標準");
            for(var n=0;n<=7;n++) precision.AddItem(n+"桁"); precision.Selected=pref.Precision+1;
            precision.ItemSelected+=i=> { pref.Precision=(int)i-1; SaveSettings(); }; row.AddChild(precision);
            var warning=new CheckBox { Text="有効",ButtonPressed=pref.WarningAbove.HasValue }; row.AddChild(warning);
            var threshold=Number(pref.WarningAbove??sensor.Max,-10000,100000,1,x=> { if(warning.ButtonPressed) { pref.WarningAbove=x; SaveSettings(); } },130);
            threshold.Editable=warning.ButtonPressed; row.AddChild(threshold);
            warning.Toggled+=enabled=> { pref.WarningAbove=enabled?threshold.Value:null; threshold.Editable=enabled; SaveSettings(); };
            row.AddChild(Ui.Label(sensor.Unit,15,Ui.Muted)); _sensorSettings.AddChild(Ui.Card(row,8));
        }
    }
    private void BuildMapSettings(VBoxContainer v)
    {
        v.AddChild(Ui.Label("地図の表示範囲",23));
        var span=new OptionButton { CustomMinimumSize=new(280,44) };
        var sizes=new[]{.5,1,2,4,8}; foreach(var size in sizes) span.AddItem($"横 {size:0.0} km");
        span.Selected=Array.IndexOf(sizes,_settings.MapSpanKm); span.ItemSelected+=i=> { _settings.MapSpanKm=sizes[i]; SaveSettings(); }; v.AddChild(span);
        var style=new OptionButton { CustomMinimumSize=new(280,44) }; style.AddItem("淡色地図"); style.AddItem("標準地図");
        style.Selected=_settings.MapPale?0:1; style.ItemSelected+=i=> { _settings.MapPale=i==0; SaveSettings(); }; v.AddChild(style);
        v.AddChild(new HSeparator()); v.AddChild(Ui.Label("車体水平補正",23));
        _levelCalibration=Ui.Label("未確認",17,Ui.Muted); v.AddChild(_levelCalibration);
        var correction=Ui.HBox(); correction.AddChild(Ui.Button("現在を水平として校正",CaptureLevelCalibration,true)); correction.AddChild(Ui.Button("補正を解除",ClearLevelCalibration)); v.AddChild(correction);
        v.AddChild(Ui.Label("停車して車体を水平にし、ロガーとGNSSアンテナを固定してから実行",15,Ui.Muted));
        v.AddChild(new HSeparator()); v.AddChild(Ui.Label("GNSS + IMUの短時間補完",23));
        var axes=new[]{"+X","-X","+Y","-Y","+Z","-Z"};
        var row=Ui.HBox(16); v.AddChild(row); row.AddChild(Ui.Label("車体の前方",19));
        var forward=new OptionButton { CustomMinimumSize=new(130,40) }; foreach(var a in axes) forward.AddItem(a); forward.Selected=Array.IndexOf(axes,_settings.ForwardAxis); row.AddChild(forward);
        row.AddChild(Ui.Label("車体の上方",19)); var up=new OptionButton { CustomMinimumSize=new(130,40) }; foreach(var a in axes) up.AddItem(a); up.Selected=Array.IndexOf(axes,_settings.UpAxis); row.AddChild(up);
        var aid=Toggle("取付軸を確認したのでIMU補完を使用する",_settings.ImuAid,x=>
        {
            if(_settings.ForwardAxis[1]==_settings.UpAxis[1]) { _notice="前方と上方に同じ軸は指定できません。"; return; }
            _settings.ImuAid=x; _position.Reset(); SaveSettings();
        });
        forward.ItemSelected+=i=> { _settings.ForwardAxis=axes[i]; _settings.ImuAid=false; aid.SetPressedNoSignal(false); _position.Reset(); SaveSettings(); };
        up.ItemSelected+=i=> { _settings.UpAxis=axes[i]; _settings.ImuAid=false; aid.SetPressedNoSignal(false); _position.Reset(); SaveSettings(); };
        aid.Toggled+=x=> { if(x&&_settings.ForwardAxis[1]==_settings.UpAxis[1]) aid.SetPressedNoSignal(false); }; v.AddChild(aid);
    }
    private void BuildLapSettings(VBoxContainer v)
    {
        v.AddChild(Ui.Label("GNSSスタートライン",23));
        v.AddChild(Ui.Note("ラインの中心位置、進行方向、幅を指定します。指定方向にラインを横切るとラップを記録します。\n精度が25 mを超える測位、1秒以上の通信の空白、IMUだけの推定位置では判定しません。"));
        v.AddChild(Toggle("GNSSによる自動ラップを有効にする",_settings.StartLine.Enabled,x=> { _settings.StartLine.Enabled=x; _race.BreakPositionContinuity(); SaveSettings(); }));
        var location=Ui.HBox(); v.AddChild(location); location.AddChild(Ui.Label("緯度",18));
        _lineLat=Number(_settings.StartLine.Latitude,-85,85,.0000001,x=> { _settings.StartLine.Latitude=x; _race.BreakPositionContinuity(); SaveSettings(); },220); location.AddChild(_lineLat);
        location.AddChild(Ui.Label("経度",18)); _lineLon=Number(_settings.StartLine.Longitude,-180,180,.0000001,x=> { _settings.StartLine.Longitude=x; _race.BreakPositionContinuity(); SaveSettings(); },220); location.AddChild(_lineLon);
        v.AddChild(Ui.Button("現在のGNSS位置をラインの中心にする",()=>
        {
            var now=ConnectionManager.Now;
            if(_frame?.Fresh(now)!=true || _frame.Get("Lat") is not double lat || _frame.Get("Lon") is not double lon || !(_frame.Get("GPSFix")>=2))
            { _notice="有効なGNSS測位を受信してから設定してください。"; return; }
            _lineLat.Value=lat; _lineLon.Value=lon;
            if(_position.Current!=null) _lineBearing.Value=_position.Current.Bearing;
        }));
        var direction=Ui.HBox(); v.AddChild(direction); direction.AddChild(Ui.Label("ライン通過時の進行方向",18));
        _lineBearing=Number(_settings.StartLine.Bearing,0,359.9,.1,x=> { _settings.StartLine.Bearing=x; _race.BreakPositionContinuity(); SaveSettings(); },150); direction.AddChild(_lineBearing);
        direction.AddChild(Ui.Label("°   北=0 / 東=90 / 南=180 / 西=270",16,Ui.Muted));
        var width=Ui.HBox(); v.AddChild(width); width.AddChild(Ui.Label("ラインの全幅",18)); width.AddChild(Number(_settings.StartLine.WidthMeters,5,200,1,x=> { _settings.StartLine.WidthMeters=x; SaveSettings(); },150)); width.AddChild(Ui.Label("m",18));
        var minimum=Ui.HBox(); v.AddChild(minimum); minimum.AddChild(Ui.Label("ラップの最短時間",18)); minimum.AddChild(Number(_settings.StartLine.MinimumLapSeconds,5,3600,1,x=> { _settings.StartLine.MinimumLapSeconds=x; SaveSettings(); },150)); minimum.AddChild(Ui.Label("秒（連続誤検出を防止）",16,Ui.Muted));
        v.AddChild(Ui.Note("Raceの「計測開始」でトータル時間を開始します。自動計測の1周目は最初のライン通過からです。\n待機中に「手動ラップ」を押すと、その瞬間から1周目を開始します。\n結果はこのPCにJSONとCSVで保存します。EcoLogger本体のラップ設定や記録は変更しません。\n走行中は設定せず、安全な場所に停車して操作してください。"));
    }
    private void BuildConnectionSettings(VBoxContainer v)
    {
        v.AddChild(Ui.Label("EcoLogger USB",23));
        _connectionDetail=Ui.Label("",18); _connectionDetail.AutowrapMode=TextServer.AutowrapMode.WordSmart; v.AddChild(_connectionDetail);
        var actions=Ui.HBox(); v.AddChild(actions); actions.AddChild(Ui.Button("USBを開き直す",()=>_connection.Retry()));
        actions.AddChild(Ui.Button("デモを切り替える",ToggleDemo));
        v.AddChild(new HSeparator()); v.AddChild(Ui.Label("保存先",23)); v.AddChild(Ui.Label(_data,16,Ui.Muted));
        v.AddChild(Ui.Button("保存フォルダーを開く",()=>OS.ShellOpen(_data)));
    }
    private void RefreshConnectionSettings()
    {
        if(_page!="settings"||_connectionDetail==null) return;
        var i=_connection.Info;
        _connectionDetail.Text=$"状態：{i.Message}\nポート：{i.Port}\nファーム：{i.Firmware}\n接続回数：{i.Connections}　受信：{i.Samples}　不正フレーム：{i.BadFrames}";
    }
    private async void CaptureLevelCalibration()
    {
        if(_connection.Info.State!="connected") { _levelCalibration.Text="EcoLoggerを接続してください"; return; }
        try
        {
            _levelCalibration.Text="静止データを取得中…"; var frames=new List<TelemetryFrame>(); ulong prior=ulong.MaxValue;
            for(var i=0;i<28;i++) { var f=_connection.Latest; if(f!=null&&f.Fresh(ConnectionManager.Now)&&f.DeviceUs!=prior){frames.Add(f);prior=f.DeviceUs;} await Task.Delay(100); }
            var c=LevelCalibrationMath.Capture(frames,_settings.ForwardAxis,_settings.UpAxis); var response=await _connection.QueryAsync("setLevelCalibration",c.ToProtocol());
            if(!response.TryGetProperty("rc",out var ok)||ok.GetInt32()!=1)throw new IOException("ロガーが補正値を受け付けませんでした。");
            _levelCalibration.Text=$"有効   Roll {c.RollZero:+0.0;-0.0;0.0}°   Pitch {c.PitchZero:+0.0;-0.0;0.0}°"; _notice="水平補正を保存しました。";
        }
        catch(Exception e) when(e is IOException or TimeoutException or InvalidOperationException) { _levelCalibration.Text="校正できません: "+e.Message; }
    }
    private async void ClearLevelCalibration()
    {
        try { var response=await _connection.QueryAsync("setLevelCalibration",new { enabled=false,rollZeroDeg=0, pitchZeroDeg=0,matrixSensorToVehicle=new[]{1d,0,0,0,1,0,0,0,1} });
            if(!response.TryGetProperty("rc",out var ok)||ok.GetInt32()!=1)throw new IOException("解除できませんでした。"); _levelCalibration.Text="無効"; }
        catch(Exception e) when(e is IOException or TimeoutException) { _levelCalibration.Text="解除できません: "+e.Message; }
    }
    private async void RefreshLevelCalibration()
    {
        if(_levelCalibration==null||_connection==null||_connection.Info.State!="connected"||ConnectionManager.Now<_levelQueryAt)return; _levelQueryAt=ConnectionManager.Now+5;
        try { var c=await _connection.QueryAsync("getLevelCalibration",null); var enabled=c.TryGetProperty("enabled",out var e)&&e.GetBoolean();
            _levelCalibration.Text=enabled?$"有効   Roll {c.GetProperty("rollZeroDeg").GetDouble():+0.0;-0.0;0.0}°   Pitch {c.GetProperty("pitchZeroDeg").GetDouble():+0.0;-0.0;0.0}°":"無効"; }
        catch(Exception e) when(e is IOException or TimeoutException){_levelCalibration.Text="未確認";}
    }
    private static CheckButton Toggle(string text,bool initial,Action<bool> changed)
    { var b=new CheckButton { Text=text,ButtonPressed=initial,CustomMinimumSize=new(0,42) }; b.Toggled+=x=>changed(x); return b; }
    private static SpinBox Number(double value,double min,double max,double step,Action<double> changed,int width=140)
    { var b=new SpinBox { MinValue=min,MaxValue=max,Step=step,Value=value,CustomMinimumSize=new(width,38),UpdateOnTextChanged=false }; b.ValueChanged+=x=>changed(x); return b; }
}
