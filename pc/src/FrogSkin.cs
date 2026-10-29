using System.Collections.Generic;
using Godot;

namespace Sapo;

public partial class Frog
{
    static Vector2[] CirclePoly(Vector2 c, float r, int n = 32)
    {
        var p = new Vector2[n];
        for (int i = 0; i < n; i++)
        {
            float a = Mathf.Tau * i / n;
            p[i] = c + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * r;
        }
        return p;
    }

    static float PolyArea(Vector2[] p)
    {
        float a = 0f;
        for (int i = 0; i < p.Length; i++) a += p[i].Cross(p[(i + 1) % p.Length]);
        return Mathf.Abs(a) * 0.5f;
    }

    static Vector2[] Largest(Godot.Collections.Array<Vector2[]> polys)
    {
        Vector2[] best = null;
        float ba = 0f;
        foreach (var p in polys)
        {
            float a = PolyArea(p);
            if (a > ba) { ba = a; best = p; }
        }
        return best;
    }

    static Vector2[] Silhouette(Vector2[] body, Vector2 l, Vector2 r, float er)
    {
        var a = Largest(Geometry2D.MergePolygons(body, CirclePoly(l, er)));
        if (a == null) return null;
        var b = Largest(Geometry2D.MergePolygons(a, CirclePoly(r, er)));
        if (b == null || Geometry2D.TriangulatePolygon(b).Length == 0) return null;
        return b;
    }

    void DrawGills()
    {
        var col = _skin.Accent;
        for (int s = -1; s <= 1; s += 2)
            for (int i = 0; i < 3; i++)
            {
                float a = Mathf.DegToRad(-28f + i * 24f);
                var from = new Vector2(s * R * 1.02f, -R * 0.1f + i * R * 0.12f);
                var dir = new Vector2(s * Mathf.Cos(a), Mathf.Sin(a));
                var to = from + dir * R * (0.5f - i * 0.06f) + new Vector2(0, Mathf.Sin(_time * 2f + i) * R * 0.03f);
                DrawLine(from, to, Ink, R * 0.22f + 6f, true);
                DrawCircle(to, R * 0.11f + 3f, Ink, true, -1f, true);
                DrawLine(from, to, col, R * 0.22f, true);
                DrawCircle(to, R * 0.11f, col, true, -1f, true);
            }
    }

    void DrawAccessory()
    {
        var acc = _skin.Accent;
        switch (_skin.Accessory)
        {
            case "leaf":
                {
                    var stem = new Vector2(R * 0.05f, -R * 0.84f);
                    var top = stem + new Vector2(R * 0.02f, -R * 0.28f);
                    DrawLine(stem, top, Ink, 4f, true);
                    float sway = Mathf.Sin(_time * 1.4f) * 0.12f;
                    var pts = new List<Vector2>();
                    for (int i = 0; i <= 20; i++)
                    {
                        float t = i / 20f;
                        pts.Add(new Vector2(t * R * 0.8f, -Mathf.Sin(t * Mathf.Pi) * R * 0.26f));
                    }
                    for (int i = 19; i > 0; i--)
                    {
                        float t = i / 20f;
                        pts.Add(new Vector2(t * R * 0.8f, Mathf.Sin(t * Mathf.Pi) * R * 0.16f));
                    }
                    var xf = new Transform2D(-0.5f + sway, top);
                    var poly = new Vector2[pts.Count];
                    for (int i = 0; i < pts.Count; i++) poly[i] = xf * pts[i];
                    DrawColoredPolygon(poly, acc);
                    var closed = new Vector2[poly.Length + 1];
                    poly.CopyTo(closed, 0);
                    closed[^1] = poly[0];
                    DrawPolyline(closed, Ink, 4f, true);
                    DrawLine(xf * new Vector2(R * 0.05f, 0), xf * new Vector2(R * 0.5f, -R * 0.02f), acc.Darkened(0.25f), 2.5f, true);
                    break;
                }
            case "drop":
                {
                    var c = new Vector2(R * 0.02f, -R * 1.02f + Mathf.Sin(_time * 1.8f) * R * 0.03f);
                    float r = R * 0.17f;
                    var pts = new List<Vector2>();
                    for (int i = 0; i <= 24; i++)
                    {
                        float a = Mathf.Lerp(-0.15f, 1.15f, i / 24f) * Mathf.Pi;
                        pts.Add(c + new Vector2(Mathf.Cos(a) * r, Mathf.Sin(a) * r));
                    }
                    pts.Add(c + new Vector2(0, -r * 2.3f));
                    var poly = pts.ToArray();
                    DrawColoredPolygon(poly, acc);
                    var closed = new Vector2[poly.Length + 1];
                    poly.CopyTo(closed, 0);
                    closed[^1] = poly[0];
                    DrawPolyline(closed, Ink, 4f, true);
                    DrawCircle(c + new Vector2(-r * 0.35f, -r * 0.2f), r * 0.25f, Colors.White, true, -1f, true);
                    break;
                }
            case "moon":
                {
                    var c = new Vector2(R * 1.05f, -R * 1.25f + Mathf.Sin(_time * 1.2f) * R * 0.05f);
                    float r = R * 0.2f;
                    var moon = Largest(Geometry2D.ClipPolygons(CirclePoly(c, r), CirclePoly(c + new Vector2(r * 0.5f, -r * 0.3f), r * 0.85f)));
                    if (moon == null) break;
                    DrawColoredPolygon(moon, acc);
                    var closed = new Vector2[moon.Length + 1];
                    moon.CopyTo(closed, 0);
                    closed[^1] = moon[0];
                    DrawPolyline(closed, Ink, 3f, true);
                    break;
                }
            case "sparkle":
                {
                    float tw = 0.75f + 0.25f * Mathf.Sin(_time * 3f);
                    Star(new Vector2(R * 1.1f, -R * 1.1f), R * 0.2f * tw, acc);
                    Star(new Vector2(-R * 1.15f, -R * 0.75f), R * 0.12f * (1.75f - tw), acc);
                    break;
                }
        }
    }

    void Star(Vector2 c, float r, Color col)
    {
        var p = new Vector2[8];
        for (int i = 0; i < 8; i++)
        {
            float a = Mathf.Tau * i / 8f - Mathf.Pi * 0.5f;
            float rr = i % 2 == 0 ? r : r * 0.32f;
            p[i] = c + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * rr;
        }
        DrawColoredPolygon(p, col);
        var closed = new Vector2[9];
        p.CopyTo(closed, 0);
        closed[8] = p[0];
        DrawPolyline(closed, Ink, 2.5f, true);
    }
}
