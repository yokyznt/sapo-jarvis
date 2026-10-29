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

    static void Save()
    {
        try
        {
            Directory.CreateDirectory(Dir);
            var tmp = FilePath + ".tmp";
            File.WriteAllText(tmp, Root.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
            File.Move(tmp, FilePath, true);
        }
        catch (Exception) { }
    }
}
