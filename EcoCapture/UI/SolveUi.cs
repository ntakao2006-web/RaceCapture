using Godot;
using EcoCapture.Core;
using System.Text.Json;

namespace EcoCapture.UI;

public partial class Main
{
    private VBoxContainer _solveSelect=null!,_solveRoute=null!;
    private OptionButton _solveFiles=null!,_overlayFiles=null!;
    private Label _solveStatus=null!,_solveSummary=null!;
    private ProgressBar _solveProgress=null!;
    private RouteView _routeView=null!;
    private List<RemoteLog> _remoteLogs=[],_remoteFiles=[];
    private bool _solveRefreshing;
    private int _solveConnectionSeen=-1;
    private FileDialog _csvDialog=null!,_imageDialog=null!;
    private CancellationTokenSource? _solveCancel;
    private string? _solvePath;

    private void BuildSolve()
    {
        var root=Ui.VBox(10); AddPage("solve",root);
        _solveSelect=Ui.VBox(14); root.AddChild(_solveSelect); Ui.Expand(_solveSelect);
        var h=Ui.HBox(); h.AddChild(Ui.Label("Solve",28)); h.AddChild(Ui.Spacer()); h.AddChild(Ui.Button("SDを再読込",RefreshSolveLogs)); _solveSelect.AddChild(h);
        _solveSelect.AddChild(Ui.Label("走行データ選択",22));
        _solveFiles=new OptionButton { CustomMinimumSize=new(620,48) }; _solveSelect.AddChild(_solveFiles);
        var actions=Ui.HBox(); actions.AddChild(Ui.Button("選択したログを開く",OpenRemoteLog,true)); actions.AddChild(Ui.Button("PCのCSVを開く",()=>_csvDialog.PopupCenteredRatio(.75f))); _solveSelect.AddChild(actions);
        _solveProgress=new ProgressBar { MinValue=0,MaxValue=1,ShowPercentage=true,CustomMinimumSize=new(0,18) }; _solveSelect.AddChild(_solveProgress);
        _solveStatus=Ui.Label("EcoLoggerを接続してください",17,Ui.Muted); _solveSelect.AddChild(_solveStatus);
        _solveRoute=Ui.VBox(8); root.AddChild(_solveRoute); Ui.Expand(_solveRoute); _solveRoute.Visible=false;
        var routeHead=Ui.HBox(); routeHead.AddChild(Ui.Button("← 走行データ選択",()=>ShowSolveSelection())); routeHead.AddChild(Ui.Label("経路",28)); routeHead.AddChild(Ui.Spacer()); routeHead.AddChild(Ui.Button("全体表示",()=>_routeView.Fit())); routeHead.AddChild(Ui.Button("図面を追加",()=>_imageDialog.PopupCenteredRatio(.75f))); _solveRoute.AddChild(routeHead);
        _solveSummary=Ui.Label("",17); _solveRoute.AddChild(_solveSummary);
        var body=Ui.HBox(10); Ui.Expand(body); _solveRoute.AddChild(body); _routeView=new RouteView(); Ui.Expand(_routeView); body.AddChild(_routeView);
        var controls=Ui.VBox(8); controls.CustomMinimumSize=new(250,0); body.AddChild(controls); controls.AddChild(Ui.Label("画像レイヤー",19)); _overlayFiles=new OptionButton{CustomMinimumSize=new(240,42)}; controls.AddChild(_overlayFiles);
        controls.AddChild(Ui.Label("縮尺",15,Ui.Muted)); controls.AddChild(Number(1,.05,20,.05,x=>ChangeLayer(l=>l.MetersPerPixel=(float)x),220));
        controls.AddChild(Ui.Label("回転",15,Ui.Muted)); controls.AddChild(Number(0,-180,180,.5,x=>ChangeLayer(l=>l.RotationDegrees=(float)x),220));
        controls.AddChild(Ui.Label("透明度",15,Ui.Muted)); controls.AddChild(Number(.65,.05,1,.05,x=>ChangeLayer(l=>l.Opacity=(float)x),220));
        controls.AddChild(Ui.Button("選択レイヤーを削除",()=>_routeView.RemoveSelected()));
        controls.AddChild(Ui.Label("ホイール：拡大縮小\n中・右ドラッグ：表示移動\n左ドラッグ：画像移動",14,Ui.Muted));
        _routeView.LayersChanged+=RefreshLayers;
        _overlayFiles.ItemSelected+=i=>_routeView.SelectedLayer=(int)i;
        _csvDialog=new FileDialog { FileMode=FileDialog.FileModeEnum.OpenFile,Access=FileDialog.AccessEnum.Filesystem,UseNativeDialog=true }; _csvDialog.AddFilter("*.csv","EcoLogger CSV"); AddChild(_csvDialog); _csvDialog.FileSelected+=path=>LoadRoute(path);
        _imageDialog=new FileDialog { FileMode=FileDialog.FileModeEnum.OpenFile,Access=FileDialog.AccessEnum.Filesystem,UseNativeDialog=true }; foreach(var f in new[]{"*.png","*.jpg,*.jpeg","*.webp","*.bmp","*.svg"})_imageDialog.AddFilter(f); AddChild(_imageDialog);
        _imageDialog.FileSelected+=path=> { if(!_routeView.AddLayer(path))_notice="画像を開けませんでした。"; };
    }
    private async void RefreshSolveLogs()
    {
        if(_solveRefreshing)return;
        if(_connection.Info.State!="connected") { _solveStatus.Text="EcoLoggerを接続してください"; return; }
        _solveRefreshing=true; _solveConnectionSeen=_connection.Info.Connections;
        try { _solveStatus.Text="SDを確認中"; _remoteFiles=(await new LogTransfer(_connection).ListAsync()).ToList(); _remoteLogs=LogTransfer.OrderedPrimaryLogs(_remoteFiles);
            _solveFiles.Clear(); foreach(var f in _remoteLogs)_solveFiles.AddItem($"{(f.Active?"記録中  ":"")}{f.Name}   {f.Size/1024d:0.0} KB"); _solveStatus.Text=_remoteLogs.Count==0?"走行ログがありません":$"{_remoteLogs.Count}件 · 新しい順"; }
        catch(Exception e){_solveStatus.Text="SDを読めません: "+e.Message;}
        finally{_solveRefreshing=false;}
    }
    private async void OpenRemoteLog()
    {
        if(_solveFiles.Selected<0||_solveFiles.Selected>=_remoteLogs.Count)return; var file=_remoteLogs[_solveFiles.Selected]; _solveCancel?.Cancel(); _solveCancel=new(); var transfer=new LogTransfer(_connection);
        try
        {
            _solveStatus.Text=file.Active?"記録を区切っています":"SDから取得中"; var progress=new Progress<double>(x=>_solveProgress.Value=x); var dir=Path.Combine(_data,"solve-data",Path.GetFileNameWithoutExtension(file.Name)); string path;
            if(file.Active)
            {
                await _connection.QueryAsync("rotateLog",null,_solveCancel.Token);
                for(var i=0;i<40;i++) { await Task.Delay(250,_solveCancel.Token); _remoteFiles=(await transfer.ListAsync(_solveCancel.Token)).ToList(); var closed=_remoteFiles.FirstOrDefault(x=>x.Name==file.Name); if(closed!=null&&!closed.Active){file=closed;break;} }
                if(file.Active)throw new IOException("記録中ログの区切りを確認できませんでした。");
                _remoteLogs=LogTransfer.OrderedPrimaryLogs(_remoteFiles);
            }
            _solveStatus.Text="SDから取得中"; path=await transfer.DownloadAsync(file,dir,progress,_solveCancel.Token);
            foreach(var suffix in new[]{".meta.json",".end.json"}) { var companion=_remoteFiles.FirstOrDefault(x=>x.Name==Path.GetFileNameWithoutExtension(file.Name)+suffix); if(companion!=null) await transfer.DownloadAsync(companion,dir,null,_solveCancel.Token); }
            LoadRoute(path);
        }
        catch(Exception e) when(e is IOException or TimeoutException or OperationCanceledException) { _solveStatus.Text="取得できません: "+e.Message; }
    }
    private async void LoadRoute(string path)
    {
        try { _solveStatus.Text="経路を解析中"; var data=await Task.Run(()=>RouteParser.Load(path)); _solvePath=path; _routeView.SetData(data); var s=data.Summary; _solveSummary.Text=$"{Path.GetFileName(path)}    平均 {s.AverageSpeedKmh:0.0} km/h    最高 {s.MaximumSpeedKmh:0.0} km/h    距離 {s.DistanceKm:0.00} km    時間 {RaceSession.FormatTime(s.DurationSeconds)}"; _solveSelect.Visible=false; _solveRoute.Visible=true; }
        catch(Exception e) when(e is IOException or FormatException or UnauthorizedAccessException) { _solveStatus.Text="開けません: "+e.Message; }
    }
    private void ShowSolveSelection(){_solveRoute.Visible=false;_solveSelect.Visible=true;}
    private void ChangeLayer(Action<RouteOverlay> change){var i=_routeView.SelectedLayer;if(i<0||i>=_routeView.Layers.Count)return;change(_routeView.Layers[i]);_routeView.QueueRedraw();}
    private void RefreshLayers(){_overlayFiles.Clear();foreach(var l in _routeView.Layers)_overlayFiles.AddItem(Path.GetFileName(l.Path));if(_routeView.SelectedLayer>=0)_overlayFiles.Selected=_routeView.SelectedLayer;}
}
