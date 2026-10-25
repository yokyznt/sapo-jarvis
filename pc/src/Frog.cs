using System;
using System.Collections.Generic;
using Godot;

namespace Sapo;

public partial class Frog : Node2D
{
    enum State { Idle, Crouch, Air, Held, Tongue, Sleep }
    enum Grab { Cursor, Window }

    const float Gravity = 2600f;
    static readonly Color Skin = new("b6dc9b");
    static readonly Color Ink = new("1c1c1c");
    static readonly Color Freckle = new("f7a3a0");
    static readonly Color TongueColor = new("ff6b8a");
    static readonly Color MouthColor = new("8a1f35");
    static readonly Color Heart = new("ff4d6d");

    Desktop _desk;
    IntPtr _hwnd;
    Jelly _jelly;
    readonly RandomNumberGenerator _rng = new();
    float R;
    Vector2 _pos, _vel, _prevVel, _jumpVel;
    State _state = State.Air;
    Platform? _platform;
    Vector2I _platformWinPos;
    float _boredom, _actionTimer = 2f, _blinkTimer = 3f, _blink, _crouchTimer, _refreshTimer, _time, _happy;
    bool _calm, _hidden, _prevS, _prevLmb, _pressedOnFrog;
    Vector2 _cursor, _cursorVel, _grabOffset, _pressPos;
    float _pressTime;
    int _tonguePhase = -1;
    float _tongueT;
    Grab _grab;
    Vector2 _tip, _tongueFrom, _tongueTo, _winGrabOffset;
    IntPtr _tongueHwnd;
    Vector2I _winStart;
    IntPtr _stompHwnd;
    Vector2I _stompStart;
    float _stompT = -1f;
    Vector2[] _region = Array.Empty<Vector2>();

    bool CanTouch => !_calm && !_hidden && !_desk.GameRunning;
    bool Grounded => _state is State.Idle or State.Crouch or State.Tongue or State.Sleep;
    Vector2 Origin => _desk.Work.Position;

    public override void _Ready()
    {
        var mons = Desktop.Monitors();
        int idx = -1;
        Vector2I? at = null;
        foreach (var a in OS.GetCmdlineUserArgs())
        {
            if (a.StartsWith("--monitor=")) int.TryParse(a[10..], out idx);
            if (a.StartsWith("--boredom=") && float.TryParse(a[10..], System.Globalization.CultureInfo.InvariantCulture, out var bo)) _boredom = Mathf.Clamp(bo, 0f, 1f);
            if (a.StartsWith("--point="))
            {
                var xy = a[8..].Split(',');
                if (xy.Length == 2 && int.TryParse(xy[0], out var px) && int.TryParse(xy[1], out var py)) at = new Vector2I(px, py);
            }
        }
        if (at is { } pt) idx = mons.FindIndex(m => m.Monitor.HasPoint(pt));
        for (int i = 0; i < mons.Count; i++)
            GD.Print($"monitor {i}: {mons[i].Monitor} work {mons[i].Work} primary={mons[i].Primary}");
        var area = idx >= 0 && idx < mons.Count ? mons[idx] : mons.Find(m => m.Primary);
        _hwnd = (IntPtr)DisplayServer.WindowGetNativeHandle(DisplayServer.HandleType.WindowHandle);
        _desk = new Desktop(_hwnd, area);
        R = 46f * Mathf.Max(0.75f, area.Monitor.Size.Y / 1080f);
        _jelly = new Jelly(R);
        SetupWindow();
        _pos = new Vector2(area.Work.Position.X + area.Work.Size.X * 0.5f, area.Work.Position.Y + R * 2f);
        _desk.Refresh(MinTopGap);
        _rng.Randomize();
    }

    int MinTopGap => (int)(R * 2.6f);

