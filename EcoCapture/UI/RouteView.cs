using Godot;
using EcoCapture.Core;

namespace EcoCapture.UI;

public sealed class RouteOverlay
{
    public required string Path { get; init; }
    public required ImageTexture Texture { get; init; }
    public Vector2 Position { get; set; }
    public float MetersPerPixel { get; set; }=1;
    public float RotationDegrees { get; set; }
    public float Opacity { get; set; }=.65f;
}

public partial class RouteView : Control
{
    private RouteData? _data; private Vector2[] _points=[]; private Vector2 _pan; private float _zoom=1;
    private bool _panning,_movingLayer; private Vector2 _last; private int _hover=-1;
    public List<RouteOverlay> Layers { get; }=[];
    public int SelectedLayer { get; set; }=-1;
    public int PointCount => _points.Length;
    public event Action? LayersChanged;
    public RouteView() { ClipContents=true; CustomMinimumSize=new(700,440); MouseDefaultCursorShape=CursorShape.Cross; }
    public void SetData(RouteData data) { _data=data; _points=data.Points.Select(p=>new Vector2((float)p.East,(float)-p.North)).ToArray(); CallDeferred(MethodName.Fit); }
    internal void PreviewPoint(int index){_hover=Math.Clamp(index,-1,_points.Length-1);QueueRedraw();}
    public void Fit()
    {
        if(_points.Length==0||Size.X<1) return; var min=_points.Aggregate((a,b)=>a.Min(b)); var max=_points.Aggregate((a,b)=>a.Max(b));
        var span=(max-min).Max(Vector2.One*20); _zoom=Math.Clamp(Math.Min((Size.X-100)/span.X,(Size.Y-100)/span.Y),.01f,1000f); _pan=-(min+max)/2*_zoom; QueueRedraw();
    }
    public bool AddLayer(string path)
    {
        if(Layers.Count>=8||!File.Exists(path)||new FileInfo(path).Length>32*1024*1024)return false;
        using var image=new Image(); if(image.Load(path)!=Error.Ok||image.GetWidth()>8192||image.GetHeight()>8192||(long)image.GetWidth()*image.GetHeight()>8_000_000) return false; image.AdjustBcs(1,1,0);
        var texture=ImageTexture.CreateFromImage(image); var routeSpan=100f;
        if(_points.Length>1) { var min=_points.Aggregate((a,b)=>a.Min(b)); var max=_points.Aggregate((a,b)=>a.Max(b)); routeSpan=Math.Max((max-min).X,(max-min).Y); }
        Layers.Add(new(){Path=path,Texture=texture,MetersPerPixel=Math.Max(.001f,routeSpan/Math.Max(image.GetWidth(),image.GetHeight()))}); SelectedLayer=Layers.Count-1; LayersChanged?.Invoke(); QueueRedraw(); return true;
    }
    public void RemoveSelected() { if(SelectedLayer<0||SelectedLayer>=Layers.Count)return; Layers[SelectedLayer].Texture.Dispose(); Layers.RemoveAt(SelectedLayer); SelectedLayer=Math.Min(SelectedLayer,Layers.Count-1); LayersChanged?.Invoke(); QueueRedraw(); }
    public override void _GuiInput(InputEvent e)
    {
        if(e is InputEventMouseButton mb)
        {
            if(mb.ButtonIndex is MouseButton.WheelUp or MouseButton.WheelDown && mb.Pressed)
            { var before=ScreenToWorld(mb.Position); _zoom=Math.Clamp(_zoom*(mb.ButtonIndex==MouseButton.WheelUp?1.18f:.84746f),.002f,5000); _pan=mb.Position-Size/2-before*_zoom; QueueRedraw(); AcceptEvent(); }
            else if(mb.ButtonIndex is MouseButton.Middle or MouseButton.Right) { _panning=mb.Pressed; _last=mb.Position; AcceptEvent(); }
            else if(mb.ButtonIndex==MouseButton.Left&&SelectedLayer>=0) { _movingLayer=mb.Pressed; _last=mb.Position; AcceptEvent(); }
        }
        else if(e is InputEventMouseMotion motion)
        {
            if(_panning) { _pan+=motion.Position-_last; _last=motion.Position; QueueRedraw(); }
            else if(_movingLayer&&SelectedLayer<Layers.Count) { Layers[SelectedLayer].Position+=(motion.Position-_last)/_zoom; _last=motion.Position; LayersChanged?.Invoke(); QueueRedraw(); }
            else { _hover=Nearest(motion.Position); QueueRedraw(); }
        }
    }
    private Vector2 ScreenToWorld(Vector2 p)=>(p-Size/2-_pan)/_zoom;
    private Vector2 WorldToScreen(Vector2 p)=>Size/2+_pan+p*_zoom;
    private int Nearest(Vector2 screen)
    {
        if(_points.Length==0)return -1; var stride=Math.Max(1,_points.Length/3000); var best=-1; var d=144f;
        for(var i=0;i<_points.Length;i+=stride) { var n=WorldToScreen(_points[i]).DistanceSquaredTo(screen); if(n<d){d=n;best=i;} }
        if(best<0)return -1; int from=Math.Max(0,best-stride),to=Math.Min(_points.Length-1,best+stride); for(var i=from;i<=to;i++){var n=WorldToScreen(_points[i]).DistanceSquaredTo(screen);if(n<d){d=n;best=i;}} return best;
    }
    public override void _Draw()
    {
        DrawRect(new(Vector2.Zero,Size),Colors.Black); for(var x=0f;x<Size.X;x+=50)DrawLine(new(x,0),new(x,Size.Y),new Color("202020")); for(var y=0f;y<Size.Y;y+=50)DrawLine(new(0,y),new(Size.X,y),new Color("202020"));
        foreach(var layer in Layers)
        {
            var size=layer.Texture.GetSize(); DrawSetTransform(Size/2+_pan+layer.Position*_zoom,Mathf.DegToRad(layer.RotationDegrees),Vector2.One*layer.MetersPerPixel*_zoom);
            DrawTextureRect(layer.Texture,new Rect2(-size/2,size),false,new Color(1,1,1,layer.Opacity));
        }
        DrawSetTransform(Vector2.Zero,0,Vector2.One);
        if(_points.Length>1)
        {
            var screen=_points.Select(WorldToScreen).ToArray(); DrawPolyline(screen,Ui.Red,3,true);
            if(_hover>=0&&_data!=null) { var p=WorldToScreen(_points[_hover]); DrawCircle(p,6,Colors.White); var v=_data.Points[_hover]; var text=$"{v.SpeedKmh:0.0} km/h   前後 {v.LongAccel:+0.00;-0.00;0.00} G   左右 {v.LatAccel:+0.00;-0.00;0.00} G   {RaceSession.FormatTime(v.Seconds)}"; var font=ThemeDB.FallbackFont; var width=font.GetStringSize(text,HorizontalAlignment.Left,-1,17).X+24; var box=new Rect2(Math.Clamp(p.X-width/2,8,Size.X-width-8),Math.Clamp(p.Y-54,8,Size.Y-42),width,36); DrawRect(box,Colors.Black); DrawRect(box,Colors.White,false,1); DrawString(font,box.Position+new Vector2(12,24),text,HorizontalAlignment.Left,-1,17,Colors.White); }
        }
        else DrawString(ThemeDB.FallbackFont,Size/2-new Vector2(70,0),"経路データなし",HorizontalAlignment.Left,-1,20,Ui.Muted);
    }
    public override void _ExitTree(){foreach(var l in Layers)l.Texture.Dispose();}
}
