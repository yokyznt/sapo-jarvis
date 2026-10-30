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
    bool _thinking, _listening;
    string _confirmId, _confirmText;
    float _confirmT;
    const float ButtonH = 30f;
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
        if (_confirmId != null)
        {
            _confirmT += dt;
            if (_confirmT > 30f) _confirmId = null;
        }
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
            _quiet = false;
            _speaking = false;
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
                case "listening":
                    _listening = root.GetProperty("on").GetBoolean();
                    if (_listening) { _gazeTarget = Vector2.Zero; _gazeTimer = 1f; }
                    break;
                case "confirm":
                    _confirmId = root.GetProperty("id").GetString();
                    _confirmText = root.GetProperty("text").GetString() ?? "";
                    _confirmT = 0f;
                    _thinking = false;
                    break;
                case "speaking":
                    _speaking = root.GetProperty("on").GetBoolean();
                    if (_speaking) _player?.Stop();
                    else _mouthLevel = 0f;
                    break;
                case "mouth":
                    if (_speaking) SetMouth(root.GetProperty("level").GetSingle());
                    break;
                case "quiet":
                    _quiet = root.GetProperty("on").GetBoolean();
                    if (_quiet) _player?.Stop();
                    break;
                case "croak":
                    Croak(root.GetProperty("kind").GetString() ?? "corto");
                    break;
                case "confirm_reply":
                case "confirm_done":
                    _confirmId = null;
                    break;
            }
        }
        catch (JsonException) { }
        catch (KeyNotFoundException) { }
        catch (System.InvalidOperationException) { }
        catch (System.FormatException) { }
    }

    int BubbleFontSize => (int)Mathf.Max(13f, R * 0.34f);

    bool BubbleRect(out Rect2 rect, out string text, out float alpha)
    {
        rect = default;
        text = null;
        alpha = 0f;
        if (_hidden) return false;
        bool confirm = _confirmId != null;
        if (confirm)
        {
            text = _confirmText;
            float fadeIn = Mathf.Clamp(_confirmT / 0.18f, 0f, 1f);
            alpha = 1f - (1f - fadeIn) * (1f - fadeIn);
        }
        else if (_bubbleT < _bubbleLife)
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
        var box = size + new Vector2(pad * 2f, pad * 2f + (confirm ? ButtonH + 8f : 0f));
        if (confirm) box.X = Mathf.Max(box.X, 170f);
        var o = _pos - Origin;
        var pos = new Vector2(o.X - box.X * 0.5f, o.Y - R * 1.45f - _hop.V - box.Y - 12f + (1f - alpha) * 6f);
        var area = Area;
        var lo = (Vector2)area.Position - Origin;
        var hi = (Vector2)area.End - Origin;
        pos.X = Mathf.Clamp(pos.X, lo.X + 8f, hi.X - box.X - 8f);
        pos.Y = Mathf.Max(lo.Y + 8f, pos.Y);
        rect = new Rect2(pos, box);
        return true;
    }

    (Rect2 yes, Rect2 no) ConfirmButtons(Rect2 rect)
    {
        float w = (rect.Size.X - 30f) * 0.5f;
        float y = rect.End.Y - 10f - ButtonH;
        return (new Rect2(rect.Position.X + 10f, y, w, ButtonH), new Rect2(rect.Position.X + 20f + w, y, w, ButtonH));
    }

    bool ConfirmClick(Vector2 screen)
    {
        if (_confirmId == null || !BubbleRect(out var rect, out _, out _)) return false;
        var local = screen - Origin;
        var (yes, no) = ConfirmButtons(rect);
        bool? ok = yes.HasPoint(local) ? true : no.HasPoint(local) ? false : null;
        if (ok is null) return rect.HasPoint(local);
        Send(new Dictionary<string, object> { ["type"] = "confirm_reply", ["id"] = _confirmId, ["ok"] = ok.Value });
        _confirmId = null;
        return true;
    }

    void DrawListening(Vector2 o)
    {
        if (!_listening || _hidden) return;
        for (int s = -1; s <= 1; s += 2)
            for (int i = 0; i < 3; i++)
            {
                float t = Mathf.PosMod(_time * 1.5f + i / 3f, 1f);
                var c = o + new Vector2(s * R * 1.25f, -R * 0.2f - _hop.V);
                float a0 = s > 0 ? -0.3f * Mathf.Pi : 0.7f * Mathf.Pi;
                DrawArc(c, R * (0.25f + t * 0.45f), a0, a0 + 0.6f * Mathf.Pi, 10, new Color(Ink, 1f - t), 3.5f, true);
            }
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
        if (_confirmId == null) return;
        var (yes, no) = ConfirmButtons(rect);
        DrawPill(yes, "Sí", Skin, ink, alpha);
        DrawPill(no, "No", new Color(0.93f, 0.93f, 0.93f), ink, alpha);
    }

    void DrawPill(Rect2 r, string label, Color fill, Color ink, float alpha)
    {
        var st = new StyleBoxFlat { BgColor = new Color(fill, alpha), BorderColor = ink, AntiAliasing = true };
        st.SetBorderWidthAll(2);
        st.SetCornerRadiusAll((int)(ButtonH * 0.5f));
        DrawStyleBox(st, r);
        var font = ThemeDB.FallbackFont;
        int fs = BubbleFontSize;
        var sz = font.GetStringSize(label, HorizontalAlignment.Left, -1, fs);
        DrawString(font, r.Position + new Vector2((r.Size.X - sz.X) * 0.5f, (r.Size.Y + font.GetAscent(fs) - font.GetDescent(fs)) * 0.5f), label, HorizontalAlignment.Left, -1, fs, ink);
    }
}
