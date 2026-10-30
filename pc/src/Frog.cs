using System;
using System.Collections.Generic;
using Godot;

namespace Sapo;

public partial class Frog : Node2D
{
    enum State { Idle, Crouch, Air, Held, Tongue, Sleep, Dance }
    enum Grab { Cursor, Window }

    sealed class Spring
    {
        public float V, Vel;
        public void To(float target, float k, float d, float dt)
        {
            Vel += (k * (target - V) - d * Vel) * dt;
            V += Vel * dt;
        }
    }

    sealed class Spring2
    {
        public Vector2 V, Vel;
        public void To(Vector2 target, float k, float d, float dt)
        {
            Vel += (k * (target - V) - d * Vel) * dt;
            V += Vel * dt;
        }
    }

    sealed class Particle
    {
        public Vector2 P, V;
        public float T, Life, Size;
    }

    const float Gravity = 2000f;

    Desktop _desk;
    IntPtr _hwnd;
    Jelly _jelly;
    readonly RandomNumberGenerator _rng = new();
    float R;
    Vector2 _pos, _vel, _prevVel, _jumpVel;
    State _state = State.Air;
    Platform? _platform;
    Vector2I _platformWinPos;
    float _boredom, _actionTimer = 2f, _crouchTimer, _refreshTimer, _time, _happy, _napTimer, _danceTimer, _danceT, _noteTimer;
    bool _calm, _hidden, _prevS, _prevLmb, _pressedOnFrog, _wasGame, _ignored1, _ignored2;
    Vector2 _cursor, _cursorVel, _grabOffset, _pressPos;
    float _pressTime, _lastCursorMove = -10f;
    int _tonguePhase = -1;
    float _tongueT;
    Grab _grab;
    Vector2 _tip, _tongueFrom, _tongueTo, _winGrabOffset;
    IntPtr _tongueHwnd;
    Vector2I _winStart;
    IntPtr _stompHwnd;
    Vector2I _stompStart;
    float _stompT = -1f;
    readonly Spring _stretch = new(), _tilt = new(), _hop = new(), _mouthOpen = new(), _mouthRound = new();
    readonly Spring _eyeOpen = new() { V = 1f };
    readonly Spring2 _gaze = new();
    Vector2 _gazeTarget;
    float _gazeTimer, _blinkTimer = 3f, _blinkHold, _lookAroundTimer;
    readonly List<Particle> _puffs = new(), _notes = new();
    Vector2[] _region = Array.Empty<Vector2>();
    string _argSkin;
    float _cfgTimer = 1f;
    float _argMenu;

    bool CanTouch => !_calm && !_hidden && !_desk.GameRunning && _napTimer <= 0f;
    bool Grounded => _state is State.Idle or State.Crouch or State.Tongue or State.Sleep or State.Dance;
    Vector2 Origin => _desk.Bounds.Position;
    Rect2I Area => _desk.AreaAt(_pos).Work;
    int MinTopGap => (int)(R * 2.6f);

