using Godot;

namespace EcoCapture.UI;

public static class Ui
{
    public static readonly Color Bg = Colors.Black, Panel = Colors.Black, Raised = Colors.Black, Border = new("606060"),
        Text = Colors.White, Muted = new("b8b8b8"), Accent = Colors.White, Amber = new("ff3030"), Red = new("ff3030");
    public static StyleBoxFlat Box(Color color, int radius = 12, int padding = 16, Color? border = null)
    {
        var box = new StyleBoxFlat { BgColor = color, CornerRadiusBottomLeft = 0, CornerRadiusBottomRight = 0,
            CornerRadiusTopLeft = 0, CornerRadiusTopRight = 0, ContentMarginLeft = padding, ContentMarginRight = padding,
            ContentMarginTop = padding, ContentMarginBottom = padding, BorderColor = border ?? Border };
        if (border.HasValue) { box.BorderWidthLeft = box.BorderWidthTop = box.BorderWidthBottom = box.BorderWidthRight = 1; }
        return box;
    }
    public static Label Label(string text, int size = 20, Color? color = null)
    {
        var l = new Label { Text = text, MouseFilter = Control.MouseFilterEnum.Ignore };
        l.AddThemeFontSizeOverride("font_size", size); l.AddThemeColorOverride("font_color", color ?? Text); return l;
    }
    public static Button Button(string text, Action action, bool accent = false)
    {
        var b = new Button { Text = text, CustomMinimumSize = new(0,44), MouseDefaultCursorShape = Control.CursorShape.PointingHand };
        b.AddThemeStyleboxOverride("normal", Box(Raised, 0, 12, accent ? Accent : Border));
        b.AddThemeStyleboxOverride("hover", Box(new Color("282828"), 0, 12, Accent));
        b.AddThemeStyleboxOverride("pressed", Box(new Color("484848"), 0, 12, Accent));
        b.AddThemeFontSizeOverride("font_size", 19); b.Pressed += action; return b;
    }
    public static VBoxContainer VBox(int separation = 12) { var v = new VBoxContainer(); v.AddThemeConstantOverride("separation", separation); return v; }
    public static HBoxContainer HBox(int separation = 12) { var v = new HBoxContainer(); v.AddThemeConstantOverride("separation", separation); return v; }
    public static PanelContainer Card(Control content, int padding = 18)
    { var p = new PanelContainer(); p.AddThemeStyleboxOverride("panel", Box(Panel, 12, padding, Border)); p.AddChild(content); return p; }
    public static void Expand(Control c) { c.SizeFlagsHorizontal = Control.SizeFlags.ExpandFill; c.SizeFlagsVertical = Control.SizeFlags.ExpandFill; }
    public static Control Spacer() => new() { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
    public static Label Note(string text) => new() { Text = text, AutowrapMode = TextServer.AutowrapMode.WordSmart, Modulate = Muted, SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
    public static ProgressBar Bar(double min, double max)
    {
        var p = new ProgressBar { MinValue = min, MaxValue = max, ShowPercentage = false, CustomMinimumSize = new(0,6) };
        p.AddThemeStyleboxOverride("background", Box(new Color("303030"), 0, 0));
        p.AddThemeStyleboxOverride("fill", Box(Accent, 3, 0)); return p;
    }
}
