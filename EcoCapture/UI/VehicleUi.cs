using Godot;
using EcoCapture.Core;
using EcoCapture.Transport;

namespace EcoCapture.UI;
public partial class Main
{
    private Label _vehicleStatus=null!, _vehicleResult=null!;
    private Button _uxAcquire=null!, _obdAcquire=null!, _obdStop=null!;
    private bool _vehicleCommandBusy;
    private void StartUxDemo()
    {
        if(_race.Running) { _notice="計測を停止してからデモを開始してください。"; return; }
        _vehicleSelector.Selected=4; _vehicleSelector.EmitSignal(OptionButton.SignalName.ItemSelected,4L);
        if(_demo==null) ToggleDemo();
        ShowPage("indicate");
    }
    private void BuildVehicleAcquisition(VBoxContainer v)
    {
        v.AddChild(Ui.Label("UX250h · 車両データ取得",23));
        v.AddChild(Ui.Note("対象：MZAH10-AWXBB（2WD）\nOBD要求はロガー自身が送信します。本体に保存され、PCを外しても継続します。\n500 kbps / 11 bit / Mode 01読取のみ。車種選択だけでは送信を開始しません。"));
        _vehicleStatus=Ui.Label("ロガー未接続",17); _vehicleStatus.AutowrapMode=TextServer.AutowrapMode.WordSmart; v.AddChild(_vehicleStatus);
        _uxAcquire=Ui.Button("UX250hの取得を開始・本体へ保存",()=>SetVehicleAcquisition(true,true),true); v.AddChild(_uxAcquire);
        _obdAcquire=Ui.Button("標準OBDのみ開始・本体へ保存",()=>SetVehicleAcquisition(true,false)); v.AddChild(_obdAcquire);
        _obdStop=Ui.Button("要求送信を停止・受信専用に保存",()=>SetVehicleAcquisition(false,false)); v.AddChild(_obdStop);
        _vehicleResult=Ui.Label("",16,Ui.Muted); _vehicleResult.AutowrapMode=TextServer.AutowrapMode.WordSmart; v.AddChild(_vehicleResult);
        v.AddChild(Ui.Note("停車中に操作し、他のOBD診断器とは同時に要求送信しないでください。\n舵角はToyota 0x025の公開定義を受信専用で使用します。実車の左右・直進との照合が必要です。\nOBD端子に舵角フレームが出ていなければ -- のままです。ゲートウェイ解除や操舵命令は送りません。\nハイブリッドの正常な0 rpmと、無応答の -- は別表示です。"));
    }
    private async void SetVehicleAcquisition(bool enabled,bool steering)
    {
        if(enabled && _connection.Status.TryGetValue("CAN.vehicleTxLocked",out var locked) && locked.Equals("true",StringComparison.OrdinalIgnoreCase)) { _vehicleResult.Text="このロガーは車載CAN送信禁止です。"; return; }
        if(_vehicleCommandBusy||_demo!=null||(enabled&&_race.Running)) return;
        _vehicleCommandBusy=true;
        try
        {
            _vehicleResult.Text="ロガーへ保存中…";
            var response=await _connection.QueryAsync("setVehicleAcquisition",
                new{obdEnabled=enabled,toyotaSteering=steering,confirm=enabled?"READ_ONLY_OBD":""});
            if(!response.TryGetProperty("rc",out var ok)||ok.GetInt32()!=1)
                throw new IOException("保存できません。停止後も再起動前に本体設定を確認してください。");
            var readback=await _connection.QueryAsync("getVehicleAcquisition",null);
            if(readback.GetProperty("obdEnabled").GetBoolean()!=enabled||readback.GetProperty("toyotaSteering").GetBoolean()!=steering)
                throw new IOException("本体の設定読戻しが一致しません。");
            if(enabled&&steering) {
                _vehicleSelector.Selected=4; _vehicleSelector.EmitSignal(OptionButton.SignalName.ItemSelected,4L);
            }
            _vehicleResult.Text=enabled?"本体保存・読戻し完了。応答待ち。USBを外しても要求は継続します。"
                :"本体保存・読戻し完了。要求送信を停止しました。";
        }
        catch(Exception e) when(e is IOException or TimeoutException or InvalidOperationException or KeyNotFoundException)
        { _vehicleResult.Text=e.Message; }
        finally { _vehicleCommandBusy=false; }
    }
    private void RefreshVehicleAcquisition()
    {
        if(_vehicleStatus==null) return;
        var connected=_connection.Info.State=="connected"; var status=_connection.Status;
        string Get(string name)=>connected&&status.TryGetValue("CAN."+name,out var value)?value:"--";
        _vehicleStatus.Text=VehicleDiagnostics.Summary(status,_frame,ConnectionManager.Now,_demo!=null,connected)+
            $"\n要求受付 {Get("obdSent")} / 応答 {Get("obdResponses")} / タイムアウト {Get("obdTimeouts")} / 受付エラー {Get("obdTxErrors")}"+
            $"\nCAN受信 {Get("vehicleRx")} / 舵角フレーム {Get("steeringRx")} / 通信エラー {Get("vehicleErrors")}";
        var disabled=!connected||!_connection.VehicleAcquisitionSupported||_demo!=null||_vehicleCommandBusy;
        _uxAcquire.Disabled=_obdAcquire.Disabled=disabled||_race.Running||(status.TryGetValue("CAN.vehicleTxLocked",out var locked)&&locked.Equals("true",StringComparison.OrdinalIgnoreCase));
        _obdStop.Disabled=disabled;
    }
}