    void SetupWindow()
    {
        var w = _desk.Work;
        long ex = (long)Win32.GetWindowLongPtr(_hwnd, Win32.GWL_EXSTYLE);
        ex = (ex | Win32.WS_EX_TOOLWINDOW | Win32.WS_EX_NOACTIVATE) & ~Win32.WS_EX_APPWINDOW;
        Win32.ShowWindow(_hwnd, Win32.SW_HIDE);
        Win32.SetWindowLongPtr(_hwnd, Win32.GWL_EXSTYLE, (IntPtr)ex);
        Win32.SetWindowPos(_hwnd, Win32.HWND_TOPMOST, w.Position.X, w.Position.Y, w.Size.X, w.Size.Y, Win32.SWP_NOACTIVATE | Win32.SWP_FRAMECHANGED);
        Win32.ShowWindow(_hwnd, Win32.SW_SHOWNOACTIVATE);
    }

    public override void _Process(double delta)
    {
        float dt = Mathf.Clamp((float)delta, 1f / 240f, 1f / 20f);
        _time += dt;
        PollHotkeys();
        _refreshTimer -= dt;
        if (_refreshTimer <= 0f)
        {
            _refreshTimer = 0.1f;
            _desk.Refresh(MinTopGap);
            UpdateVisibility();
            ValidatePlatform();
        }
        FollowPlatform();
        PollMouse(dt);
        bool asleep = _calm || _desk.GameRunning;
        if (asleep && Grounded && _state != State.Sleep)
        {
            EndTongue();
            _state = State.Sleep;
        }
        if (!asleep && _state == State.Sleep) _state = State.Idle;
        if (!asleep && _state != State.Held) _boredom = Mathf.Min(1f, _boredom + dt / 150f);
        _happy = Mathf.Max(0f, _happy - dt);
        Step(dt);
        UpdateStomp(dt);
        var accel = (_vel - _prevVel) / dt;
        _prevVel = _vel;
        _jelly.Step(dt, accel, Grounded && _platform is { } p ? p.Y - 6f - _pos.Y : float.PositiveInfinity);
        Blink(dt);
        UpdateRegion();
        QueueRedraw();
    }

    void PollHotkeys()
    {
        bool combo = Win32.KeyDown(0x11) && Win32.KeyDown(0x12);
        bool s = combo && Win32.KeyDown(0x53);
        if (s && !_prevS) _calm = !_calm;
        _prevS = s;
        if (combo && Win32.KeyDown(0x51)) GetTree().Quit();
    }

    void UpdateVisibility()
    {
        bool hide = _desk.GameOnOurMonitor;
        if (hide == _hidden) return;
        _hidden = hide;
        Win32.ShowWindow(_hwnd, hide ? Win32.SW_HIDE : Win32.SW_SHOWNOACTIVATE);
        if (!hide) Win32.SetWindowPos(_hwnd, Win32.HWND_TOPMOST, 0, 0, 0, 0, Win32.SWP_NOSIZE | 0x2 | Win32.SWP_NOACTIVATE);
    }

    void PollMouse(float dt)
    {
        Win32.GetCursorPos(out var p);
        var c = new Vector2(p.X, p.Y);
        _cursorVel = _cursorVel.Lerp((c - _cursor) / dt, 0.35f);
        _cursor = c;
        bool lmb = Win32.KeyDown(0x01);
        if (lmb && !_prevLmb && !_hidden && OnFrog(c))
        {
            _pressedOnFrog = true;
            _pressPos = c;
            _pressTime = _time;
            _grabOffset = _pos - c;
            EndTongue();
            _state = State.Held;
            _platform = null;
            _boredom = Mathf.Max(0f, _boredom - 0.3f);
        }
        if (!lmb && _prevLmb && _pressedOnFrog)
        {
            _pressedOnFrog = false;
            bool click = _time - _pressTime < 0.25f && c.DistanceTo(_pressPos) < 8f;
            _state = State.Air;
            _vel = click ? new Vector2(0, -350f) : _cursorVel.LimitLength(3200f);
            if (click) Pet(c);
        }
        _prevLmb = lmb;
    }

    void Pet(Vector2 at)
    {
        _boredom = 0f;
        _happy = 1.6f;
        _jelly.Poke(at - _pos, R * 0.5f);
    }

