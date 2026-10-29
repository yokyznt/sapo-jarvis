using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using Godot;

namespace Sapo;

public sealed record Skin(string Id, string Name, Color Body, Color Outline, Color Cheek, Color Mouth, Color Tongue, string Accessory, Color Accent)
{
    public static readonly Skin Default = new("clasico", "Clásico", new Color("b6dc9b"), new Color("1c1c1c"), new Color("f7a3a0"), new Color("7a2236"), new Color("ff6b8a"), "none", Colors.White);

    public static List<Skin> LoadAll()
    {
        var list = new List<Skin>();
        if (Godot.FileAccess.FileExists("res://skins.json")) Parse(Godot.FileAccess.GetFileAsString("res://skins.json"), list);
        var dir = Path.Combine(Config.Dir, "skins");
        if (Directory.Exists(dir))
            foreach (var f in Directory.GetFiles(dir, "*.json"))
            {
                try { Parse(File.ReadAllText(f), list); }
                catch (Exception) { }
            }
        if (list.Count == 0) list.Add(Default);
        return list;
    }

    static void Parse(string json, List<Skin> list)
    {
        using var doc = JsonDocument.Parse(json);
        if (doc.RootElement.ValueKind == JsonValueKind.Array)
            foreach (var e in doc.RootElement.EnumerateArray()) Add(e, list);
        else Add(doc.RootElement, list);
    }

    static void Add(JsonElement e, List<Skin> list)
    {
        string S(string k, string d) => e.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : d;
        Color C(string k, Color d) => Color.HtmlIsValid(S(k, "")) ? new Color(S(k, "")) : d;
        var id = S("id", "");
        if (id.Length == 0) return;
        list.RemoveAll(s => s.Id == id);
        list.Add(new Skin(id, S("name", id), C("body", Default.Body), C("outline", Default.Outline), C("cheek", Default.Cheek), C("mouth", Default.Mouth), C("tongue", Default.Tongue), S("accessory", "none"), C("accent", Default.Accent)));
    }
}
