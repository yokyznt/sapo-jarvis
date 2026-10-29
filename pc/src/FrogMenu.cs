using System;
using System.Collections.Generic;
using System.Text.Json.Nodes;
using Godot;

namespace Sapo;

public partial class Frog
{
    enum Energy { Zen, Normal, Travieso }

    sealed class MenuItem
    {
        public string Id, Label;
        public Rect2 Rect;
        public float Hover;
    }

    static readonly string[] EnergyNames = { "Zen", "Normal", "Travieso" };
    static readonly float[] Sizes = { 0.8f, 1f, 1.25f };
    static readonly string[] SizeNames = { "Chico", "Mediano", "Grande" };

    List<Sapo.Skin> _skins;
    Sapo.Skin _skin = Sapo.Skin.Default;
    Energy _energy = Energy.Normal;
    int _sizeIdx = 1;
    float _baseR;
    bool _pinned, _dropThrough, _prevRmb, _menuOpen;
    Vector2 _pin;
    float _jumpTimer = 25f, _menuT, _menuIdle;
    readonly List<MenuItem> _menu = new();

    Color Skin => _skin.Body;
    Color Ink => _skin.Outline;
    Color Cheek => _skin.Cheek;
    Color TongueColor => _skin.Tongue;
    Color MouthColor => _skin.Mouth;

    void LoadPrefs()
    {
        _skins = Sapo.Skin.LoadAll();
        var id = Config.GetString("skin", "clasico");
        _skin = _skins.Find(s => s.Id == id) ?? _skins[0];
        _energy = Enum.TryParse<Energy>(Config.GetString("energy", "Normal"), out var e) ? e : Energy.Normal;
        _sizeIdx = Math.Clamp((int)Config.GetFloat("size", 1), 0, Sizes.Length - 1);
        ResetJumpTimer();
    }

    float SizeScale => Sizes[_sizeIdx];

    void ApplySize()
    {
        float foot = _pos.Y + (_jelly?.Bottom ?? 0f);
        R = _baseR * SizeScale;
        _jelly = new Jelly(R);
        if (_pos != Vector2.Zero) _pos.Y = foot - _jelly.Bottom;
        if (_pinned) PlaceOnPin();
    }

    void ResetJumpTimer()
    {
        var (a, b) = _energy switch
        {
            Energy.Zen => (60f, 180f),
            Energy.Normal => (20f, 60f),
            _ => (6f, 18f)
        };
        _jumpTimer = _rng.RandfRange(a, b);
    }

    void RestorePin()
    {
        if (Config.GetPin() is not { } p) return;
        var v = new Vector2(p.x, p.y);
        foreach (var a in _desk.Areas)
            if (_desk.Allowed(a) && a.Work.HasPoint((Vector2I)v.Round()))
            {
                Pin(v, false);
                return;
            }
    }

    void Pin(Vector2 foot, bool save = true)
    {
        _pinned = true;
        _pin = foot;
        EndTongue();
        EndDance();
        PlaceOnPin();
        if (save) Config.SetPin((foot.X, foot.Y));
    }

    void PlaceOnPin()
    {
        _pos = new Vector2(_pin.X, _pin.Y - _jelly.Bottom - 8f);
        _vel = Vector2.Zero;
        _platform = new Platform(IntPtr.Zero, (int)_pin.Y, (int)(_pin.X - R * 2f), (int)(_pin.X + R * 2f));
        if (_state != State.Sleep) _state = State.Idle;
    }

    void Unpin()
    {
        _pinned = false;
        Config.SetPin(null);
        _state = State.Air;
        _platform = null;
        _vel = new Vector2(0, -420f);
    }

    Vector2 PadCenter => _pinned && _state != State.Held ? _pin : new Vector2(_pos.X, _pos.Y + _jelly.Bottom + 8f);

    bool OnPad(Vector2 c)
    {
        if (!_pinned) return false;
        var d = c - PadCenter;
        float rx = R * 1.8f, ry = R * 0.5f;
        return d.X * d.X / (rx * rx) + d.Y * d.Y / (ry * ry) <= 1f;
    }

    bool Open(Vector2 p)
    {
        foreach (var a in _desk.Areas)
            if (_desk.Allowed(a) && a.Work.HasPoint((Vector2I)p.Round())) return true;
        return false;
    }

