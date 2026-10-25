using System.Collections.Generic;
using System.Text;
using System.Text.Json;
using Godot;

namespace Sapo;

public partial class Frog
{
    string BrainUrl = "ws://127.0.0.1:8765";
    WebSocketPeer _ws;
    bool _wsOpen;
    float _wsRetry;
    string _bubble = "";
    float _bubbleT = 99f, _bubbleLife;
    bool _thinking;
    StyleBoxFlat _bubbleStyle;

    void SetupBubble()
    {
        _bubbleStyle = new StyleBoxFlat { BgColor = Colors.White, BorderColor = Ink };
        _bubbleStyle.SetBorderWidthAll(3);
        _bubbleStyle.SetCornerRadiusAll(14);
        _bubbleStyle.AntiAliasing = true;
    }

    void PollBrain(float dt)
    {
        _bubbleT += dt;
        if (_ws == null)
        {
            _wsRetry -= dt;
            if (_wsRetry > 0f) return;
            _wsRetry = 5f;
            _ws = new WebSocketPeer();
            if (_ws.ConnectToUrl(BrainUrl) != Error.Ok) _ws = null;
            return;
        }
        _ws.Poll();
        var st = _ws.GetReadyState();
        if (st == WebSocketPeer.State.Open)
        {
            if (!_wsOpen)
            {
                _wsOpen = true;
                Send(new Dictionary<string, object> { ["type"] = "hello", ["version"] = 1 });
            }
            while (_ws.GetAvailablePacketCount() > 0) Handle(Encoding.UTF8.GetString(_ws.GetPacket()));
        }
        else if (st == WebSocketPeer.State.Closed)
        {
            _ws = null;
            _wsOpen = false;
            _thinking = false;
        }
    }

    void Send(Dictionary<string, object> msg)
    {
        if (_wsOpen) _ws.SendText(JsonSerializer.Serialize(msg));
    }

    void SendEvent(string name) => Send(new Dictionary<string, object> { ["type"] = "event", ["name"] = name, ["boredom"] = _boredom });

    void Handle(string raw)
    {
        try
        {
            using var doc = JsonDocument.Parse(raw);
            var root = doc.RootElement;
            switch (root.GetProperty("type").GetString())
            {
                case "say":
                    var text = root.GetProperty("text").GetString() ?? "";
                    if (text.Length == 0) return;
                    _bubble = text;
                    _bubbleT = 0f;
                    _bubbleLife = Mathf.Clamp(2.5f + text.Length * 0.06f, 3f, 9f);
                    _thinking = false;
                    if (root.TryGetProperty("mood", out var mood) && mood.GetString() == "happy") _happy = 1.2f;
                    break;
                case "action":
                    DoAction(root.GetProperty("name").GetString() ?? "none");
                    break;
                case "thinking":
                    _thinking = root.GetProperty("on").GetBoolean();
                    break;
            }
        }
        catch (JsonException) { }
        catch (KeyNotFoundException) { }
        catch (System.InvalidOperationException) { }
    }

    int BubbleFontSize => (int)Mathf.Max(13f, R * 0.34f);

    bool BubbleRect(out Rect2 rect, out string text, out float alpha)
    {
        rect = default;
        text = null;
        alpha = 0f;
        if (_hidden) return false;
        if (_bubbleT < _bubbleLife)
        {
            text = _bubble;
            float fadeIn = Mathf.Clamp(_bubbleT / 0.18f, 0f, 1f);
            float fadeOut = Mathf.Clamp((_bubbleLife - _bubbleT) / 0.2f, 0f, 1f);
            alpha = Mathf.Min(1f - (1f - fadeIn) * (1f - fadeIn), fadeOut);
        }
        else if (_thinking)
        {
            text = new string('.', 1 + (int)(_time * 3f) % 3).PadRight(3);
            alpha = 1f;
        }
        else return false;
        var font = ThemeDB.FallbackFont;
        float maxW = R * 5.5f;
        var size = font.GetMultilineStringSize(text, HorizontalAlignment.Left, maxW, BubbleFontSize);
        float pad = 10f;
        var box = size + new Vector2(pad * 2f, pad * 2f);
        var o = _pos - Origin;
        var pos = new Vector2(o.X - box.X * 0.5f, o.Y - R * 1.45f - _hop.V - box.Y - 12f + (1f - alpha) * 6f);
        var ws = (Vector2)_desk.Work.Size;
        pos.X = Mathf.Clamp(pos.X, 8f, ws.X - box.X - 8f);
        pos.Y = Mathf.Max(8f, pos.Y);
        rect = new Rect2(pos, box);
        return true;
    }

    void DrawBubble()
    {
        if (!BubbleRect(out var rect, out var text, out var alpha)) return;
        var font = ThemeDB.FallbackFont;
        var bg = new Color(1f, 1f, 1f, alpha);
        var ink = new Color(Ink, alpha);
        _bubbleStyle.BgColor = bg;
        _bubbleStyle.BorderColor = ink;
        float tx = Mathf.Clamp(_pos.X - Origin.X, rect.Position.X + 18f, rect.End.X - 18f);
        var tail = new[] { new Vector2(tx - 9f, rect.End.Y - 2f), new Vector2(tx + 9f, rect.End.Y - 2f), new Vector2(tx, rect.End.Y + 12f) };
        DrawColoredPolygon(tail, ink);
        DrawStyleBox(_bubbleStyle, rect);
        DrawColoredPolygon(new[] { tail[0] + new Vector2(3.5f, -3f), tail[1] + new Vector2(-3.5f, -3f), tail[2] + new Vector2(0, -5f) }, bg);
        DrawMultilineString(font, rect.Position + new Vector2(10f, 10f + font.GetAscent(BubbleFontSize)), text, HorizontalAlignment.Left, R * 5.5f, BubbleFontSize, -1, ink);
    }
}