    bool OnFrog(Vector2 c)
    {
        var d = c - (_pos + new Vector2(0, -R * 0.15f));
        float rx = R * 1.2f, ry = R * 1.15f;
        return d.X * d.X / (rx * rx) + d.Y * d.Y / (ry * ry) <= 1f;
    }

    void Step(float dt)
    {
        switch (_state)
        {
            case State.Idle:
                _actionTimer -= dt;
                if (_actionTimer <= 0f) ChooseAction();
                break;
            case State.Crouch:
                _crouchTimer -= dt;
                if (_crouchTimer <= 0f)
                {
                    _vel = _jumpVel;
                    _state = State.Air;
                    _platform = null;
                }
                break;
            case State.Air:
                Fly(dt);
                break;
            case State.Held:
                _pos = _cursor + _grabOffset;
                _vel = _cursorVel;
                break;
            case State.Tongue:
                StepTongue(dt);
                break;
        }
    }

    void Fly(float dt)
    {
        var w = _desk.Work;
        float b = _jelly.Bottom;
        float prevBottom = _pos.Y + b;
        _vel.Y += Gravity * dt;
        var next = _pos + _vel * dt;
        if (next.X < w.Position.X + R) { next.X = w.Position.X + R; _vel.X = Mathf.Abs(_vel.X) * 0.5f; }
        if (next.X > w.End.X - R) { next.X = w.End.X - R; _vel.X = -Mathf.Abs(_vel.X) * 0.5f; }
        if (next.Y < w.Position.Y + R * 1.4f) { next.Y = w.Position.Y + R * 1.4f; _vel.Y = Mathf.Abs(_vel.Y) * 0.3f; }
        Platform? hit = null;
        if (_vel.Y > 0)
        {
            foreach (var p in _desk.Platforms)
            {
                if (next.X < p.X0 + R * 0.3f || next.X > p.X1 - R * 0.3f) continue;
                if (prevBottom > p.Y + 1 || next.Y + b < p.Y) continue;
                if (hit is null || p.Y < hit.Value.Y) hit = p;
            }
        }
        _pos = next;
        if (_pos.Y + b > w.End.Y) hit = _desk.Platforms[0];
        if (hit is { } h) Land(h);
    }

    void Land(Platform p)
    {
        _pos.Y = p.Y - _jelly.Bottom - 8f;
        _vel = Vector2.Zero;
        _state = State.Idle;
        _platform = p;
        if (p.Hwnd != IntPtr.Zero && Desktop.BoundsOf(p.Hwnd) is { } r) _platformWinPos = r.Position;
        _actionTimer = _rng.RandfRange(0.6f, 1.6f);
        if (p.Hwnd != IntPtr.Zero && CanTouch && _boredom > 0.6f && _rng.Randf() < 0.5f && !Win32.IsZoomed(p.Hwnd)) StartStomp(p.Hwnd);
    }

    void FollowPlatform()
    {
        if (!Grounded || _platform is not { } p || p.Hwnd == IntPtr.Zero) return;
        if (Desktop.BoundsOf(p.Hwnd) is not { } r)
        {
            Fall();
            return;
        }
        var d = r.Position - _platformWinPos;
        if (d == Vector2I.Zero) return;
        _platformWinPos = r.Position;
        _pos += d;
        _platform = p with { Y = r.Position.Y, X0 = p.X0 + d.X, X1 = p.X1 + d.X };
        if (_tonguePhase >= 0) _tongueFrom += d;
    }

    void ValidatePlatform()
    {
        if (!Grounded || _platform is not { } p || p.Hwnd == IntPtr.Zero) return;
        foreach (var q in _desk.Platforms)
            if (q.Hwnd == p.Hwnd && q.Y == p.Y && _pos.X >= q.X0 && _pos.X <= q.X1)
            {
                _platform = q;
                return;
            }
        Fall();
    }

    void Fall()
    {
        EndTongue();
        _platform = null;
        _state = State.Air;
        _vel = new Vector2(0, 50f);
    }

