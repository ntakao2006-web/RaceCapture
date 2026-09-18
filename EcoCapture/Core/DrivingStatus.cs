namespace EcoCapture.Core;

public sealed record DrivingAssessment(string State, string Detail, bool Warning=false,
    double? RearSlipPercent=null, double? YawResidualDps=null);

// Advisory only: no steering-angle sensor or validated tire model is available.
public sealed class DrivingStatus
{
    private ulong _lastUs;
    private double _wheelSince=-1, _yawSince=-1, _clearSince=-1;
    private DrivingAssessment _current=new("待機", "データを待っています");
    public void Reset() { _lastUs=0; _wheelSince=_yawSince=_clearSince=-1; _current=new("待機","データを待っています"); }
    public DrivingAssessment Update(TelemetryFrame? frame,double now,AppSettings settings)
    {
        DrivingAssessment Hold(string state,string why) { Reset(); return _current=new(state,why); }
        if(!settings.DrivingWarnings) return Hold("警告OFF","Statusで有効にできます");
        if(settings.Vehicle!="roadster" || !settings.CanEnabled) return Hold("対象外","NCECの4輪CANを使用します");
        if(frame?.Fresh(now)!=true) return Hold("データ待ち","通信が途切れると判定を解除します");
        if(frame.DeviceUs==_lastUs) return _current;
        if(_lastUs!=0 && (frame.DeviceUs<_lastUs || frame.DeviceUs-_lastUs>300000)) Reset();
        _lastUs=frame.DeviceUs;
        var t=frame.DeviceUs/1e6;
        var fl=frame.Get("WheelSpeedFL");var fr=frame.Get("WheelSpeedFR");
        var rl=frame.Get("WheelSpeedRL");var rr=frame.Get("WheelSpeedRR");
        if(!fl.HasValue||!fr.HasValue||!rl.HasValue||!rr.HasValue) return Hold("輪速待ち","4輪すべての受信が必要です");
        var front=(fl.Value+fr.Value)/2;var rear=(rl.Value+rr.Value)/2;
        if(front<25 || rear<0) return Hold("低速待機","25 km/h以上で判定します");
        if(frame.Get("BrakePedal")!=0 || frame.Get("ClutchDisengaged")!=0 || frame.Get("ParkingBrake")!=0)
            return Hold("操作中・判定休止","ブレーキ・クラッチ・パーキング操作中は警告を抑制します");
        var slip=100*(rear/front-1);
        bool wheel=slip>8;
        _wheelSince=wheel ? (_wheelSince<0?t:_wheelSince) : -1;
        double? residual=null; string yawReason="車体方向の確認が必要です";
        var cal=frame.Get("IMUCal");
        var imuReady=settings.VehicleAxesConfirmed && settings.ImuEnabled && frame.Get("IMULink")==1 && frame.Get("IMUErr")==0 &&
            cal.HasValue && (((int)cal.Value>>4)&3)==3 && (((int)cal.Value>>2)&3)>=2;
        bool yaw=false;
        if(imuReady) {
            double[] Read(string prefix)=>new[]{frame.Get(prefix+"X")??double.NaN,frame.Get(prefix+"Y")??double.NaN,frame.Get(prefix+"Z")??double.NaN};
            var g=Read("Gravity");var gyro=Read("Gyro");var accel=Read("GForce");
            var norm=Math.Sqrt(g.Sum(x=>x*x));
            if(norm is >8 and <11.8 && gyro.All(double.IsFinite) && accel.All(double.IsFinite) && settings.ForwardAxis[1]!=settings.UpAxis[1]) {
                var up=g.Select(x=>x/norm).ToArray();
                var axis=settings.ForwardAxis[1]-'X';var forward=new double[3];forward[axis]=settings.ForwardAxis[0]=='-'?-1:1;
                var dot=forward.Zip(up,(a,b)=>a*b).Sum();for(int i=0;i<3;i++)forward[i]-=up[i]*dot;
                var fn=Math.Sqrt(forward.Sum(x=>x*x));
                if(fn>.5) {
                    for(int i=0;i<3;i++)forward[i]/=fn;
                    var lateral=new[]{up[1]*forward[2]-up[2]*forward[1],up[2]*forward[0]-up[0]*forward[2],up[0]*forward[1]-up[1]*forward[0]};
                    var ay=accel.Zip(lateral,(a,b)=>a*b).Sum();var yawRate=gyro.Zip(up,(a,b)=>a*b).Sum();
                    residual=Math.Abs(yawRate)-Math.Abs(ay*9.80665/(front/3.6)*180/Math.PI);
                    yaw=Math.Abs(ay)>.15 && Math.Abs(yawRate)>6 && residual>6;
                    yawReason="舵角なしの推定。切り返し・路面傾斜でも反応する場合があります";
                } else yawReason="取付方向を確認してください";
            } else yawReason="IMUデータ待ち";
        } else if(settings.VehicleAxesConfirmed) yawReason="IMU校正待ち（ジャイロ3・加速度2以上）";
        _yawSince=yaw ? (_yawSince<0?t:_yawSince) : -1;
        bool wheelAlarm=_wheelSince>=0 && t-_wheelSince>=.35;
        bool yawAlarm=_yawSince>=0 && t-_yawSince>=.4;
        if(wheelAlarm||yawAlarm) {
            _clearSince=-1;
            return _current=new(yawAlarm&&wheelAlarm?"オーバーステア疑い":yawAlarm?"横滑り傾向":"後輪スリップ傾向",yawReason,true,slip,residual);
        }
        if(_current.Warning && (slip>4 || residual>3)) _clearSince=-1;
        else if(_current.Warning && _clearSince<0) _clearSince=t;
        if(_current.Warning && (_clearSince<0 || t-_clearSince<.8)) return _current with {RearSlipPercent=slip,YawResidualDps=residual};
        return _current=new(residual.HasValue?"警告条件なし":"輪速監視中",yawReason,false,slip,residual);
    }
}
