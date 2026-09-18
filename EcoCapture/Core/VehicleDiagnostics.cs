namespace EcoCapture.Core;

public static class VehicleDiagnostics
{
    public static bool Flag(IReadOnlyDictionary<string,string> status,string key) =>
        status.TryGetValue("CAN."+key,out var v) && (v.Equals("true",StringComparison.OrdinalIgnoreCase)||v=="1");
    public static string TxPolicy(IReadOnlyDictionary<string,string> status,bool connected,bool demo) {
        if(demo) return "デモ · 実機状態は未確認";
        if(!connected) return "車載CANの送信制限を確認待ち";
        if(Flag(status,"vehicleTxLocked")) return "送信禁止 · 本体で固定";
        if(!Flag(status,"vehicleObdOnly")||!Flag(status,"arbitraryTxBlocked")) return "車載CANの送信制限を確認待ち";
        if(Flag(status,"obdFault")) return "OBD送信停止 · 通信異常";
        return Flag(status,"obdEnabled") ? "CAN受信 ＋ OBD読取のみ送信" : "CAN受信中 · OBD読取は停止中";
    }
    public static string Summary(IReadOnlyDictionary<string,string> status, TelemetryFrame? frame,
        double now, bool demo, bool connected)
    {
        if (demo) return "DEMO · 選択車種の模擬データ。実測ではありません";
        if (!connected) return "OBD未確認 · EcoLoggerのUSBを接続してください";
        bool Flag(string key) => status.TryGetValue("CAN."+key,out var v) &&
                                  (v.Equals("true",StringComparison.OrdinalIgnoreCase)||v=="1");
        if (!status.ContainsKey("CAN.obdEnabled")) return "OBD設定未確認 · 対応ファームを確認してください";
        if (Flag("obdFault")) return "OBD送信停止 · CAN通信異常。停車して接続を確認してください";
        if (!Flag("obdEnabled")) return frame?.Fresh(now)==true && frame.Get("RPM").HasValue ? "CAN受信中 · 受信専用" : "受信専用 · 車載CANデータ待ち";
        if (!Flag("vehicleOK") || Flag("vehicleListenOnly")) return "OBD開始待ち · CAN側の状態を確認中";
        if (frame?.Fresh(now)==true && frame.Get("RPM") is double rpm)
            return rpm==0 ? "OBD応答あり · 0 rpm（エンジン停止値。EV走行中にも正常）"
                          : "OBD応答あり · エンジン回転数を取得中";
        return Flag("obdDiscovering") ? "OBD対応項目を確認中 · 応答待ち" : "OBD応答待ち · 欠測は --（0 rpmとは区別）";
    }
}