    public override void _Ready()
    {
        if (DumpRequested(out var dumpDir))
        {
            Croaks.Dump(dumpDir);
            GD.Print("croacs en " + dumpDir);
            SetProcess(false);
            Visible = false;
            GetTree().Quit();
            return;
        }
        var mons = Desktop.Monitors();
        int idx = -1;
        Vector2I? at = null;
        foreach (var a in OS.GetCmdlineUserArgs())
        {
            if (a.StartsWith("--monitor=")) int.TryParse(a[10..], out idx);
            if (a.StartsWith("--boredom=") && float.TryParse(a[10..], System.Globalization.CultureInfo.InvariantCulture, out var bo)) _boredom = Mathf.Clamp(bo, 0f, 1f);
            if (a.StartsWith("--brain=")) BrainUrl = a[8..];
            if (a.StartsWith("--skin=")) _argSkin = a[7..];
            if (a == "--menu") _argMenu = 2.5f;
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
        _desk = new Desktop(_hwnd, mons);
        _baseR = 36f * Mathf.Max(0.75f, area.Monitor.Size.Y / 1080f);
        LoadPrefs();
        R = _baseR * SizeScale;
        _jelly = new Jelly(R);
        SetupWindow(_desk.Bounds);
        SetupBubble();
        SetupSound();
        _pos = new Vector2(area.Work.Position.X + area.Work.Size.X * 0.5f, area.Work.Position.Y + R * 2f);
        _desk.Refresh(MinTopGap);
        _rng.Randomize();
        RestorePin();
        if (_argSkin != null) _skin = _skins.Find(k => k.Id == _argSkin) ?? _skin;
    }


    void SetupWindow(Rect2I w)
    {
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
        _cfgTimer -= dt;
        if (_cfgTimer <= 0f)
        {
            _cfgTimer = 1f;
            if (Config.Reload()) ApplyConfig();
        }
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
        UpdateMenu(dt);
        if (_argMenu > 0f && (_argMenu -= dt) <= 0f && _state == State.Idle) OpenMenu();
        bool game = _desk.GameRunning;
        if (game != _wasGame)
        {
            _wasGame = game;
            SendEvent(game ? "game_on" : "game_off");
        }
        if (_napTimer > 0f)
        {
            _napTimer -= dt;
            if (_napTimer <= 0f) SendEvent("woke");
        }
        bool asleep = _calm || game || _napTimer > 0f;
        if (asleep && Grounded && _state != State.Sleep)
        {
            EndTongue();
            EndDance();
            _state = State.Sleep;
            if (!game) Croak("sueno");
        }
        if (!asleep && _state == State.Sleep) _state = State.Idle;
        if (!asleep && _state != State.Held) _boredom = Mathf.Min(1f, _boredom + dt / 300f);
        if (_boredom > 0.5f && !_ignored1) { _ignored1 = true; SendEvent("ignored"); }
        if (_boredom > 0.85f && !_ignored2) { _ignored2 = true; SendEvent("ignored"); }
        _happy = Mathf.Max(0f, _happy - dt);
        Step(dt);
        UpdateSound(dt);
        UpdateStomp(dt);
        var accel = (_vel - _prevVel) / dt;
        _prevVel = _vel;
        _jelly.Step(dt, accel, Grounded && _platform is { } p ? p.Y - 6f - _pos.Y : float.PositiveInfinity);
        Animate(dt);
        PollBrain(dt);
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
        var bounds = Desktop.Union(_desk.Areas, _desk.GameMonitor);
        bool hide = bounds.Size.X <= 0;
        if (!hide && bounds != _desk.Bounds)
        {
            _desk.Bounds = bounds;
            SetupWindow(bounds);
            _region = Array.Empty<Vector2>();
            if (!bounds.HasPoint((Vector2I)_pos.Round()))
            {
                var a = _desk.AreaAt(_pos).Work;
                EndTongue();
                EndDance();
                _platform = null;
                _state = State.Air;
                _vel = Vector2.Zero;
                _pos = new Vector2(a.Position.X + a.Size.X * 0.5f, a.Position.Y + R * 2f);
            }
            _desk.Refresh(MinTopGap);
        }
        if (hide == _hidden) return;
        _hidden = hide;
        Win32.ShowWindow(_hwnd, hide ? Win32.SW_HIDE : Win32.SW_SHOWNOACTIVATE);
        if (!hide) Win32.SetWindowPos(_hwnd, Win32.HWND_TOPMOST, 0, 0, 0, 0, Win32.SWP_NOSIZE | 0x2 | Win32.SWP_NOACTIVATE);
    }

    void PollMouse(float dt)
    {
        Win32.GetCursorPos(out var p);
        var c = new Vector2(p.X, p.Y);
        if (c.DistanceSquaredTo(_cursor) > 4f) _lastCursorMove = _time;
        _cursorVel = _cursorVel.Lerp((c - _cursor) / dt, 0.35f);
        _cursor = c;
        bool rmb = Win32.KeyDown(0x02);
        if (rmb && !_prevRmb && !_hidden && _state != State.Held && (OnFrog(c) || OnPad(c)))
        {
            if (_menuOpen) CloseMenu();
            else OpenMenu();
        }
        _prevRmb = rmb;
        bool lmb = Win32.KeyDown(0x01);
        if (lmb && !_prevLmb && MenuClick(c)) { _prevLmb = lmb; return; }
        if (lmb && !_prevLmb && ConfirmClick(c)) { _prevLmb = lmb; return; }
        if (lmb && !_prevLmb && !_hidden && (OnFrog(c) || OnPad(c)))
        {
            _pressedOnFrog = true;
            _pressPos = c;
            _pressTime = _time;
            _grabOffset = _pos - c;
            _napTimer = 0f;
            EndTongue();
            EndDance();
            _state = State.Held;
            _grabCroaked = false;
            _platform = null;
            _boredom = Mathf.Max(0f, _boredom - 0.3f);
        }
        if (!lmb && _prevLmb && _pressedOnFrog)
        {
            _pressedOnFrog = false;
            bool click = _time - _pressTime < 0.25f && c.DistanceTo(_pressPos) < 8f;
            if (_pinned)
            {
                _state = State.Idle;
                Pin(new Vector2(_pos.X, _pos.Y + _jelly.Bottom + 8f));
                if (click) Pet(c);
                else Croak("plop");
                _prevLmb = lmb;
                return;
            }
            _state = State.Air;
            _vel = click ? new Vector2(0, -350f) : _cursorVel.LimitLength(3200f);
            if (click) Pet(c);
            else if (_vel.Length() > 1200f)
            {
                SendEvent("thrown");
                Croak("grunon");
            }
        }
        _prevLmb = lmb;
    }

    void Pet(Vector2 at)
    {
        _boredom = 0f;
        _ignored1 = _ignored2 = false;
        _happy = 1.6f;
        _jelly.Poke(at - _pos, R * 0.5f);
        SendEvent("petted");
    }

    bool OnFrog(Vector2 c)
    {
        var d = c - (_pos + new Vector2(0, -R * 0.15f - _hop.V));
        float rx = R * 1.25f, ry = R * 1.15f;
        return d.X * d.X / (rx * rx) + d.Y * d.Y / (ry * ry) <= 1f;
    }

    void Step(float dt)
    {
        switch (_state)
        {
            case State.Idle:
                if (_menuOpen) break;
                _actionTimer -= dt;
                if (!_pinned)
                {
                    _jumpTimer -= dt;
                    if (_jumpTimer <= 0f)
                    {
                        ResetJumpTimer();
                        JumpNow();
                        break;
                    }
                }
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
            case State.Dance:
                _danceT += dt;
                _danceTimer -= dt;
                _noteTimer -= dt;
                if (_noteTimer <= 0f)
                {
                    _noteTimer = 0.45f;
                    _notes.Add(new Particle { P = _pos + new Vector2(_rng.RandfRange(-R, R), -R * 1.3f), V = new Vector2(_rng.RandfRange(-30f, 30f), -90f), Life = 1.6f, Size = R * (_rng.Randf() < 0.5f ? 0.15f : 0.17f) });
                }
                if (_danceTimer <= 0f) EndDance();
                break;
        }
    }

    void Fly(float dt)
    {
        var w = Area;
        float b = _jelly.Bottom;
        float prevBottom = _pos.Y + b;
        _vel.Y += Gravity * dt;
        var next = _pos + _vel * dt;
        if (next.X < w.Position.X + R && !Open(new Vector2(w.Position.X - R, next.Y))) { next.X = w.Position.X + R; _vel.X = Mathf.Abs(_vel.X) * 0.5f; _jelly.Poke(new Vector2(-R, 0), R * 0.3f); }
        if (next.X > w.End.X - R && !Open(new Vector2(w.End.X + R, next.Y))) { next.X = w.End.X - R; _vel.X = -Mathf.Abs(_vel.X) * 0.5f; _jelly.Poke(new Vector2(R, 0), R * 0.3f); }
        if (next.Y < w.Position.Y + R * 1.4f && !Open(new Vector2(next.X, w.Position.Y - R * 1.5f))) { next.Y = w.Position.Y + R * 1.4f; _vel.Y = Mathf.Abs(_vel.Y) * 0.3f; }
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
        if (_vel.Y > 0f && _pos.Y + b > w.End.Y && !(_dropThrough && Open(new Vector2(_pos.X, w.End.Y + R)))) hit = _desk.Floor(_desk.AreaAt(_pos));
        if (hit is { } h) Land(h);
    }

    void Land(Platform p)
    {
        float impact = Mathf.Max(0f, _vel.Y);
        _pos.Y = p.Y - _jelly.Bottom - 8f;
        _vel = Vector2.Zero;
        _state = State.Idle;
        _platform = p;
        _dropThrough = false;
        if (p.Hwnd != IntPtr.Zero && Desktop.BoundsOf(p.Hwnd) is { } r) _platformWinPos = r.Position;
        _actionTimer = _rng.RandfRange(2.5f, 5f);
        _stretch.Vel -= impact * 0.0011f;
        if (impact > 450f) SpawnPuffs(p.Y, impact);
        if (impact > 1100f)
        {
            _blinkHold = 0.12f;
            Croak("aterrizaje");
        }
        if (_energy == Energy.Travieso && p.Hwnd != IntPtr.Zero && CanTouch && _boredom > 0.6f && _rng.Randf() < 0.5f && !Win32.IsZoomed(p.Hwnd)) StartStomp(p.Hwnd);
    }

    void SpawnPuffs(float y, float impact)
    {
        float k = Mathf.Clamp(impact / 1500f, 0.4f, 1.4f);
        for (int s = -1; s <= 1; s += 2)
            for (int i = 0; i < 3; i++)
                _puffs.Add(new Particle
                {
                    P = new Vector2(_pos.X + s * R * _rng.RandfRange(0.4f, 0.8f), y - 6f),
                    V = new Vector2(s * _rng.RandfRange(110f, 260f) * k, -_rng.RandfRange(10f, 60f)),
                    Life = _rng.RandfRange(0.35f, 0.55f),
                    Size = R * _rng.RandfRange(0.1f, 0.18f) * k
                });
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
        EndDance();
        _platform = null;
        _state = State.Air;
        _vel = new Vector2(0, 50f);
    }

    void ChooseAction()
    {
        float b = _boredom;
        bool wild = _energy == Energy.Travieso && !_pinned;
        _actionTimer = (_energy == Energy.Zen ? 9f : 6f) * _rng.RandfRange(0.7f, 1.6f);
        var options = new (float w, Func<bool> act)[]
        {
            (2.2f, () => true),
            (1f, LookAround),
            (_energy switch { Energy.Zen => 0.05f, Energy.Normal => 0.15f, _ => 0.3f }, StartDance),
            (b < 0.3f ? (_energy == Energy.Zen ? 0.35f : 0.15f) : 0f, StartNap),
            (wild && CanTouch && b > 0.35f ? b * 1.4f : 0f, TryTongueCursor),
            (wild && CanTouch && b > 0.6f ? b * 1.1f : 0f, TryTongueWindow),
        };
        float total = 0f;
        foreach (var o in options) total += o.w;
        float roll = _rng.Randf() * total;
        foreach (var o in options)
        {
            roll -= o.w;
            if (roll > 0f || o.w <= 0f) continue;
            o.act();
            return;
        }
    }

    void JumpNow()
    {
        float b = _boredom;
        float hop = _energy switch { Energy.Zen => 0f, Energy.Normal => 0.1f, _ => 0.2f };
        if (_rng.Randf() < hop && HopMonitor()) return;
        if (_energy == Energy.Travieso && b > 0.3f && _rng.Randf() < 0.3f && ChaseCursor()) return;
        if (_rng.Randf() < 0.5f && PlanJump(b, true)) return;
        PlanJump(b, false);
    }

    bool LookAround()
    {
        _lookAroundTimer = _rng.RandfRange(1.2f, 2.4f);
        _gazeTimer = 0f;
        return true;
    }

    bool StartNap()
    {
        if (_state != State.Idle) return false;
        _napTimer = _rng.RandfRange(10f, 25f);
        return true;
    }

    bool StartDance()
    {
        if (_state != State.Idle) return false;
        _state = State.Dance;
        _danceTimer = _rng.RandfRange(3.5f, 6f);
        _danceT = 0f;
        _noteTimer = 0f;
        SendEvent("dancing");
        Croak("feliz");
        return true;
    }

    void EndDance()
    {
        if (_state == State.Dance) _state = State.Idle;
    }

    bool ChaseCursor()
    {
        Platform? best = null;
        foreach (var p in _desk.Platforms)
        {
            if (_cursor.X < p.X0 + R || _cursor.X > p.X1 - R || p.Y < _cursor.Y) continue;
            if (best is null || p.Y < best.Value.Y) best = p;
        }
        if (best is not { } t || t.Y < _pos.Y + _jelly.Bottom - R * 14f) return false;
        return JumpTo(t, _cursor.X, _boredom);
    }

    bool PlanJump(float b, bool sameOnly)
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
        if (sameOnly)
        {
            if (same is not { } s) return false;
            float sx = _pos.X + _rng.RandfRange(R * 1f, R * 2.5f) * (_rng.Randf() < 0.5f ? -1f : 1f);
            return JumpTo(s, sx, b * 0.3f);
        }
        if (cands.Count == 0) return false;
        var t = cands[_rng.RandiRange(0, cands.Count - 1)];
        float tx = _rng.RandfRange(t.X0 + R * 1.3f, t.X1 - R * 1.3f);
        float reach = Mathf.Lerp(R * 7f, R * 22f, b);
        return JumpTo(t, Mathf.Clamp(tx, _pos.X - reach, _pos.X + reach), b);
    }

