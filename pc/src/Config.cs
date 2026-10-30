using System;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Sapo;

public static class Config
{
    public static readonly string Dir = Environment.GetEnvironmentVariable("SAPO_HOME") is { Length: > 0 } h ? h : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Sapo");
    static readonly string FilePath = Path.Combine(Dir, "config.json");
    static JsonObject _root;
    static DateTime _mtime;

    public static bool Reload()
    {
        DateTime m;
        try { m = File.Exists(FilePath) ? File.GetLastWriteTimeUtc(FilePath) : DateTime.MinValue; }
        catch (Exception) { return false; }
        if (m == _mtime) return false;
        _mtime = m;
        _root = null;
        return true;
    }

    static JsonObject Root
    {
        get
        {
            if (_root != null) return _root;
            try { _root = File.Exists(FilePath) ? JsonNode.Parse(File.ReadAllText(FilePath)) as JsonObject : null; }
            catch (Exception) { _root = null; }
            _root ??= new JsonObject();
            return _root;
        }
    }

    static JsonObject Pc
    {
        get
        {
            if (Root["pc"] is JsonObject o) return o;
            var n = new JsonObject();
            Root["pc"] = n;
            return n;
        }
    }

    public static string GetString(string key, string def)
    {
        try { return Pc[key]?.GetValue<string>() ?? def; }
        catch (Exception) { return def; }
    }

    public static float GetFloat(string key, float def)
    {
        try { return Pc[key]?.GetValue<float>() ?? def; }
        catch (Exception) { return def; }
    }

    public static bool GetBool(string key, bool def)
    {
        try { return Pc[key]?.GetValue<bool>() ?? def; }
        catch (Exception) { return def; }
    }

    public static (float x, float y)? GetPin()
    {
        try
        {
            if (Pc["pin"] is not JsonObject p) return null;
            return (p["x"].GetValue<float>(), p["y"].GetValue<float>());
        }
        catch (Exception) { return null; }
    }

    public static void Set(string key, JsonNode value)
    {
        Pc[key] = value;
        Save();
    }

    public static void SetPin((float x, float y)? pin)
    {
        Pc["pin"] = pin is { } p ? new JsonObject { ["x"] = p.x, ["y"] = p.y } : null;
        Save();
    }

    public static void EnsureStartupCommand(string command)
    {
        Reload();
        var st = Root["startup"] as JsonObject;
        if (st != null && OperatingSystem.IsWindows())
        {
            bool run = Microsoft.Win32.Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Run")?.GetValue("Sapo") is string;
            bool cur0 = false;
            try { cur0 = st["autostart"]?.GetValue<bool>() ?? false; }
            catch (Exception) { }
            if (cur0 != run) { st["autostart"] = run; Save(); }
        }
        string cur = null;
        try { cur = st?["command"]?.GetValue<string>(); }
        catch (Exception) { }
        var exe = cur?.Trim().Split('"', StringSplitOptions.RemoveEmptyEntries) is { Length: > 0 } parts ? parts[0].Trim() : null;
        if (!string.IsNullOrWhiteSpace(cur) && exe != null && File.Exists(exe)) return;
        if (st == null)
        {
            st = new JsonObject { ["autostart"] = OperatingSystem.IsWindows() && Microsoft.Win32.Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Run")?.GetValue("Sapo") is string };
            Root["startup"] = st;
        }
        st["command"] = command;
        Save();
    }

    static void Save()
    {
        try
        {
            Directory.CreateDirectory(Dir);
            var tmp = FilePath + ".tmp";
            File.WriteAllText(tmp, Root.ToJsonString(new JsonSerializerOptions { WriteIndented = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping }));
            File.Move(tmp, FilePath, true);
            _mtime = File.GetLastWriteTimeUtc(FilePath);
        }
        catch (Exception) { }
    }
}
