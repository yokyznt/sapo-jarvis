using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Net.NetworkInformation;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;
using Godot;

namespace Sapo;

static class WinNative
{
    public delegate void WinEventProc(IntPtr hook, uint ev, IntPtr hwnd, int idObject, int idChild, uint thread, uint time);

    [StructLayout(LayoutKind.Sequential)]
    public struct SYSTEM_POWER_STATUS { public byte ACLineStatus, BatteryFlag, BatteryLifePercent, SystemStatusFlag; public int BatteryLifeTime, BatteryFullLifeTime; }

    [DllImport("user32.dll")] public static extern IntPtr SetWinEventHook(uint min, uint max, IntPtr mod, WinEventProc proc, uint pid, uint tid, uint flags);
    [DllImport("user32.dll")] public static extern bool UnhookWinEvent(IntPtr hook);
    [DllImport("user32.dll")] public static extern uint GetClipboardSequenceNumber();
    [DllImport("user32.dll")] public static extern bool IsClipboardFormatAvailable(uint format);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern IntPtr SetFocus(IntPtr h);
    [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("user32.dll", CharSet = CharSet.Unicode, EntryPoint = "GetWindowTextW")] public static extern int GetWindowText(IntPtr h, StringBuilder sb, int max);
    [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
    [DllImport("kernel32.dll")] public static extern bool GetSystemPowerStatus(out SYSTEM_POWER_STATUS s);
    [DllImport("wininet.dll")] public static extern bool InternetGetConnectedState(out int flags, int reserved);

    public static string Title(IntPtr h)
    {
        var sb = new StringBuilder(256);
        GetWindowText(h, sb, sb.Capacity);
        return sb.ToString();
    }
}

[System.Runtime.Versioning.SupportedOSPlatform("windows")]
static class AudioState
{
    [ComImport, Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDeviceEnumerator
    {
        [PreserveSig] int EnumAudioEndpoints(int dataFlow, int mask, out IntPtr devices);
        [PreserveSig] int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice device);
    }