    void ChooseAction()
    {
        float b = _boredom;
        _actionTimer = Mathf.Lerp(4.5f, 1.1f, b) * _rng.RandfRange(0.6f, 1.4f);
        if (CanTouch && b > 0.35f && _rng.Randf() < 0.12f + b * 0.3f && TryTongueCursor()) return;
        if (CanTouch && b > 0.6f && _rng.Randf() < 0.35f && TryTongueWindow()) return;
        if (b < 0.3f && _rng.Randf() < 0.45f) return;
        PlanJump(b);
    }

    void PlanJump(float b)
    {
        float bottom = _pos.Y + _jelly.Bottom;
        float maxUp = Mathf.Lerp(R * 5f, R * 14f, b);
        var cands = new List<Platform>();
        Platform? same = null;
        foreach (var p in _desk.Platforms)
        {
            if (p.X1 - p.X0 < R * 2.6f || p.Y < bottom - maxUp) continue;
            cands.Add(p);
            if (_platform is { } cur && p.Hwnd == cur.Hwnd && p.Y == cur.Y && _pos.X >= p.X0 && _pos.X <= p.X1) same = p;
        }
        if (cands.Count == 0) return;
        var t = same is { } s && _rng.Randf() < 0.55f - b * 0.35f ? s : cands[_rng.RandiRange(0, cands.Count - 1)];
        float tx = _rng.RandfRange(t.X0 + R * 1.3f, t.X1 - R * 1.3f);
        float reach = Mathf.Lerp(R * 10f, R * 30f, b);
        tx = Mathf.Clamp(tx, _pos.X - reach, _pos.X + reach);
        tx = Mathf.Clamp(tx, t.X0 + R * 1.3f, t.X1 - R * 1.3f);
        float ty = t.Y - _jelly.Bottom;
        float apex = Mathf.Min(_pos.Y, ty) - _rng.RandfRange(R * 1.2f, R * (2.5f + b * 4f));
        apex = Mathf.Max(apex, _desk.Work.Position.Y + R * 1.5f);
        if (apex >= _pos.Y - 4f) apex = _pos.Y - R;
        float vy = -Mathf.Sqrt(2f * Gravity * (_pos.Y - apex));
        float time = -vy / Gravity + Mathf.Sqrt(2f * Mathf.Max(1f, ty - apex) / Gravity);
        _jumpVel = new Vector2(Mathf.Clamp((tx - _pos.X) / time, -2200f, 2200f), vy);
        _state = State.Crouch;
        _crouchTimer = 0.15f;
        _jelly.Squash(R * 0.35f);
    }

    Vector2 Mouth() => _pos + new Vector2(0, R * 0.02f);

    bool TryTongueCursor()
    {
        if (Win32.KeyDown(0x01) || Win32.KeyDown(0x02)) return false;
        float d = _cursor.DistanceTo(Mouth());
        if (d > R * 14f || d < R * 1.5f) return false;
        StartTongue(Grab.Cursor, _cursor, IntPtr.Zero);
        return true;
    }

    bool TryTongueWindow()
    {
        var opts = new List<(IntPtr h, Vector2 p)>();
        for (int i = 0; i < _desk.Windows.Count; i++)
        {
            var w = _desk.Windows[i];
            if (w.Maximized || (_platform is { } pl && pl.Hwnd == w.Hwnd)) continue;
            var gp = new Vector2I(w.Rect.Position.X + w.Rect.Size.X / 2, w.Rect.Position.Y + 14);
            if (!_desk.Work.HasPoint(gp) || _desk.PointCovered(gp, i)) continue;
            if (((Vector2)gp).DistanceTo(Mouth()) > R * 14f || OnFrog(gp)) continue;
            opts.Add((w.Hwnd, gp));
        }
        if (opts.Count == 0) return false;
        var (h, p) = opts[_rng.RandiRange(0, opts.Count - 1)];
        StartTongue(Grab.Window, p, h);
        return true;
    }

