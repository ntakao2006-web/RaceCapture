using Godot;
using EcoCapture.Core;
using System.Globalization;

namespace EcoCapture.UI;

public partial class MetricTile : PanelContainer
{
    private readonly SensorDefinition _sensor;
    private readonly SensorPreference _preference;
    private Label _value = null!, _state = null!;
    private ProgressBar _bar = null!;
    public MetricTile(SensorDefinition sensor, SensorPreference preference)
    {
        _sensor = sensor; _preference = preference;
        CustomMinimumSize = new(0, 142); SizeFlagsHorizontal = SizeFlags.ExpandFill;
    }
    public override void _Ready()
    {
        AddThemeStyleboxOverride("panel", Ui.Box(Ui.Panel, 10, 16, Ui.Border));
        TooltipText = _sensor.Note;
        var v = Ui.VBox(5); AddChild(v);
        var heading = Ui.HBox(6); v.AddChild(heading);
        var label = Ui.Label(_sensor.Label, 19); label.SizeFlagsHorizontal = SizeFlags.ExpandFill;
        label.TextOverrunBehavior = TextServer.OverrunBehavior.TrimEllipsis; heading.AddChild(label);
        _state = Ui.Label(_sensor.Source, 13, Ui.Muted); heading.AddChild(_state);
        var row = Ui.HBox(8); row.SizeFlagsVertical = SizeFlags.ExpandFill; v.AddChild(row);
        _value = Ui.Label("--", _sensor.Id is "Lat" or "Lon" ? 34 : 45); _value.SizeFlagsHorizontal = SizeFlags.ExpandFill;
        row.AddChild(_value); var unit = Ui.Label(_sensor.Unit, 17, Ui.Muted); unit.VerticalAlignment = VerticalAlignment.Bottom; row.AddChild(unit);
        _bar = Ui.Bar(_sensor.Min, _sensor.Max); _bar.Visible = _preference.Bar; v.AddChild(_bar);
    }
    public void UpdateValue(TelemetryFrame? frame, double now, bool sourceEnabled)
    {
        if (_value == null) return;
        var value = sourceEnabled && frame?.Fresh(now) == true ? frame.Get(_sensor.Id) : null;
        if (_sensor.Id == "AFR" && frame?.Get("AFRValid") != 1) value = null;
        var warn = value.HasValue && _preference.WarningAbove.HasValue && value > _preference.WarningAbove;
        _value.Text = value.HasValue ? value.Value.ToString("F" + (_preference.Precision >= 0 ? _preference.Precision : _sensor.Precision), CultureInfo.InvariantCulture) : "--";
        _value.AddThemeColorOverride("font_color", value.HasValue ? warn ? Ui.Amber : Ui.Text : Ui.Muted);
        _state.Text = !sourceEnabled ? "無効" : warn ? "上限超過" : value.HasValue ? _sensor.Source : "未受信";
        _bar.Value = value ?? _sensor.Min;
        _bar.Modulate = value.HasValue ? Colors.White : new Color(1,1,1,.25f);
    }
}
