using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using Godot;

namespace Sapo;

public readonly record struct Win(IntPtr Hwnd, Rect2I Rect, bool Maximized);
public readonly record struct Platform(IntPtr Hwnd, int Y, int X0, int X1);
public readonly record struct MonitorArea(Rect2I Monitor, Rect2I Work, bool Primary);

public sealed class Desktop
{
    static readonly HashSet<string> ShellClasses = new()
    {
        "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Windows.UI.Core.CoreWindow", "XamlExplorerHostIslandWindow"
    };

    static readonly HashSet<string> GameProcesses = new(StringComparer.OrdinalIgnoreCase)
    {
        "FortniteClient-Win64-Shipping.exe", "FortniteClient-Win64-Shipping_EAC_EOS.exe", "RobloxPlayerBeta.exe", "VALORANT-Win64-Shipping.exe", "cs2.exe", "Minecraft.Windows.exe"
    };

    public readonly IntPtr Self;
    public readonly Rect2I Monitor;
    public readonly Rect2I Work;
    public readonly List<Win> Windows = new();
    public readonly List<Platform> Platforms = new();
    public bool GameRunning { get; private set; }
    public bool GameOnOurMonitor { get; private set; }
    readonly uint _selfPid;

    public Desktop(IntPtr self, MonitorArea area)
    {
        Self = self;
        Monitor = area.Monitor;
        Work = area.Work;
        Win32.GetWindowThreadProcessId(self, out _selfPid);
    }

    public static List<MonitorArea> Monitors()
    {
        var list = new List<MonitorArea>();
        Win32.EnumDisplayMonitors(IntPtr.Zero, IntPtr.Zero, (IntPtr h, IntPtr _, ref Win32.RECT _, IntPtr _) =>
        {
            var info = new Win32.MONITORINFO { cbSize = Marshal.SizeOf<Win32.MONITORINFO>() };
            if (Win32.GetMonitorInfo(h, ref info))
                list.Add(new MonitorArea(ToRect(info.rcMonitor), ToRect(info.rcWork), (info.dwFlags & 1) != 0));
            return true;
        }, IntPtr.Zero);
        return list;
    }

    public void Refresh(int minTopGap)
    {
        Windows.Clear();
        Win32.EnumWindows((h, _) =>
        {
            var w = Describe(h);
            if (w.HasValue) Windows.Add(w.Value);
            return true;
        }, IntPtr.Zero);
        BuildPlatforms(minTopGap);
        DetectGame();
    }

    public static Rect2I ToRect(Win32.RECT r) => new(r.Left, r.Top, r.Right - r.Left, r.Bottom - r.Top);

    public static Rect2I? BoundsOf(IntPtr h)
    {
        if (!Win32.IsWindow(h) || !Win32.IsWindowVisible(h) || Win32.IsIconic(h)) return null;
        if (Win32.DwmGetWindowAttribute(h, 9, out Win32.RECT r, Marshal.SizeOf<Win32.RECT>()) == 0) return ToRect(r);
        return Win32.GetWindowRect(h, out var g) ? ToRect(g) : null;
    }

    public static Vector2I? OuterPosition(IntPtr h) => Win32.GetWindowRect(h, out var r) ? new Vector2I(r.Left, r.Top) : null;

    static string ClassOf(IntPtr h)
    {
        var sb = new StringBuilder(128);
        Win32.GetClassName(h, sb, sb.Capacity);
        return sb.ToString();
    }

    static string ProcessName(IntPtr h)
    {
        Win32.GetWindowThreadProcessId(h, out var pid);
        var p = Win32.OpenProcess(0x1000, false, pid);
        if (p == IntPtr.Zero) return "";
        try
        {
            var sb = new StringBuilder(512);
            int size = sb.Capacity;
            return Win32.QueryFullProcessImageName(p, 0, sb, ref size) ? System.IO.Path.GetFileName(sb.ToString()) : "";
        }
        finally { Win32.CloseHandle(p); }
    }

    Win? Describe(IntPtr h)
    {
        if (h == Self || !Win32.IsWindowVisible(h) || Win32.IsIconic(h)) return null;
        Win32.GetWindowThreadProcessId(h, out var pid);
        if (pid == _selfPid) return null;
        if (Win32.DwmGetWindowAttribute(h, 14, out int cloaked, 4) == 0 && cloaked != 0) return null;
        long ex = (long)Win32.GetWindowLongPtr(h, Win32.GWL_EXSTYLE);
        if ((ex & Win32.WS_EX_TOOLWINDOW) != 0 && (ex & Win32.WS_EX_APPWINDOW) == 0) return null;
        if (Win32.GetWindowTextLength(h) == 0) return null;
        if (ShellClasses.Contains(ClassOf(h))) return null;
        var r = BoundsOf(h);
        if (r is not { } rect || rect.Size.X < 120 || rect.Size.Y < 60) return null;
        return new Win(h, rect, Win32.IsZoomed(h));
    }

    void BuildPlatforms(int minTopGap)
    {
        Platforms.Clear();
        Platforms.Add(new Platform(IntPtr.Zero, Work.End.Y, Work.Position.X, Work.End.X));
        for (int i = 0; i < Windows.Count; i++)
        {
            var w = Windows[i];
            int y = w.Rect.Position.Y;
            if (y < Work.Position.Y + minTopGap || y >= Work.End.Y - 4) continue;
            var segs = new List<(int a, int b)> { (Math.Max(w.Rect.Position.X, Work.Position.X), Math.Min(w.Rect.End.X, Work.End.X)) };
            for (int j = 0; j < i && segs.Count > 0; j++)
            {
                var o = Windows[j].Rect;
                if (o.Position.Y > y - 2 || o.End.Y < y - 2) continue;
                segs = Subtract(segs, o.Position.X, o.End.X);
            }
            foreach (var (a, b) in segs)
                if (b - a >= 60) Platforms.Add(new Platform(w.Hwnd, y, a, b));
        }
    }

    static List<(int a, int b)> Subtract(List<(int a, int b)> segs, int x0, int x1)
    {
        var res = new List<(int a, int b)>();
        foreach (var (a, b) in segs)
        {
            if (x1 <= a || x0 >= b) { res.Add((a, b)); continue; }
            if (x0 > a) res.Add((a, x0));
            if (x1 < b) res.Add((x1, b));
        }
        return res;
    }

    public bool PointCovered(Vector2I p, int uptoIndex)
    {
        for (int j = 0; j < uptoIndex && j < Windows.Count; j++)
            if (Windows[j].Rect.HasPoint(p)) return true;
        return false;
    }

    void DetectGame()
    {
        GameRunning = false;
        GameOnOurMonitor = false;
        var fg = Win32.GetForegroundWindow();
        if (fg == IntPtr.Zero || fg == Self) return;
        if (ShellClasses.Contains(ClassOf(fg))) return;
        var mon = Win32.MonitorFromWindow(fg, 2);
        var info = new Win32.MONITORINFO { cbSize = Marshal.SizeOf<Win32.MONITORINFO>() };
        if (!Win32.GetMonitorInfo(mon, ref info)) return;
        bool known = GameProcesses.Contains(ProcessName(fg));
        bool fullscreen = false;
        if (Win32.GetWindowRect(fg, out var r))
            fullscreen = !Win32.IsZoomed(fg) && r.Left <= info.rcMonitor.Left && r.Top <= info.rcMonitor.Top && r.Right >= info.rcMonitor.Right && r.Bottom >= info.rcMonitor.Bottom;
        if (!known && !fullscreen) return;
        GameRunning = true;
        GameOnOurMonitor = ToRect(info.rcMonitor) == Monitor;
    }
}