    [ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDevice
    {
        [PreserveSig] int Activate(ref Guid iid, int ctx, IntPtr p, [MarshalAs(UnmanagedType.IUnknown)] out object iface);
    }

    [ComImport, Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IAudioEndpointVolume
    {
        [PreserveSig] int RegisterControlChangeNotify(IntPtr n);
        [PreserveSig] int UnregisterControlChangeNotify(IntPtr n);
        [PreserveSig] int GetChannelCount(out uint n);
        [PreserveSig] int SetMasterVolumeLevel(float db, ref Guid ctx);
        [PreserveSig] int SetMasterVolumeLevelScalar(float v, ref Guid ctx);
        [PreserveSig] int GetMasterVolumeLevel(out float db);
        [PreserveSig] int GetMasterVolumeLevelScalar(out float v);
        [PreserveSig] int SetChannelVolumeLevel(uint ch, float db, ref Guid ctx);
        [PreserveSig] int SetChannelVolumeLevelScalar(uint ch, float v, ref Guid ctx);
        [PreserveSig] int GetChannelVolumeLevel(uint ch, out float db);
        [PreserveSig] int GetChannelVolumeLevelScalar(uint ch, out float v);
        [PreserveSig] int SetMute([MarshalAs(UnmanagedType.Bool)] bool mute, ref Guid ctx);
        [PreserveSig] int GetMute([MarshalAs(UnmanagedType.Bool)] out bool mute);
    }

    [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
    class MMDeviceEnumerator { }

    public static int Muted()
    {
        object e = null, d = null, v = null;
        try
        {
            e = new MMDeviceEnumerator();
            if (((IMMDeviceEnumerator)e).GetDefaultAudioEndpoint(0, 1, out var dev) != 0 || dev == null) return -1;
            d = dev;
            var iid = typeof(IAudioEndpointVolume).GUID;
            if (dev.Activate(ref iid, 23, IntPtr.Zero, out v) != 0 || v is not IAudioEndpointVolume vol) return -1;
            if (vol.GetMute(out bool mute) != 0 || vol.GetMasterVolumeLevelScalar(out float level) != 0) return -1;
            return mute || level < 0.01f ? 1 : 0;
        }
        catch (COMException) { return -1; }
        catch (InvalidCastException) { return -1; }
        finally
        {
            if (v != null) Marshal.ReleaseComObject(v);
            if (d != null) Marshal.ReleaseComObject(d);
            if (e != null) Marshal.ReleaseComObject(e);
        }
    }
}

public partial class Frog
{
    const uint EvMinimizeStart = 0x16, EvShow = 0x8002, EvLocation = 0x800B, EvUncloaked = 0x8018;
    readonly ConcurrentQueue<(uint ev, IntPtr hwnd)> _winQ = new();
    readonly List<IntPtr> _hooks = new();
    readonly Dictionary<string, float> _winCd = new();
    WinNative.WinEventProc _winProc;
    IntPtr _locHook, _locHwnd;
    float _scare, _flash, _peekT, _eatT = -1f, _winTimer, _probeTimer, _netTimer, _moveAccum;
    Vector2 _peekGaze;
    string _eatPath;
    uint _clipSeq;
    int _lastHour = -1, _netState = -1, _muteState = -1, _fakeBattery = -1;
    volatile int _netProbe = -1, _muteProbe = -1;
    volatile bool _probing;
    bool _batteryLowSent;
    float _fakeOffA = -1f, _fakeOffB = -1f, _testHourAt = -1f, _testDropAt = -1f;
    string _testDrop;
    LineEdit _chat;
    bool _chatOpen;
    float _chatT, _lastClickT = -10f;
    Vector2 _lastClickPos;
    IntPtr _chatPrevFg;

    bool Reactive => !_quiet && !_calm && !_hidden && !_desk.GameRunning && _state != State.Sleep;

    void SetupWin()
    {
        _winProc = OnWinEvent;
        foreach (var ev in new[] { EvMinimizeStart, EvShow, EvUncloaked })
        {
            var h = WinNative.SetWinEventHook(ev, ev, IntPtr.Zero, _winProc, 0, 0, 0x2);
            if (h != IntPtr.Zero) _hooks.Add(h);
        }
        _clipSeq = WinNative.GetClipboardSequenceNumber();
        _lastHour = DateTime.Now.Hour;
        GetWindow().FilesDropped += OnFilesDropped;
        SetupChat();
        var inv = System.Globalization.CultureInfo.InvariantCulture;
        foreach (var a in OS.GetCmdlineUserArgs())
        {
            if (a.StartsWith("--fake-battery=")) int.TryParse(a[15..], out _fakeBattery);
            if (a.StartsWith("--test-hour=")) float.TryParse(a[12..], System.Globalization.NumberStyles.Float, inv, out _testHourAt);
            if (a.StartsWith("--fake-offline="))
            {
                var ab = a[15..].Split('-');
                if (ab.Length == 2 && float.TryParse(ab[0], System.Globalization.NumberStyles.Float, inv, out var fa) && float.TryParse(ab[1], System.Globalization.NumberStyles.Float, inv, out var fb)) { _fakeOffA = fa; _fakeOffB = fb; }
            }
            if (a.StartsWith("--test-drop="))
            {
                var spec = a[12..];
                int at = spec.LastIndexOf('@');
                _testDropAt = 4f;
                if (at > 2 && float.TryParse(spec[(at + 1)..], System.Globalization.NumberStyles.Float, inv, out var td)) { _testDropAt = td; spec = spec[..at]; }
                _testDrop = spec;
            }
        }
        GD.Print($"win hooks {_hooks.Count}");
    }

    public override void _ExitTree()
    {
        foreach (var h in _hooks) WinNative.UnhookWinEvent(h);
        _hooks.Clear();
        if (_locHook != IntPtr.Zero) WinNative.UnhookWinEvent(_locHook);
        _locHook = IntPtr.Zero;
    }

    void OnWinEvent(IntPtr hook, uint ev, IntPtr hwnd, int idObject, int idChild, uint thread, uint time)
    {
        if (idObject != 0 || idChild != 0 || hwnd == IntPtr.Zero) return;
        _winQ.Enqueue((ev, hwnd));
    }

    void SyncLocationHook()
    {
        var h = Grounded && _platform is { } p ? p.Hwnd : IntPtr.Zero;
        if (h == _locHwnd) return;
        if (_locHook != IntPtr.Zero) WinNative.UnhookWinEvent(_locHook);
        _locHook = IntPtr.Zero;
        _locHwnd = h;
        if (h == IntPtr.Zero) return;
        uint tid = Win32.GetWindowThreadProcessId(h, out var pid);
        _locHook = WinNative.SetWinEventHook(EvLocation, EvLocation, IntPtr.Zero, _winProc, pid, tid, 0x2);
    }

    void UpdateWin(float dt)
    {
        SyncLocationHook();
        RideBar();
        while (_winQ.TryDequeue(out var e)) HandleWinEvent(e.ev, e.hwnd);
        _scare = Mathf.Max(0f, _scare - dt);
        _flash = Mathf.Max(0f, _flash - dt);
        _moveAccum = Mathf.Max(0f, _moveAccum - dt * R * 0.5f);
        if (_eatT >= 0f)
        {
            float prev = _eatT;
            _eatT += dt;
            if (prev < 0.35f && _eatT >= 0.35f) { _croakCd = 0f; Croak("plop"); }
            if (_eatT >= 1.15f)
            {
                _eatT = -1f;
                _happy = 0.9f;
            }
        }
        if (_testDropAt >= 0f && _time >= _testDropAt)
        {
            _testDropAt = -1f;
            GD.Print("test-drop " + _testDrop);
            Eat(_testDrop);
        }
        if (_testHourAt >= 0f && _time >= _testHourAt)
        {
            _testHourAt = -1f;
            OnHour();
        }
        _winTimer -= dt;
        if (_winTimer <= 0f)
        {
            _winTimer = 1f;
            PollSystem(dt);
        }
        UpdateChat(dt);
    }

    void RideBar()
    {
        if (_pinned || _state != State.Idle || _platform is not { } fp || fp.Hwnd != IntPtr.Zero) return;
        foreach (var b in _desk.Bars)
        {
            if (b.Y >= fp.Y - 4 || _pos.X < b.X0 + R * 0.5f || _pos.X > b.X1 - R * 0.5f) continue;
            _platform = null;
            _state = State.Air;
            _vel = new Vector2(0f, -Mathf.Sqrt(2f * Gravity * (fp.Y - b.Y + R * 0.8f)));
            _jelly.Squash(R * 0.25f);
            return;
        }
    }

    void HandleWinEvent(uint ev, IntPtr hwnd)
    {
        switch (ev)
        {
            case EvLocation:
                if (Grounded && _platform is { } p && p.Hwnd == hwnd && Win32.IsZoomed(hwnd)) PlatformMaximized();
                break;
            case EvMinimizeStart:
                if (!BigWindow(hwnd) || !Reactive || !Cool("minimized", 60f)) break;
                Scare();
                SendWin("minimized");
                break;
            case EvShow:
            case EvUncloaked:
                if (IsToast(hwnd)) Notice(hwnd);
                break;
        }
    }

    bool BigWindow(IntPtr hwnd)
    {
        foreach (var w in _desk.Windows)
        {
            if (w.Hwnd != hwnd) continue;
            var a = _desk.AreaAt(w.Rect.GetCenter()).Monitor;
            return (float)w.Rect.Size.X * w.Rect.Size.Y >= 0.3f * a.Size.X * a.Size.Y;
        }
        return false;
    }

    static bool IsToast(IntPtr hwnd)
    {
        if (Desktop.ClassOf(hwnd) != "Windows.UI.Core.CoreWindow") return false;
        var t = WinNative.Title(hwnd).ToLowerInvariant();
        if (t.Contains("nueva notificación") || t.Contains("new notification")) return true;
        return t.Length == 0 && Desktop.ProcessName(hwnd).Equals("ShellExperienceHost.exe", StringComparison.OrdinalIgnoreCase);
    }

    bool Cool(string key, float cd)
    {
        if (_winCd.TryGetValue(key, out var t) && _time - t < cd) return false;
        _winCd[key] = _time;
        return true;
    }

    void SendWin(string what)
    {
        GD.Print("win " + what);
        Send(new Dictionary<string, object> { ["type"] = "event", ["name"] = "win", ["what"] = what });
    }

    void Scare()
    {
        _scare = 1.3f;
        _blinkHold = 0f;
        _stretch.Vel += 0.9f;
        _croakCd = 0f;
        Croak("sorpresa");
    }

    void PlatformMaximized()
    {
        Fall();
        _vel = new Vector2(_rng.RandfRange(-140f, 140f), -380f);
        _jelly.Poke(new Vector2(0, R), R * 0.4f);
        if (!Reactive) return;
        _scare = 0.8f;
        _croakCd = 0f;
        Croak("sorpresa");
        if (Cool("maximized", 30f)) SendWin("maximized");
    }

    bool PlatformMoved(Vector2I d)
    {
        if (_platform is { } pp && _desk.IsBar(pp.Hwnd)) return false;
        float dist = ((Vector2)d).Length();
        _moveAccum += dist;
        bool tell = _moveAccum > R * 3f && Reactive && Cool("moved", 60f);
        if (dist > R * 2.2f)
        {
            Fall();
            _vel = new Vector2(Mathf.Clamp(d.X * 6f, -600f, 600f), -160f);
            if (Reactive) { _scare = 0.5f; _croakCd = 0f; Croak("sorpresa"); }
            if (tell) SendWin("moved");
            return true;
        }
        _tilt.Vel += Mathf.Clamp(-d.X * 0.12f, -3f, 3f);
        if (d.X != 0) _jelly.Poke(new Vector2(Mathf.Sign(d.X) * R, -R * 0.2f), Mathf.Min(Mathf.Abs(d.X) * 0.12f, R * 0.1f));
        _stretch.Vel += Mathf.Clamp(d.Y * 0.012f, -0.6f, 0.6f);
        if (tell) SendWin("moved");
        return false;
    }

    void Notice(IntPtr hwnd)
    {
        if (!Reactive || !Cool("notice", 8f)) return;
        var target = Desktop.BoundsOf(hwnd) is { } r && r.Size.X > 0 ? (Vector2)r.GetCenter() : PrimaryCorner();
        _peekGaze = Toward(target);
        if (_peekGaze.LengthSquared() < 0.25f) _peekGaze = new Vector2(0.8f, 0.6f);
        _peekT = 2f;
        if (Cool("notification", 60f)) SendWin("notification");
    }

    Vector2 PrimaryCorner()
    {
        foreach (var a in _desk.Areas) if (a.Primary) return a.Monitor.End;
        return _desk.AreaAt(_pos).Monitor.End;
    }

    void OnHour()
    {
        if (!Reactive) return;
        var corner = _desk.AreaAt(_pos).Monitor.End;
        _peekGaze = Toward(corner);
        _peekT = 1.5f;
        _stretch.Vel -= 0.6f;
        _croakCd = 0f;
        Croak("doble");
        SendWin("hour");
    }

    void PollSystem(float dt)
    {
        var now = DateTime.Now;
        if (now.Hour != _lastHour && now.Minute == 0)
        {
            _lastHour = now.Hour;
            OnHour();
        }
        uint seq = WinNative.GetClipboardSequenceNumber();
        if (seq != _clipSeq)
        {
            _clipSeq = seq;
            if (WinNative.IsClipboardFormatAvailable(2) || WinNative.IsClipboardFormatAvailable(8) || WinNative.IsClipboardFormatAvailable(17)) Screenshot();
            else Clipped();
        }
        PollBattery();
        _probeTimer -= 1f;
        _netTimer -= 1f;
        if (_probeTimer <= 0f && !_probing)
        {
            _probeTimer = 2f;
            bool net = _netTimer <= 0f;
            if (net) _netTimer = 10f;
            bool forceOff = _fakeOffA >= 0f && _time >= _fakeOffA && _time < _fakeOffB;
            _probing = true;
            Task.Run(() =>
            {
                try
                {
                    if (net) _netProbe = !forceOff && NetworkInterface.GetIsNetworkAvailable() && WinNative.InternetGetConnectedState(out _, 0) ? 1 : 0;
                    _muteProbe = OperatingSystem.IsWindows() ? AudioState.Muted() : -1;
                }
                catch (Exception) { }
                finally { _probing = false; }
            });
        }
        int n = _netProbe;
        if (n >= 0 && n != _netState)
        {
            bool first = _netState < 0;
            _netState = n;
            if (!first && Reactive)
            {
                if (n == 0 && Cool("offline", 30f)) { LookAround(); SendWin("offline"); }
                if (n == 1 && Cool("online", 30f)) { _happy = 0.7f; SendWin("online"); }
            }
        }
        int m = _muteProbe;
        if (m >= 0 && m != _muteState)
        {
            bool first = _muteState < 0;
            _muteState = m;
            if (!first && m == 1 && Reactive && Cool("muted", 120f))
            {
                _peekGaze = new Vector2(0f, 0.7f);
                _peekT = 1.2f;
                _blinkHold = 0.25f;
                SendWin("muted");
            }
        }
    }

    void PollBattery()
    {
        int pct;
        bool ac;
        if (_fakeBattery >= 0) { pct = _fakeBattery; ac = false; }
        else
        {
            if (!WinNative.GetSystemPowerStatus(out var s) || s.BatteryLifePercent == 255 || (s.BatteryFlag & 128) != 0) return;
            pct = s.BatteryLifePercent;
            ac = s.ACLineStatus == 1;
        }
        if (!_batteryLowSent && !ac && pct < 15 && _time > 6f && Reactive)
        {
            _batteryLowSent = true;
            _blinkHold = 0.45f;
            _stretch.Vel += 0.3f;
            SendWin("battery_low");
        }
        else if (_batteryLowSent && (ac || pct >= 20)) _batteryLowSent = false;
    }

    void Screenshot()
    {
        if (!Reactive || !Cool("shot", 10f)) return;
        _flash = 0.55f;
        if (Cool("screenshot", 60f)) SendWin("screenshot");
    }

    void Clipped()
    {
        if (!Reactive || !Cool("clipboard", 300f)) return;
        _peekGaze = Toward(_cursor);
        _peekT = 0.8f;
        SendWin("clipboard");
    }

    void OnFilesDropped(string[] files)
    {
        if (files.Length == 0) return;
        Win32.GetCursorPos(out var p);
        var c = new Vector2(p.X, p.Y);
        GD.Print($"files dropped at {c}: {files[0]}");
        if (!OnFrog(c) && c.DistanceTo(_pos) > R * 2f) return;
        Eat(files[0]);
    }

    void Eat(string path)
    {
        if (string.IsNullOrEmpty(path)) return;
        _eatT = 0f;
        _eatPath = path;
        _napTimer = 0f;
        _peekT = 0f;
        _boredom = Mathf.Max(0f, _boredom - 0.3f);
        GD.Print("file_drop " + path);
        Send(new Dictionary<string, object> { ["type"] = "event", ["name"] = "file_drop", ["path"] = path });
    }

    bool ReactGaze(float dt)
    {
        if (_eatT >= 0f) { _gazeTarget = Vector2.Zero; return true; }
        if (_peekT <= 0f) return false;
        _peekT -= dt;
        _gazeTarget = _peekGaze;
        return true;
    }

    void ReactMouth(ref float mo, ref float mr)
    {
        if (_eatT >= 0f)
        {
            if (_eatT < 0.35f) { mo = 1f; mr = 1f; }
            else { mo = 0.12f + 0.4f * Mathf.Abs(Mathf.Sin((_eatT - 0.35f) * 13f)); mr = 0f; }
            return;
        }
        if (_scare > 0f) { mo = Mathf.Max(mo, 0.45f); mr = 1f; }
    }

    float EyeScale => 1f + 0.4f * Mathf.Clamp(_scare / 0.5f, 0f, 1f);

    Vector2 PaperPos()
    {
        float k = Mathf.Clamp(_eatT / 0.35f, 0f, 1f);
        var from = _pos + new Vector2(R * 1.4f, -R * 2.1f);
        return from.Lerp(Mouth(), k * k);
    }

    void DrawReactions()
    {
        if (_hidden) return;
        if (_eatT >= 0f && _eatT < 0.35f)
        {
            float k = _eatT / 0.35f;
            var c = PaperPos() - Origin;
            float s = R * 0.5f * (1f - 0.75f * k);
            DrawSetTransformMatrix(new Transform2D(0.25f + k * 2f, c));
            DrawRect(new Rect2(-s * 0.4f, -s * 0.5f, s * 0.8f, s), Colors.White, true);
            DrawRect(new Rect2(-s * 0.4f, -s * 0.5f, s * 0.8f, s), Ink, false, 2f);
            for (int i = 0; i < 3; i++) DrawLine(new Vector2(-s * 0.25f, -s * 0.25f + i * s * 0.22f), new Vector2(s * 0.25f, -s * 0.25f + i * s * 0.22f), new Color(Ink, 0.6f), 1.5f);
            DrawSetTransformMatrix(Transform2D.Identity);
        }
        if (_flash > 0f)
        {
            float k = _flash / 0.55f;
            var c = _pos - Origin + new Vector2(R * 1.1f, -R * 1.3f - _hop.V);
            var col = new Color(1f, 0.97f, 0.7f, k);
            float s = R * (0.25f + 0.25f * (1f - k));
            for (int i = 0; i < 4; i++)
            {
                var d = Vector2.Right.Rotated(Mathf.Pi * 0.5f * i + 0.4f);
                DrawLine(c + d * s * 0.3f, c + d * s, col, 3f, true);
            }
            DrawCircle(c, s * 0.18f, col, true, -1f, true);
        }
    }

    void AddReactionRegion(List<Vector2> pts)
    {
        if (_eatT >= 0f && _eatT < 0.35f) AddCircle(pts, PaperPos() - Origin, R * 0.45f);
        if (_flash > 0f) AddCircle(pts, _pos - Origin + new Vector2(R * 1.1f, -R * 1.3f - _hop.V), R * 0.55f);
        if (_chatOpen)
        {
            var r = new Rect2(_chat.Position, _chat.Size).Grow(6f);
            pts.Add(r.Position);
            pts.Add(new Vector2(r.End.X, r.Position.Y));
            pts.Add(new Vector2(r.Position.X, r.End.Y));
            pts.Add(r.End);
        }
    }

    bool DoubleClick(Vector2 c) => _time - _lastClickT < 0.4f && c.DistanceTo(_lastClickPos) < 24f;

    bool RegisterClick(Vector2 c)
    {
        if (DoubleClick(c))
        {
            _lastClickT = -10f;
            OpenChat();
            return true;
        }
        _lastClickT = _time;
        _lastClickPos = c;
        return false;
    }

    void SetupChat()
    {
        _chat = new LineEdit { Visible = false, PlaceholderText = "Escríbele al sapo…", MaxLength = 400, ContextMenuEnabled = false, CaretBlink = true };
        _chat.TextSubmitted += SubmitChat;
        _chat.GuiInput += e =>
        {
            if (e is InputEventKey k && k.Pressed && k.Keycode == Key.Escape)
            {
                _chat.AcceptEvent();
                CloseChat(true);
            }
        };
        AddChild(_chat);
    }

    void StyleChat()
    {
        var sb = new StyleBoxFlat { BgColor = Colors.White, BorderColor = Ink, AntiAliasing = true };
        sb.SetBorderWidthAll(3);
        sb.SetCornerRadiusAll(14);
        sb.ContentMarginLeft = sb.ContentMarginRight = 12f;
        sb.ContentMarginTop = sb.ContentMarginBottom = 6f;
        _chat.AddThemeStyleboxOverride("normal", sb);
        _chat.AddThemeStyleboxOverride("focus", new StyleBoxEmpty());
        _chat.AddThemeColorOverride("font_color", Ink);
        _chat.AddThemeColorOverride("font_placeholder_color", new Color(Ink, 0.45f));
        _chat.AddThemeColorOverride("caret_color", Ink);
        _chat.AddThemeColorOverride("selection_color", new Color(Skin, 0.5f));
        _chat.AddThemeFontSizeOverride("font_size", BubbleFontSize);
    }

    void OpenChat()
    {
        if (_chatOpen || _hidden) return;
        CloseMenu();
        _chatOpen = true;
        _chatT = 0f;
        _chat.Text = "";
        StyleChat();
        LayoutChat();
        _chat.Visible = true;
        _chatPrevFg = Win32.GetForegroundWindow();
        DisplayServer.WindowSetFlag(DisplayServer.WindowFlags.NoFocus, false);
        SetActivatable(true);
        FocusSelf();
        _chat.GrabFocus();
        GD.Print($"chat open fg={Win32.GetForegroundWindow() == _hwnd}");
    }

    void CloseChat(bool restore)
    {
        if (!_chatOpen) return;
        _chatOpen = false;
        _chat.ReleaseFocus();
        _chat.Visible = false;
        DisplayServer.WindowSetFlag(DisplayServer.WindowFlags.NoFocus, true);
        SetActivatable(false);
        if (restore && _chatPrevFg != IntPtr.Zero && _chatPrevFg != _hwnd && Win32.IsWindow(_chatPrevFg)) WinNative.SetForegroundWindow(_chatPrevFg);
        _chatPrevFg = IntPtr.Zero;
        GD.Print("chat closed");
    }

    void SubmitChat(string text)
    {
        text = text.Trim();
        if (text.Length > 0)
        {
            GD.Print("chat " + text);
            Send(new Dictionary<string, object> { ["type"] = "chat", ["text"] = text, ["source"] = "bubble" });
            if (_wsOpen) _thinking = true;
            _happy = 0.6f;
        }
        CloseChat(true);
    }

    void SetActivatable(bool on)
    {
        long ex = (long)Win32.GetWindowLongPtr(_hwnd, Win32.GWL_EXSTYLE);
        ex = (ex | Win32.WS_EX_TOOLWINDOW) & ~Win32.WS_EX_APPWINDOW;
        ex = on ? ex & ~Win32.WS_EX_NOACTIVATE : ex | Win32.WS_EX_NOACTIVATE;
        Win32.SetWindowLongPtr(_hwnd, Win32.GWL_EXSTYLE, (IntPtr)ex);
        Win32.SetWindowPos(_hwnd, Win32.HWND_TOPMOST, 0, 0, 0, 0, Win32.SWP_NOSIZE | 0x2 | Win32.SWP_NOACTIVATE | Win32.SWP_FRAMECHANGED);
    }

    void FocusSelf()
    {
        if (WinNative.SetForegroundWindow(_hwnd) && Win32.GetForegroundWindow() == _hwnd) return;
        var fg = Win32.GetForegroundWindow();
        uint other = Win32.GetWindowThreadProcessId(fg, out _), me = WinNative.GetCurrentThreadId();
        bool attached = other != me && WinNative.AttachThreadInput(me, other, true);
        WinNative.SetForegroundWindow(_hwnd);
        WinNative.SetFocus(_hwnd);
        if (attached) WinNative.AttachThreadInput(me, other, false);
    }

    void LayoutChat()
    {
        float w = Mathf.Max(220f, R * 6f), h = BubbleFontSize + 22f;
        var o = _pos - Origin;
        var pos = new Vector2(o.X - w * 0.5f, o.Y - R * 1.45f - _hop.V - h - 14f);
        var lo = (Vector2)Area.Position - Origin;
        var hi = (Vector2)Area.End - Origin;
        pos.X = Mathf.Clamp(pos.X, lo.X + 8f, hi.X - w - 8f);
        pos.Y = Mathf.Max(lo.Y + 8f, pos.Y);
        _chat.Position = pos.Round();
        _chat.Size = new Vector2(w, h);
    }

    void UpdateChat(float dt)
    {
        if (!_chatOpen) return;
        _chatT += dt;
        LayoutChat();
        if (_hidden || (_chat.Text.Length == 0 && _chatT > 45f)) CloseChat(false);
    }

    public override void _Notification(int what)
    {
        if (what is (int)NotificationApplicationFocusOut or (int)NotificationWMWindowFocusOut && _chatOpen && _chatT > 0.4f) CloseChat(false);
    }
}