    void StartTongue(Grab kind, Vector2 target, IntPtr hwnd)
    {
        _grab = kind;
        _tongueHwnd = hwnd;
        _tongueTo = target;
        _tip = Mouth();
        _tonguePhase = 0;
        _tongueT = 0f;
        _state = State.Tongue;
        if (hwnd != IntPtr.Zero && Desktop.BoundsOf(hwnd) is { } r) _winGrabOffset = target - (Vector2)r.Position;
    }

    void StepTongue(float dt)
    {
        var mouth = Mouth();
        switch (_tonguePhase)
        {
            case 0:
                _tongueT = Mathf.Min(1f, _tongueT + dt / 0.16f);
                var goal = _grab == Grab.Cursor ? _cursor : _tongueTo;
                if (_grab == Grab.Window && Desktop.BoundsOf(_tongueHwnd) is { } r) goal = (Vector2)r.Position + _winGrabOffset;
                _tip = mouth.Lerp(goal, EaseOut(_tongueT));
                if (_tongueT >= 1f)
                {
                    _tonguePhase = 1;
                    _tongueT = 0f;
                    _tongueFrom = goal;
                    if (_grab == Grab.Window)
                    {
                        if (Desktop.OuterPosition(_tongueHwnd) is not { } o) { Retract(); return; }
                        _winStart = o;
                    }
                }
                break;
            case 1:
                if (!CanTouch || Win32.KeyDown(0x01)) { Retract(); return; }
                _tongueT = Mathf.Min(1f, _tongueT + dt / 0.6f);
                var end = _grab == Grab.Cursor ? mouth : _tongueFrom + (mouth - _tongueFrom).LimitLength(R * 6f);
                _tip = _tongueFrom.Lerp(end, EaseInOut(_tongueT));
                if (_grab == Grab.Cursor) Win32.SetCursorPos((int)_tip.X, (int)_tip.Y);
                else
                {
                    var np = _winStart + (Vector2I)(_tip - _tongueFrom).Round();
                    Win32.SetWindowPos(_tongueHwnd, IntPtr.Zero, np.X, np.Y, 0, 0, Win32.SWP_NOSIZE | Win32.SWP_NOZORDER | Win32.SWP_NOACTIVATE);
                }
                if (_tongueT >= 1f) Retract();
                break;
            case 2:
                _tongueT = Mathf.Min(1f, _tongueT + dt / 0.12f);
                _tip = _tongueFrom.Lerp(mouth, _tongueT);
                if (_tongueT >= 1f) EndTongue();
                break;
        }
    }

    void Retract()
    {
        _tonguePhase = 2;
        _tongueT = 0f;
        _tongueFrom = _tip;
    }

    void EndTongue()
    {
        _tonguePhase = -1;
        if (_state == State.Tongue) _state = State.Idle;
    }

    void StartStomp(IntPtr h)
    {
        if (Desktop.OuterPosition(h) is not { } o) return;
        _stompHwnd = h;
        _stompStart = o;
        _stompT = 0f;
    }

    void UpdateStomp(float dt)
    {
        if (_stompT < 0f) return;
        _stompT += dt;
        float k = _stompT / 0.45f;
        int dy = k >= 1f ? 0 : (int)(Mathf.Sin(_stompT * 45f) * R * 0.18f * (1f - k));
        Win32.SetWindowPos(_stompHwnd, IntPtr.Zero, _stompStart.X, _stompStart.Y + Mathf.Abs(dy), 0, 0, Win32.SWP_NOSIZE | Win32.SWP_NOZORDER | Win32.SWP_NOACTIVATE);
        if (k >= 1f || !CanTouch)
        {
            Win32.SetWindowPos(_stompHwnd, IntPtr.Zero, _stompStart.X, _stompStart.Y, 0, 0, Win32.SWP_NOSIZE | Win32.SWP_NOZORDER | Win32.SWP_NOACTIVATE);
            _stompT = -1f;
        }
    }

