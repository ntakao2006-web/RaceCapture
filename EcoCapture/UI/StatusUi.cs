using Godot;
using EcoCapture.Core;
using EcoCapture.Transport;
namespace EcoCapture.UI;
public partial class Main
{
    private readonly DrivingStatus _drivingStatus=new();
    private CheckButton _axesConfirmedToggle=null!;
    private Button _statusObdStart=null!,_statusObdStop=null!;
    private Button _drivingBanner=null!;
    private Label _motionState=null!,_motionDetail=null!,_slipStatus=null!,_canLockStatus=null!,_coolingStatus=null!;
    private void BuildStatus()
    {
        var scroll=new ScrollContainer {HorizontalScrollMode=ScrollContainer.ScrollMode.Disabled}; AddPage("status",scroll);
        var v=Ui.VBox(12); v.SizeFlagsHorizontal=SizeFlags.ExpandFill; scroll.AddChild(v);
        v.AddChild(Ui.Label("Status",28));
        var motion=Ui.VBox(8); motion.AddChild(Ui.Label("走行状態",18,Ui.Muted));
        _motionState=Ui.Label("待機",32);motion.AddChild(_motionState);
        _slipStatus=Ui.Label("",19);motion.AddChild(_slipStatus);
        _motionDetail=Ui.Note("");motion.AddChild(_motionDetail);
        motion.AddChild(Toggle("滑り傾向の警告",_settings.DrivingWarnings,x=>{_settings.DrivingWarnings=x;_drivingStatus.Reset();SaveSettings();}));
        motion.AddChild(_axesConfirmedToggle=Toggle("ロガー固定・Settingsの車体方向を確認済み",_settings.VehicleAxesConfirmed,x=>{_settings.VehicleAxesConfirmed=x;_drivingStatus.Reset();SaveSettings();}));
        motion.AddChild(Ui.Note("25 km/h以上で監視。4輪速の差と、校正済みIMUの旋回・横加速度を使用します。\n舵角がないためオーバーステアの確定判定ではありません。走行での精度は未検証です。"));
        v.AddChild(Ui.Card(motion));
        var cooling=Ui.VBox(8);cooling.AddChild(Ui.Label("冷却系",18,Ui.Muted));
        _coolingStatus=Ui.Label("",22);cooling.AddChild(_coolingStatus);
        cooling.AddChild(Ui.Note("NCEC実車で暫定採用したファン1リレー指令です。モーターの実回転を検出した値ではありません。"));v.AddChild(Ui.Card(cooling));
        var can=Ui.VBox(8);can.AddChild(Ui.Label("車載CAN · CAN1",18,Ui.Muted));
        _canLockStatus=Ui.Label("",22);can.AddChild(_canLockStatus);
        can.AddChild(Ui.Note("任意CAN送信・制御命令は禁止。OBDは標準読取と、Mazdaの指定2項目の読取要求だけ送ります。\nCAN受信を続けたまま、対応する追加データを取得します。"));
        var controls=Ui.HBox();
        _statusObdStart=Ui.Button("OBD読取を開始",()=>SetVehicleAcquisition(true,_settings.Vehicle=="ux250h"));controls.AddChild(_statusObdStart);
        _statusObdStop=Ui.Button("OBD読取を停止",()=>SetVehicleAcquisition(false,_settings.Vehicle=="ux250h"));controls.AddChild(_statusObdStop);
        can.AddChild(controls);v.AddChild(Ui.Card(can));
    }
    private void UpdateStatus(double now)
    {
        _axesConfirmedToggle.SetPressedNoSignal(_settings.VehicleAxesConfirmed);
        var a=_drivingStatus.Update(_frame,now,_settings);
        _motionState.Text=a.State;_motionState.Modulate=a.Warning?Ui.Red:Ui.Text;
        _motionDetail.Text=a.Detail;
        _slipStatus.Text=$"後輪速度差 {(a.RearSlipPercent is double s?s.ToString("F1")+" %":"--")}    旋回差 {(a.YawResidualDps is double y?y.ToString("F1")+" °/s":"--")}";
        _drivingBanner.Visible=a.Warning;_drivingBanner.Text=a.State+"  ·  Statusで確認";_drivingBanner.Modulate=Ui.Red;
        var fresh=_frame?.Fresh(now)==true && _settings.CanEnabled;
        string Value(string id,string unit)=>fresh&&_frame!.Get(id) is double value?value.ToString("F1")+unit:"--";
        var ac=fresh?_frame!.Get("ACRequest"):null;
        _coolingStatus.Text=$"クーリングファン指令：--\n水温 {Value("WaterTemp"," °C")}    A/C要求 {(ac==1?"ON":ac==0?"OFF":"--")}";
        if(_demo==null && _connection.Info.State=="connected" && _settings.Vehicle=="roadster" && _settings.CanEnabled) {
            string Candidate(string rawKey,string ageKey,int bit) {
                var status=_connection.Status;
                return VehicleDiagnostics.Flag(status,"obdEnabled") && !VehicleDiagnostics.Flag(status,"obdFault") && status.TryGetValue("CAN."+rawKey,out var r)&&int.TryParse(r,out var raw)&&
                    status.TryGetValue("CAN."+ageKey,out var age)&&uint.TryParse(age,out var ms)&&ms<15000
                    ? ((raw&(1<<bit))!=0?"ON":"OFF") : "--";
            }
            _coolingStatus.Text=_coolingStatus.Text.Replace("クーリングファン指令：--", "クーリングファン指令："+Candidate("fan1103Raw","fan1103AgeMs",2));
            _coolingStatus.Text+=$"\n追加リレー候補 2: {Candidate("fan1103Raw","fan1103AgeMs",3)}  3: {Candidate("fan0967Raw","fan0967AgeMs",2)}";
        }
        var connected=_connection.Info.State=="connected" && _demo==null;
        _canLockStatus.Text=VehicleDiagnostics.TxPolicy(_connection.Status,connected,_demo!=null);
        bool obdOnly=connected&&VehicleDiagnostics.Flag(_connection.Status,"vehicleObdOnly");
        _statusObdStart.Disabled=!obdOnly||_vehicleCommandBusy||_race.Running;
        _statusObdStop.Disabled=!obdOnly||_vehicleCommandBusy;
    }
}