    bool HopMonitor()
    {
        if (_pinned || _state != State.Idle) return false;
        var cur = _desk.AreaAt(_pos).Work;
        var opts = new List<(Rect2I w, int dir)>();
        foreach (var a in _desk.Areas)
        {
            if (!_desk.Allowed(a) || a.Work == cur) continue;
            var w = a.Work;
            bool xo = w.Position.X < cur.End.X - R * 3 && w.End.X > cur.Position.X + R * 3;
            bool yo = w.Position.Y < cur.End.Y - R * 3 && w.End.Y > cur.Position.Y + R * 3;
            if (xo && Mathf.Abs(w.End.Y - cur.Position.Y) < 80) opts.Add((w, -1));
            else if (xo && Mathf.Abs(w.Position.Y - cur.End.Y) < 80) opts.Add((w, 1));
            else if (yo && (Mathf.Abs(w.Position.X - cur.End.X) < 80 || Mathf.Abs(w.End.X - cur.Position.X) < 80)) opts.Add((w, 0));
        }
        if (opts.Count == 0) return false;
        var (t, dir) = opts[_rng.RandiRange(0, opts.Count - 1)];
        float b = _jelly.Bottom;
        if (dir == 1)
        {
            _dropThrough = true;
            _jumpVel = new Vector2(_rng.RandfRange(-120f, 120f), -520f);
        }
        else if (dir == -1)
        {
            float lo = Mathf.Max(t.Position.X, cur.Position.X) + R * 2f, hi = Mathf.Min(t.End.X, cur.End.X) - R * 2f;
            float tx = Mathf.Clamp(_pos.X + _rng.RandfRange(-R * 6f, R * 6f), lo, hi);
            float apex = t.End.Y - b - R * 3f;
            float vy = -Mathf.Sqrt(2f * Gravity * Mathf.Max(R, _pos.Y - apex));
            float time = -vy / Gravity + Mathf.Sqrt(2f * R * 3f / Gravity);
            _jumpVel = new Vector2((tx - _pos.X) / time, vy);
        }
        else
        {
            float tx = t.Position.X > _pos.X ? t.Position.X + R * 4f : t.End.X - R * 4f;
            float ty = t.End.Y - b;
            float apex = Mathf.Min(_pos.Y, ty) - R * 3f;
            float vy = -Mathf.Sqrt(2f * Gravity * Mathf.Max(R, _pos.Y - apex));
            float time = -vy / Gravity + Mathf.Sqrt(2f * Mathf.Max(1f, ty - apex) / Gravity);
            _jumpVel = new Vector2(Mathf.Clamp((tx - _pos.X) / time, -2600f, 2600f), vy);
        }
        _state = State.Crouch;
        _crouchTimer = 0.28f;
        _jelly.Squash(R * 0.4f);
        return true;
    }

    void OpenMenu()
    {
        _menu.Clear();
        _menuOpen = true;
        _menuT = 0f;
        _menuIdle = 0f;
        Add("pin", _pinned ? "Soltar" : "Fijar aquí");
        Add("sleep", _calm ? "Despertar" : "Dormir");
        Add("skin", "Diseño: " + _skin.Name);
        Add("energy", "Energía: " + EnergyNames[(int)_energy]);
        Add("size", "Tamaño: " + SizeNames[_sizeIdx]);
        Add("quit", "Salir");
        LayoutMenu();
    }

    void Add(string id, string label) => _menu.Add(new MenuItem { Id = id, Label = label });

    void LayoutMenu()
    {
        var font = ThemeDB.FallbackFont;
        int fs = BubbleFontSize;
        var area = _desk.AreaAt(_pos).Work;
        int n = _menu.Count, half = (n + 1) / 2;
        float gap = 8f, colX = R * 1.75f;
        for (int i = 0; i < n; i++)
        {
            var it = _menu[i];
            var sz = font.GetStringSize(it.Label, HorizontalAlignment.Left, -1, fs) + new Vector2(28f, 14f);
            bool left = i < half;
            int row = left ? i : i - half;
            int rows = left ? half : n - half;
            float y = _pos.Y - R * 0.25f + (row - (rows - 1) * 0.5f) * (sz.Y + gap) - sz.Y * 0.5f;
            float x = left ? _pos.X - colX - sz.X : _pos.X + colX;
            var pos = new Vector2(x, y);
            if (pos.X < area.Position.X + 6f) pos.X = _pos.X + colX;
            if (pos.X + sz.X > area.End.X - 6f) pos.X = _pos.X - colX - sz.X;
            pos.X = Mathf.Clamp(pos.X, area.Position.X + 6f, area.End.X - sz.X - 6f);
            pos.Y = Mathf.Clamp(pos.Y, area.Position.Y + 6f, area.End.Y - sz.Y - 6f);
            it.Rect = new Rect2(pos, sz);
        }
    }

    void CloseMenu() => _menuOpen = false;

    void UpdateMenu(float dt)
    {
        if (!_menuOpen) return;
        _menuT += dt;
        bool any = false;
        foreach (var it in _menu)
        {
            bool h = it.Rect.HasPoint(_cursor);
            any |= h;
            it.Hover = Mathf.MoveToward(it.Hover, h ? 1f : 0f, dt / 0.12f);
        }
        _menuIdle = any ? 0f : _menuIdle + dt;
        if (_menuIdle > 7f) CloseMenu();
    }

    bool MenuClick(Vector2 c)
    {
        if (!_menuOpen) return false;
        foreach (var it in _menu)
        {
            if (!it.Rect.HasPoint(c)) continue;
            RunMenu(it.Id);
            return true;
        }
        CloseMenu();
        return OnFrog(c);
    }

