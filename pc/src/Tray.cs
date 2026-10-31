using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text.Json.Nodes;
using Godot;

namespace Sapo;

public partial class Frog
{
    StatusIndicator _tray;
    PopupMenu _trayMenu;
    readonly List<string> _trayIds = new();
    string _trayKey = "";
    float _trayTimer, _trayTestT = -1f;
    string _trayTest;
    bool _userHidden;
    Core _core;
    System.Threading.Mutex _single;

    static string ExeDir => Path.GetDirectoryName(OS.GetExecutablePath()) ?? ".";
    static bool Exported => !OS.HasFeature("editor");

    bool AlreadyRunning()
    {
        if (!Exported) return false;
        _single = new System.Threading.Mutex(true, "Local\\SapoJarvisPc", out var created);
        if (created) return false;
        GD.Print("ya hay un Sapo corriendo, salgo");
        return true;
    }

    void SetupCore()
    {
        foreach (var a in OS.GetCmdlineUserArgs())
            if (a.StartsWith("--tray=")) { _trayTest = a[7..]; _trayTestT = 4f; }
        if (Exported) Config.EnsureStartupCommand($"\"{OS.GetExecutablePath().Replace('/', '\\')}\"");
        _core = new Core(BrainUrl);
    }

    void SetupTray()
    {
        _trayMenu = new PopupMenu { PreferNativeMenu = true };
        AddChild(_trayMenu);
        _trayMenu.IdPressed += id => RunTray(id >= 0 && id < _trayIds.Count ? _trayIds[(int)id] : "");
        _tray = new StatusIndicator { Tooltip = "Sapo", Icon = GD.Load<Texture2D>("res://icon.png") };
        AddChild(_tray);
        _tray.Menu = _tray.GetPathTo(_trayMenu);
        RefreshTray();
    }

    IEnumerable<(string id, string label)> TrayItems()
    {
        yield return ("prefs", "Preferencias…");
        yield return ("energy", _energy == Energy.Zen ? "Energía normal" : "Calmar");
        yield return ("pin", _pinned ? "Soltar del nenúfar" : "Fijar en nenúfar");
        yield return ("clip", "Clipear");
        yield return ("hide", _userHidden ? "Mostrar" : "Ocultar");
        yield return ("quit", "Salir");
    }

    void RefreshTray()
    {
        if (_trayMenu == null) return;
        var items = new List<(string id, string label)>(TrayItems());
        var key = string.Join("|", items.ConvertAll(i => i.label));
        if (key == _trayKey) return;
        _trayKey = key;
        _trayMenu.Clear();
        _trayIds.Clear();
        foreach (var (id, label) in items)
        {
            if (id == "quit") _trayMenu.AddSeparator();
            _trayMenu.AddItem(label, _trayIds.Count);
            _trayIds.Add(id);
        }
        GD.Print("bandeja: " + key);
    }

    void TickTray(float dt)
    {
        _core?.Tick(dt);
        _trayTimer -= dt;
        if (_trayTimer <= 0f)
        {
            _trayTimer = 0.5f;
            RefreshTray();
        }
        if (_trayTestT > 0f && (_trayTestT -= dt) <= 0f)
            foreach (var id in _trayTest.Split(',')) RunTray(id);
    }

    void RunTray(string id)
    {
        GD.Print("bandeja: elegí " + id);
        switch (id)
        {
            case "prefs":
                var prefs = Path.Combine(ExeDir, "SapoPreferencias.exe");
                if (!File.Exists(prefs)) { GD.Print("bandeja: no encuentro " + prefs); break; }
                try { Process.Start(new ProcessStartInfo(prefs) { UseShellExecute = true, WorkingDirectory = ExeDir }); }
                catch (Exception e) { GD.Print("bandeja: no pude abrir Preferencias: " + e.Message); }
                break;
            case "energy":
                _energy = _energy == Energy.Zen ? Energy.Normal : Energy.Zen;
                Config.Set("energy", JsonValue.Create(_energy.ToString()));
                ResetJumpTimer();
                break;
            case "pin":
                if (_state == State.Held) break;
                if (_pinned) Unpin();
                else if (Grounded) Pin(new Vector2(_pos.X, _pos.Y + _jelly.Bottom + 8f));
                break;
            case "clip":
                if (!_wsOpen) { Say("No tengo cerebro conectado para clipear."); break; }
                Send(new Dictionary<string, object> { ["type"] = "chat", ["text"] = "clipea eso", ["source"] = "tray" });
                _thinking = true;
                break;
            case "hide":
                _userHidden = !_userHidden;
                if (_userHidden) { CloseMenu(); CloseChat(false); }
                _refreshTimer = 0f;
                break;
            case "quit":
                GetTree().Quit();
                break;
        }
        RefreshTray();
    }

    void Say(string text)
    {
        _bubble = text;
        _bubbleT = 0f;
        _bubbleLife = Mathf.Clamp(2.5f + text.Length * 0.06f, 3f, 9f);
    }

    void StopCore()
    {
        _core?.Stop();
        _core = null;
        if (_tray != null) _tray.Visible = false;
        _single?.Dispose();
        _single = null;
    }
}