    void Blink(float dt)
    {
        _blinkTimer -= dt;
        if (_blinkTimer <= 0f)
        {
            _blink = 1f;
            _blinkTimer = _rng.RandfRange(2f, 5.5f);
        }
        _blink = Mathf.Max(0f, _blink - dt * 7f);
    }

    static float EaseOut(float t) => 1f - (1f - t) * (1f - t);
    static float EaseInOut(float t) => t * t * (3f - 2f * t);

    (Vector2 l, Vector2 r, float er) Eyes(Vector2 o, Vector2 scale)
    {
        float er = R * 0.38f;
        var l = o + _jelly.At(Mathf.DegToRad(-124f)) * scale * 0.78f + new Vector2(0, -R * 0.2f);
        var r = o + _jelly.At(Mathf.DegToRad(-56f)) * scale * 0.78f + new Vector2(0, -R * 0.2f);
        return (l, r, er);
    }

    Vector2 BodyScale()
    {
        float breath = _state == State.Sleep ? Mathf.Sin(_time * 1.6f) * 0.035f : Grounded ? Mathf.Sin(_time * 2.4f) * 0.015f : 0f;
        return new Vector2(1f - breath * 0.5f, 1f + breath);
    }

    void UpdateRegion()
    {
        var o = _pos - Origin;
        var scale = BodyScale();
        var pts = new List<Vector2>();
        foreach (var p in _jelly.Outline(o, scale, 1)) pts.Add(o + (p - o) * 1.12f);
        var (l, r, er) = Eyes(o, scale);
        AddCircle(pts, l, er + 6f);
        AddCircle(pts, r, er + 6f);
        if (_tonguePhase >= 0) AddCircle(pts, _tip - Origin, R * 0.25f);
        if (_state == State.Sleep || _happy > 0f)
        {
            pts.Add(o + new Vector2(R * 0.4f, -R * 3.2f));
            pts.Add(o + new Vector2(R * 2f, -R * 3.2f));
            pts.Add(o + new Vector2(-R * 0.8f, -R * 3.2f));
        }
        var hull = Geometry2D.ConvexHull(pts.ToArray());
        if (SameRegion(hull)) return;
        _region = hull;
        DisplayServer.WindowSetMousePassthrough(hull);
    }

    bool SameRegion(Vector2[] h)
    {
        if (h.Length != _region.Length) return false;
        for (int i = 0; i < h.Length; i++)
            if (h[i].DistanceSquaredTo(_region[i]) > 1f) return false;
        return true;
    }

    static void AddCircle(List<Vector2> pts, Vector2 c, float r)
    {
        for (int i = 0; i < 10; i++)
        {
            float a = Mathf.Tau * i / 10f;
            pts.Add(c + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * r);
        }
    }

    public override void _Draw()
    {
        if (_hidden) return;
        var o = _pos - Origin;
        var scale = BodyScale();
        var body = _jelly.Outline(o, scale, 4);
        var (el, erp, er) = Eyes(o, scale);
        bool valid = Geometry2D.TriangulatePolygon(body).Length > 0;

        DrawCircle(el, er + 3.5f, Ink, true, -1f, true);
        DrawCircle(erp, er + 3.5f, Ink, true, -1f, true);
        var closed = new Vector2[body.Length + 1];
        body.CopyTo(closed, 0);
        closed[^1] = body[0];
        DrawPolyline(closed, Ink, 8f, true);
        DrawCircle(el, er, Skin, true, -1f, true);
        DrawCircle(erp, er, Skin, true, -1f, true);
        if (valid) DrawColoredPolygon(body, Skin);
        else DrawCircle(o, R, Skin, true, -1f, true);

        DrawEye(el, er, -1);
        DrawEye(erp, er, 1);
        DrawCheeks(o);
        DrawMouth(o);
        if (_tonguePhase >= 0) DrawTongue(Mouth() - Origin, _tip - Origin);
        if (_tonguePhase >= 0) DrawCircle(_tip - Origin, R * 0.17f, TongueColor, true, -1f, true);
        if (_state == State.Sleep) DrawZ(o);
        if (_happy > 0f) DrawHearts(o);
    }

