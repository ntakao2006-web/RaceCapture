namespace EcoCapture.Core;

public static class VehicleDiagnostics
{
    public static string Summary(IReadOnlyDictionary<string,string> status, TelemetryFrame? frame,
        double now, bool demo, bool connected)
    {
        if (demo) return "DEMO · UXのEV走行 / エンジン稼働を模擬。実測ではありません";
        if (!connected) return "OBD未確認 · EcoLoggerのUSBを接続してください";
        bool Flag(string key) => status.TryGetValue("CAN."+key,out var v) &&
                                  (v.Equals("true",StringComparison.OrdinalIgnoreCase)||v=="1");
        if (!status.ContainsKey("CAN.obdEnabled")) return "OBD設定未確認 · 対応ファームを確認してください";
        if (Flag("obdFault")) return "OBD送信停止 · CAN通信異常。停車して接続を確認してください";
        if (!Flag("obdEnabled")) return "OBD要求OFF · 受信専用（設定の「車両データ取得」で開始）";
        if (!Flag("vehicleOK") || Flag("vehicleListenOnly")) return "OBD開始待ち · CAN側の状態を確認中";
        if (frame?.Fresh(now)==true && frame.Get("RPM") is double rpm)
            return rpm==0 ? "OBD応答あり · 0 rpm（エンジン停止値。EV走行中にも正常）"
                          : "OBD応答あり · エンジン回転数を取得中";
        return Flag("obdDiscovering") ? "OBD対応項目を確認中 · 応答待ち" : "OBD応答待ち · 欠測は --（0 rpmとは区別）";
    }
}