    void RunMenu(string id)
    {
        switch (id)
        {
            case "pin":
                CloseMenu();
                if (_pinned) Unpin();
                else Pin(new Vector2(_pos.X, _pos.Y + _jelly.Bottom + 8f));
                return;
            case "sleep":
                _calm = !_calm;
                CloseMenu();
                return;
            case "skin":
                _skin = _skins[(_skins.IndexOf(_skin) + 1) % _skins.Count];
                Config.Set("skin", JsonValue.Create(_skin.Id));
                _happy = 0.8f;
                break;
            case "energy":
                _energy = (Energy)(((int)_energy + 1) % 3);
                Config.Set("energy", JsonValue.Create(_energy.ToString()));
                ResetJumpTimer();
                break;
            case "size":
                _sizeIdx = (_sizeIdx + 1) % Sizes.Length;
                Config.Set("size", JsonValue.Create(_sizeIdx));
                ApplySize();
                break;
            case "quit":
                GetTree().Quit();
                return;
        }
        var keep = _menuT;
        OpenMenu();
        _menuT = Mathf.Max(keep, 1f);
    }

    void AddMenuRegion(List<Vector2> pts)
    {
        if (!_menuOpen) return;
        foreach (var it in _menu)
        {
            var r = it.Rect.Grow(4f);
            pts.Add(r.Position - Origin);
            pts.Add(new Vector2(r.End.X, r.Position.Y) - Origin);
            pts.Add(new Vector2(r.Position.X, r.End.Y) - Origin);
            pts.Add(r.End - Origin);
        }
    }

    void DrawMenu()
    {
        if (!_menuOpen) return;
        var font = ThemeDB.FallbackFont;
        int fs = BubbleFontSize;
        for (int i = 0; i < _menu.Count; i++)
        {
            var it = _menu[i];
            float t = Mathf.Clamp((_menuT - i * 0.035f) / 0.16f, 0f, 1f);
            float e = 1f - (1f - t) * (1f - t) * (1f - t);
            if (e <= 0f) continue;
            var r = it.Rect;
            var c = r.GetCenter() - Origin;
            var from = _pos - Origin;
            var center = from.Lerp(c, 0.3f + 0.7f * e);
            float s = 0.92f + 0.08f * e + it.Hover * 0.04f;
            var rect = new Rect2(center - r.Size * 0.5f * s, r.Size * s);
            var st = new StyleBoxFlat { BgColor = new Color(Colors.White.Lerp(Skin, it.Hover * 0.7f), e), BorderColor = new Color(Ink, e), AntiAliasing = true };
            st.SetBorderWidthAll(3);
            st.SetCornerRadiusAll((int)(rect.Size.Y * 0.5f));
            DrawStyleBox(st, rect);
            var tsz = font.GetStringSize(it.Label, HorizontalAlignment.Left, -1, fs);
            DrawString(font, rect.Position + new Vector2((rect.Size.X - tsz.X) * 0.5f, (rect.Size.Y + font.GetAscent(fs) - font.GetDescent(fs)) * 0.5f), it.Label, HorizontalAlignment.Left, -1, fs, new Color(Ink, e));
        }
    }

    void DrawPad()
    {
        if (!_pinned) return;
        var c = PadCenter - Origin + new Vector2(0, Mathf.Sin(_time * 1.3f) * 1.5f);
        float rx = R * 1.75f, ry = R * 0.46f;
        var pad = new Color("8fd07a");
        var dark = new Color("6db35a");
        var pts = new List<Vector2> { c };
        for (int i = 0; i <= 40; i++)
        {
            float a = Mathf.Lerp(-0.42f * Mathf.Pi, 1.42f * Mathf.Pi, i / 40f);
            pts.Add(c + new Vector2(Mathf.Cos(a) * rx, Mathf.Sin(a) * ry));
        }
        var arr = pts.ToArray();
        var closed = new Vector2[arr.Length + 1];
        arr.CopyTo(closed, 0);
        closed[^1] = arr[0];
        if (Geometry2D.TriangulatePolygon(arr).Length > 0) DrawColoredPolygon(arr, pad);
        DrawPolyline(closed, Ink, 5f, true);
        for (int i = 0; i < 5; i++)
        {
            float a = Mathf.Lerp(0.05f, 0.95f, i / 4f) * Mathf.Pi + Mathf.Pi;
            DrawLine(c + new Vector2(0, ry * 0.1f), c + new Vector2(Mathf.Cos(a) * rx * 0.72f, Mathf.Sin(a) * ry * 0.72f), dark, 2.5f, true);
        }
        var f = c + new Vector2(rx * 0.72f, -ry * 0.15f);
        for (int i = 0; i < 5; i++)
        {
            float a = Mathf.Tau * i / 5f - Mathf.Pi * 0.5f;
            DrawCircle(f + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * R * 0.11f, R * 0.1f, new Color("ffc1d6"), true, -1f, true);
        }
        DrawCircle(f, R * 0.07f, new Color("ffd65a"), true, -1f, true);
    }

    void AddPadRegion(List<Vector2> pts)
    {
        if (!_pinned) return;
        var c = PadCenter - Origin;
        for (int i = 0; i < 12; i++)
        {
            float a = Mathf.Tau * i / 12f;
            pts.Add(c + new Vector2(Mathf.Cos(a) * R * 1.9f, Mathf.Sin(a) * R * 0.6f));
        }
    }
}