    void DrawTongue(Vector2 from, Vector2 to)
    {
        DrawLine(from, to, TongueColor.Darkened(0.25f), R * 0.2f + 3f, true);
        DrawLine(from, to, TongueColor, R * 0.2f, true);
    }

    void DrawEye(Vector2 c, float er, int side)
    {
        float sr = er * 0.74f;
        bool sleeping = _state == State.Sleep || _blink > 0.35f;
        if (sleeping)
        {
            DrawArc(c + new Vector2(0, -sr * 0.2f), sr * 0.6f, 0.15f * Mathf.Pi, 0.85f * Mathf.Pi, 12, Ink, 4.5f, true);
            return;
        }
        if (_happy > 0f)
        {
            DrawArc(c + new Vector2(0, sr * 0.3f), sr * 0.6f, 1.15f * Mathf.Pi, 1.85f * Mathf.Pi, 12, Ink, 4.5f, true);
            return;
        }
        var look = _tonguePhase >= 0 ? _tip : _cursor;
        var dir = look - (c + Origin);
        float pr = er * 0.6f;
        var pc = c + new Vector2(0, er * 0.08f) + dir.Normalized() * Mathf.Min(1f, dir.Length() / (R * 4f)) * er * 0.14f;
        DrawCircle(pc, pr, Ink, true, -1f, true);
        DrawCircle(pc + new Vector2(pr * 0.32f, -pr * 0.32f), pr * 0.3f, Colors.White, true, -1f, true);
    }

    void DrawCheeks(Vector2 o)
    {
        for (int s = -1; s <= 1; s += 2)
        {
            DrawSetTransform(o + new Vector2(s * R * 0.74f, R * 0.1f), 0f, new Vector2(1f, 0.82f));
            DrawCircle(Vector2.Zero, R * 0.19f, Freckle, true, -1f, true);
            DrawSetTransform(Vector2.Zero, 0f, Vector2.One);
        }
    }

    void DrawMouth(Vector2 o)
    {
        var m = Mouth() - Origin;
        if (_tonguePhase >= 0)
        {
            DrawCircle(m, R * 0.14f, MouthColor, true, -1f, true);
            return;
        }
        float r = R * 0.22f;
        var c = m + new Vector2(0, -r * 0.75f);
        DrawArc(c, r, (_happy > 0f ? 0.12f : 0.22f) * Mathf.Pi, (_happy > 0f ? 0.88f : 0.78f) * Mathf.Pi, 18, Ink, 4.5f, true);
    }

    void DrawZ(Vector2 o)
    {
        var font = ThemeDB.FallbackFont;
        for (int i = 0; i < 3; i++)
        {
            float t = Mathf.PosMod(_time * 0.6f + i / 3f, 1f);
            var p = o + new Vector2(R * (0.7f + t * 0.8f), -R * (1.3f + t * 1.6f));
            DrawString(font, p, "z", HorizontalAlignment.Left, -1, (int)(R * (0.35f + t * 0.3f)), new Color(Ink, 1f - t));
        }
    }

    void DrawHearts(Vector2 o)
    {
        float t = 1f - _happy / 1.6f;
        for (int i = -1; i <= 1; i++)
        {
            var c = o + new Vector2(i * R * 0.7f, -R * (1.6f + t * 1.2f + Mathf.Abs(i) * 0.2f));
            float s = R * 0.16f;
            var col = new Color(Heart, 1f - t);
            DrawCircle(c + new Vector2(-s * 0.5f, 0), s * 0.55f, col, true, -1f, true);
            DrawCircle(c + new Vector2(s * 0.5f, 0), s * 0.55f, col, true, -1f, true);
            DrawColoredPolygon(new[] { c + new Vector2(-s * 1.02f, s * 0.15f), c + new Vector2(s * 1.02f, s * 0.15f), c + new Vector2(0, s * 1.2f) }, col);
        }
    }
}
