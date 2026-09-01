using Godot;
using EcoCapture.Core;
using EcoCapture.Transport;
using System.Text.Json;

namespace EcoCapture.UI;

public partial class Main
{
    private async Task WaitUi(Func<bool> condition,double seconds=15)
    {
        var end=ConnectionManager.Now+seconds;
        while(!condition()&&ConnectionManager.Now<end) await ToSignal(GetTree().CreateTimer(.05),SceneTreeTimer.SignalName.Timeout);
        if(!condition()) throw new TimeoutException("UI test condition timed out");
    }
    private async Task CaptureUi(string file,double delay=.3)
    {
        await ToSignal(GetTree().CreateTimer(delay),SceneTreeTimer.SignalName.Timeout);
        await ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
        using var img=GetViewport().GetTexture().GetImage();
        if(img.SavePng(Path.Combine(_hardwareDirectory!,file+".png"))!=Error.Ok) throw new IOException("Screenshot save failed");
    }
    private async void RunHardwareTest()
    {
        var checks=new Dictionary<string,bool>();
        void Verify(string name,bool result) { checks[name]=result; if(!result) throw new Exception("UI test failed: "+name); }
        try
        {
            Directory.CreateDirectory(_hardwareDirectory!);
            var licenses=Engine.GetLicenseInfo();
            File.WriteAllText(Path.Combine(_hardwareDirectory!,"Godot-third-party.txt"),Engine.GetLicenseText()+"\n\n"+
                GD.VarToStr(Engine.GetCopyrightInfo())+"\n\n"+string.Join("\n\n",licenses.Select(p=>p.Key+"\n"+p.Value)));
            await WaitUi(()=>_frame?.Fresh(ConnectionManager.Now)==true&&_frame.Get("GPSFix")>=2);
            Verify("real_usb_not_demo",_demo==null&&_connection.Info.State=="connected");
            var usbSchema=_frame!.Schema; var usbChannels=_connection.SchemaChannels.ToHashSet(StringComparer.Ordinal);
            Verify("usb_schema_contract",usbSchema==DemoSource.LoggerSchema&&usbChannels.Count==DemoSource.LoggerChannels.Length);
            Verify("no_can_traffic",_frame!.Get("CAN1Rx")==0&&_frame.Get("CAN2Rx")==0);
            Verify("imu_and_sd_healthy",_frame.Get("IMULink")==1&&_frame.Get("IMUErr")==0&&_frame.Get("SDPass")==1);
            var calibrationFrames=new List<TelemetryFrame>(); ulong calibrationUs=ulong.MaxValue;
            for(var i=0;i<24;i++){var f=_connection.Latest;if(f!=null&&f.DeviceUs!=calibrationUs){calibrationFrames.Add(f);calibrationUs=f.DeviceUs;}await ToSignal(GetTree().CreateTimer(.1),SceneTreeTimer.SignalName.Timeout);}
            var testCalibration=LevelCalibrationMath.Capture(calibrationFrames,_settings.ForwardAxis,_settings.UpAxis);
            var calibrationResponse=await _connection.QueryAsync("setLevelCalibration",testCalibration.ToProtocol());
            Verify("level_calibration_saved",calibrationResponse.GetProperty("rc").GetInt32()==1);
            await WaitUi(()=>_frame?.Get("LevelRoll").HasValue==true,5);
            Verify("corrected_channels_stream",_frame!.Get("LongAccel").HasValue&&_frame.Get("LatAccel").HasValue);
            ShowPage("home"); await CaptureUi("01-home");
            Input.ParseInputEvent(new InputEventKey { Keycode=Key.Key1,Pressed=true });
            await WaitUi(()=>_page=="indicate",2);
            Verify("nine_sensor_values",_metrics.Count==9&&Catalog.Sensors.Where(s=>_settings.CurrentSensors()[s.Id].Visible).All(s=>s.Source!="CAN"&&_frame.Get(s.Id).HasValue));
            await CaptureUi("02-indicate");
            _indicateTabs.CurrentTab=1; await CaptureUi("03-sensor-status"); _indicateTabs.CurrentTab=0;
            ShowPage("settings");
            for(var i=0;i<Catalog.Vehicles.Length;i++)
            { _vehicleSelector.Selected=i; _vehicleSelector.EmitSignal(OptionButton.SignalName.ItemSelected,(long)i); Verify("vehicle_"+i,_settings.Vehicle==Catalog.Vehicles[i].Id); }
            Verify("no_can_selected",!_settings.CanEnabled&&_canToggle.Disabled);
            for(var i=0;i<5;i++) { _settingsTabs.CurrentTab=i; await CaptureUi("04-settings-"+i); }
            var preference=_settings.CurrentSensors()["GPSSpeed"];
            preference.Bar=true; preference.Precision=2; preference.WarningAbove=-1; SaveSettings();
            ShowPage("indicate"); await CaptureUi("05-display-options");
            Verify("display_settings_saved",SettingsStore.Load(_settingsPath,out _).CurrentSensors()["GPSSpeed"].Precision==2);
            preference.Bar=false; preference.Precision=-1; preference.WarningAbove=null;
            _settings.Columns=2; SaveSettings(); ShowPage("indicate"); await CaptureUi("06-two-columns"); Verify("two_columns",_sensorGrids.Count>0&&_sensorGrids.All(x=>x.Columns==2));
            _settings.Columns=1; SaveSettings(); ShowPage("indicate");
            Verify("one_column",_sensorGrids.Count>0&&_sensorGrids.All(x=>x.Columns==1));
            _settings.GnssEnabled=false; _settings.ImuEnabled=false; SaveSettings(); ShowPage("indicate");
            Verify("disabled_sources_hidden",_metrics.Count==0&&Value("GPSSpeed",ConnectionManager.Now,"GNSS")==null);
            _settings.GnssEnabled=true; _settings.ImuEnabled=true;
            _settings.Columns=3; SaveSettings();
            ShowPage("race"); _settings.StartLine.Enabled=false; ToggleRace();
            await ToSignal(GetTree().CreateTimer(1.4),SceneTreeTimer.SignalName.Timeout);
            Verify("manual_lap",_race.Mark(ConnectionManager.Now)); SaveRace();
            var connections=_connection.Info.Connections; var totalBefore=_race.Elapsed(ConnectionManager.Now);
            await CaptureUi("07-race-before-reconnect");
            File.WriteAllText(Path.Combine(_hardwareDirectory!,"ready-for-usb.json"),"{}");
            await WaitUi(()=>_connection.Info.State!="connected",20);
            await ToSignal(GetTree().CreateTimer(.2),SceneTreeTimer.SignalName.Timeout);
            await CaptureUi("08-race-disconnected",.1);
            Verify("disconnected_values_invalid",Value("GPSSpeed",ConnectionManager.Now,"GNSS")==null);
            await WaitUi(()=>_connection.Info.Connections>connections&&_frame?.Fresh(ConnectionManager.Now)==true,15);
            Verify("race_survived_reconnect",_race.Running&&_race.Elapsed(ConnectionManager.Now)>totalBefore+1);
            Verify("rpm_hidden_without_can",!_rpmCard.Visible);
            await CaptureUi("09-race-reconnected");
            if (_hardwareReconnectOnly)
            {
                ToggleRace();
                await DisableTestLevelCalibration();
                File.WriteAllText(Path.Combine(_hardwareDirectory!,"hardware-ui.json"),JsonSerializer.Serialize(new { passed=true,checks,usb=_connection.Info,
                    limitation="Targeted full logger reset test; extended Solve and Maps checks run separately." },new JsonSerializerOptions{WriteIndented=true}));
                GetTree().Quit(); return;
            }
            ToggleRace(); Verify("race_json_csv_saved",Directory.GetFiles(Path.Combine(_data,"sessions"),"*.csv").Length>0);
            var realCount=Directory.GetFiles(Path.Combine(_data,"sessions"),"*.json").Length;
            ToggleDemo(); await WaitUi(()=>_connection.Info.State=="paused");
            Verify("demo_explicit_and_usb_released",_demo!=null&&_race.StartedAt<0&&_connection.Latest==null);
            await WaitUi(()=>_frame?.Fresh(ConnectionManager.Now)==true&&_demo!=null,3);
            Verify("demo_usb_schema_equivalent",_frame!.Schema==usbSchema&&usbChannels.SetEquals(_frame.Values.Keys));
            ToggleRace(); await ToSignal(GetTree().CreateTimer(1.1),SceneTreeTimer.SignalName.Timeout);
            _race.Mark(ConnectionManager.Now); ToggleRace(); ToggleDemo();
            Verify("demo_results_separate",Directory.GetFiles(Path.Combine(_data,"demo-sessions"),"*.json").Length==1&&Directory.GetFiles(Path.Combine(_data,"sessions"),"*.json").Length==realCount);
            await WaitUi(()=>_frame?.Fresh(ConnectionManager.Now)==true&&_demo==null&&_connection.Info.State=="connected");
            Verify("return_from_demo_real_usb",_frame!.Get("IMULink")==1);
            var attempt=_connection.Info.Connections; _connection.Retry();
            await WaitUi(()=>_connection.Info.Connections>attempt&&_frame?.Fresh(ConnectionManager.Now)==true);
            Verify("manual_reconnect",_connection.Info.Connections>attempt);
            ShowPage("solve"); RefreshSolveLogs(); await WaitUi(()=>_remoteLogs.Count>0,25); Verify("solve_sd_list",_remoteLogs.Count>0); _solveFiles.Selected=0; OpenRemoteLog();
            await WaitUi(()=>_solveRoute.Visible&&_routeView.PointCount>1,70); Verify("solve_sd_download_and_route",_solvePath!=null&&File.Exists(_solvePath)&&_routeView.PointCount>1); _routeView.PreviewPoint(_routeView.PointCount/2); await CaptureUi("09b-solve-route"); ShowSolveSelection();
            ShowPage("maps");
            foreach(var span in new[]{.5,1d,2d,4d,8d})
            {
                _settings.MapSpanKm=span; SaveSettings();
                await ToSignal(GetTree().CreateTimer(.3),SceneTreeTimer.SignalName.Timeout);
                await WaitUi(()=>_map.TileStatus=="地図表示中",15); await CaptureUi("10-map-"+span.ToString("0.0",Invariant),1);
                Verify("map_"+span,_map.TileStatus=="地図表示中"&&_position.Usable(ConnectionManager.Now));
            }
            _settings.MapSpanKm=1; _settings.MapPale=false; SaveSettings();
            await CaptureUi("11-map-standard",4); Verify("standard_map",_map.TileStatus=="地図表示中");
            var cache=Path.Combine(_data,"map-cache");
            foreach(var path in Directory.GetFiles(cache,"*.png",SearchOption.AllDirectories)) File.SetLastWriteTimeUtc(path,DateTime.UtcNow.AddDays(-8));
            ReplaceTestMap(cache,new OfflineMapHandler());
            await WaitUi(()=>_map.TileStatus=="地図表示中",10);
            Verify("offline_expired_cache",_position.Usable(ConnectionManager.Now)); await CaptureUi("11b-map-offline-cache");
            ReplaceTestMap(Path.Combine(_data,"empty-test-cache"),new OfflineMapHandler());
            await WaitUi(()=>_map.TileStatus.StartsWith("未取得"),10);
            Verify("offline_uncached_position_alive",_position.Usable(ConnectionManager.Now)); await CaptureUi("11c-map-offline-empty");
            ReplaceTestMap(cache,null);
            _settings.MapPale=true;
            _settings.ImuAid=true; _settings.ForwardAxis="+X"; _settings.UpAxis="+X"; SaveSettings();
            Verify("invalid_imu_axes_rejected",!_settings.ImuAid); _settings.UpAxis="+Z";
            _settings.StartLine.Latitude=_frame!.Get("Lat")!.Value; _settings.StartLine.Longitude=_frame.Get("Lon")!.Value;
            _settings.StartLine.Enabled=true; SaveSettings(); StartRace(ConnectionManager.Now,true);
            Verify("automatic_lap_armed",_race.AwaitingStartLine&&_race.Laps.Count==0); _race.Stop(ConnectionManager.Now); _settings.StartLine.Enabled=false;
            var baseSize=DisplayServer.WindowGetSize(); DisplayServer.WindowSetSize(new(1000,680));
            ShowPage("indicate"); _indicateTabs.CurrentTab=0; await CaptureUi("12-small-window",1);
            ShowPage("maps"); await CaptureUi("13-small-maps");
            DisplayServer.WindowSetSize(baseSize);
            SaveSettings(); var stored=SettingsStore.Load(_settingsPath,out var warning);
            Verify("no_can_settings_roundtrip",stored.Vehicle=="none"&&!stored.CanEnabled&&stored.MapSpanKm==1&&warning==null);
            await DisableTestLevelCalibration();
            File.WriteAllText(Path.Combine(_hardwareDirectory!,"hardware-ui.json"),JsonSerializer.Serialize(new { passed=true,checks,usb=_connection.Info,
                limitation="Static bench: GNSS line crossing and moving IMU fusion are algorithm-tested, not a driving validation." },new JsonSerializerOptions{WriteIndented=true}));
            GetTree().Quit();
        }
        catch(Exception e)
        {
            try { await DisableTestLevelCalibration(); } catch { }
            File.WriteAllText(Path.Combine(_hardwareDirectory!,"hardware-ui.json"),JsonSerializer.Serialize(new{passed=false,checks,error=e.ToString(),solveStatus=_solveStatus?.Text,solveProgress=_solveProgress?.Value,selectedLog=_solveFiles?.Selected>=0&&_solveFiles.Selected<_remoteLogs.Count?_remoteLogs[_solveFiles.Selected]:null},new JsonSerializerOptions{WriteIndented=true}));
            GD.PushError(e.ToString()); GetTree().Quit(1);
        }
    }
    private Task<JsonElement> DisableTestLevelCalibration()=>_connection.QueryAsync("setLevelCalibration",new { enabled=false,rollZeroDeg=0,pitchZeroDeg=0,matrixSensorToVehicle=new[]{1d,0,0,0,1,0,0,0,1} });
    private void ReplaceTestMap(string cache,System.Net.Http.HttpMessageHandler? handler)
    {
        var parent=_map.GetParent(); parent.RemoveChild(_map); _map.QueueFree();
        _map=new MapView(cache,handler); parent.AddChild(_map);
    }
    private sealed class OfflineMapHandler : System.Net.Http.HttpMessageHandler
    {
        protected override Task<System.Net.Http.HttpResponseMessage> SendAsync(System.Net.Http.HttpRequestMessage request,CancellationToken cancellationToken)
            => Task.FromException<System.Net.Http.HttpResponseMessage>(new System.Net.Http.HttpRequestException("Simulated offline; no network changes"));
    }
}