    bool JumpTo(Platform t, float tx, float b)
    {
        if (t.X1 - t.X0 < R * 2.6f) return false;
        tx = Mathf.Clamp(tx, t.X0 + R * 1.3f, t.X1 - R * 1.3f);
        float ty = t.Y - _jelly.Bottom;
        float apex = Mathf.Min(_pos.Y, ty) - _rng.RandfRange(R * 0.8f, R * (1.6f + b * 2.5f));
        apex = Mathf.Max(apex, _desk.AreaAt(new Vector2(tx, ty)).Work.Position.Y + R * 1.5f);
        if (apex >= _pos.Y - 4f) apex = _pos.Y - R;
        float vy = -Mathf.Sqrt(2f * Gravity * (_pos.Y - apex));
        float time = -vy / Gravity + Mathf.Sqrt(2f * Mathf.Max(1f, ty - apex) / Gravity);
        _jumpVel = new Vector2(Mathf.Clamp((tx - _pos.X) / time, -2200f, 2200f), vy);
        _state = State.Crouch;
        _crouchTimer = 0.24f;
        _jelly.Squash(R * 0.35f);
        return true;
    }

    void DoAction(string name)
    {
        if (_state != State.Idle) return;
        if (_pinned && name is "jump" or "steal_cursor") return;
        if (name == "steal_cursor" && _energy != Energy.Travieso) return;
        switch (name)
        {
            case "dance": StartDance(); break;
            case "jump": PlanJump(_boredom, false); break;
            case "sleep": StartNap(); break;
            case "look_around": LookAround(); break;
            case "steal_cursor": if (CanTouch) TryTongueCursor(); break;
        }
    }

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
            if (!_desk.Bounds.HasPoint(gp) || _desk.PointCovered(gp, i)) continue;
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
                    SendEvent(_grab == Grab.Cursor ? "stole_cursor" : "moved_window");
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
                _tip = _tongueFrom.Lerp(mouth, EaseOut(_tongueT));
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

    static float EaseOut(float t) => 1f - (1f - t) * (1f - t);
    static float EaseInOut(float t) => t * t * (3f - 2f * t);
}
