using System.Collections.Generic;
using Godot;

namespace Sapo;

public partial class Frog
{
    const float EyeSpread = 0.4f;
    const float EyePitch = 0.3f;
    const int Rings = 6;

    float Rx => R * 1.16f;
    float Ry => _jelly.Bottom;
    float Yaw => Mathf.Clamp(_gaze.V.X, -1f, 1f) * 0.34f;
    float Pitch => -Mathf.Clamp(_gaze.V.Y, -1f, 1f) * 0.22f;

    (Vector2 p, Vector2 f) EyeOnSphere(int side)
    {
        float yaw = Yaw;
        var p = new Vector2(side * R * 0.58f + Mathf.Sin(yaw) * Rx * 0.5f, -R * 0.66f - Mathf.Sin(Pitch) * Ry * 0.4f);
        float fx = Mathf.Clamp(Mathf.Cos(yaw + side * EyeSpread) / Mathf.Cos(EyeSpread), 0.6f, 1.06f);
        var f = new Vector2(fx, Mathf.Max(0.82f, Mathf.Cos(Pitch)));
        return (p, f);
    }

    Vector2 MouthLocal() => new(Mathf.Sin(Yaw) * Rx * 0.75f, Ry * 0.1f - Mathf.Sin(Pitch) * Ry * 0.35f);

    Color BodyAt(Vector2 v, float s)
    {
        var top = Color.FromHsv(Skin.H, Skin.S * 0.95f, Mathf.Min(1f, Skin.V * 1.08f));
        var bottom = Color.FromHsv(Skin.H, Mathf.Min(1f, Skin.S * 1.25f), Skin.V * 0.84f);
        var rimCol = Color.FromHsv(Skin.H, Mathf.Min(1f, Skin.S * 1.4f), Skin.V * 0.62f);
        var a = new Vector2(Rx * 0.7f, -Ry * 0.85f);
        var b = new Vector2(-Rx * 0.8f, Ry * 0.9f);
        var ab = b - a;
        float t = Mathf.Clamp((v - a).Dot(ab) / ab.LengthSquared(), 0f, 1f);
        var c = top.Lerp(bottom, t);
        float rim = Mathf.SmoothStep(0.6f, 1f, s) * 0.45f;
        c = c.Lerp(rimCol, rim);
        var h = new Vector2(Rx * 0.34f, -Ry * 0.46f);
        float hl = Mathf.Max(0f, 1f - v.DistanceTo(h) / (R * 0.46f));
        c = c.Lerp(Colors.White, 0.6f * hl * hl);
        c.A = 1f;
        return c;
    }

    void DrawSoftBody(Vector2[] outline)
    {
        int n = outline.Length;
        var center = new Vector2(0, Ry * 0.05f);
        var pts = new Vector2[1 + n * Rings];
        var cols = new Color[pts.Length];
        pts[0] = center;
        cols[0] = BodyAt(center, 0f);
        for (int k = 1; k <= Rings; k++)
        {
            float s = k / (float)Rings;
            for (int i = 0; i < n; i++)
            {
                var v = center + (outline[i] - center) * s;
                int idx = 1 + (k - 1) * n + i;
                pts[idx] = v;
                cols[idx] = BodyAt(v, s);
            }
        }
        var ind = new List<int>(n * 3 * (2 * Rings - 1));
        for (int i = 0; i < n; i++)
        {
            ind.Add(0);
            ind.Add(1 + i);
            ind.Add(1 + (i + 1) % n);
        }
        for (int k = 1; k < Rings; k++)
            for (int i = 0; i < n; i++)
            {
                int a = 1 + (k - 1) * n + i, b = 1 + (k - 1) * n + (i + 1) % n;
                int c = a + n, d = b + n;
                ind.Add(a); ind.Add(c); ind.Add(d);
                ind.Add(a); ind.Add(d); ind.Add(b);
            }
        RenderingServer.CanvasItemAddTriangleArray(GetCanvasItem(), ind.ToArray(), pts, cols);
        var edge = new Vector2[n + 1];
        var edgeCols = new Color[n + 1];
        for (int i = 0; i <= n; i++)
        {
            edge[i] = outline[i % n];
            edgeCols[i] = BodyAt(edge[i], 1f).Darkened(0.12f);
        }
        DrawPolylineColors(edge, edgeCols, 2f, true);
    }

    void DrawShadow()
    {
        if (_state is State.Air or State.Held) return;
        var c = new Vector2(_pos.X, _pos.Y + _jelly.Bottom + 6f) - Origin;
        float w = R * 1.05f * (1f + _stretch.V * -0.5f);
        for (int i = 0; i < 4; i++)
        {
            float k = 1f - i * 0.22f;
            DrawSetTransformMatrix(new Transform2D(0f, new Vector2(1f, 0.16f), 0f, c));
            DrawCircle(Vector2.Zero, w * k, new Color(0f, 0f, 0f, 0.05f), true, -1f, true);
        }
        DrawSetTransformMatrix(Transform2D.Identity);
    }

    void DrawCheeks()
    {
        float yo = Mathf.Sin(Yaw) * Rx * 0.8f;
        for (int s = -1; s <= 1; s += 2)
        {
            var c = new Vector2(s * R * 0.8f + yo * 0.8f, R * 0.06f - Mathf.Sin(Pitch) * Ry * 0.3f);
            for (int i = 0; i < 3; i++)
            {
                float k = 1f - i * 0.22f;
                DrawSetTransformMatrix(BaseXf() * new Transform2D(0f, new Vector2(1f, 0.6f), 0f, c));
                DrawCircle(Vector2.Zero, R * 0.25f * k, new Color(Cheek, 0.3f), true, -1f, true);
            }
        }
        DrawSetTransformMatrix(BaseXf());
    }

    void DrawPill(Vector2 c, float w, float h, Color col)
    {
        float r = Mathf.Min(w, h) * 0.5f;
        var pts = new List<Vector2>();
        void Arc(Vector2 o, float a0)
        {
            for (int i = 0; i <= 8; i++)
            {
                float a = a0 + Mathf.Pi * 0.5f * i / 8f;
                pts.Add(o + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * r);
            }
        }
        float hx = w * 0.5f - r, hy = h * 0.5f - r;
        Arc(c + new Vector2(hx, hy), 0f);
        Arc(c + new Vector2(-hx, hy), Mathf.Pi * 0.5f);
        Arc(c + new Vector2(-hx, -hy), Mathf.Pi);
        Arc(c + new Vector2(hx, -hy), Mathf.Pi * 1.5f);
        DrawColoredPolygon(pts.ToArray(), col);
        var closed = new Vector2[pts.Count + 1];
        pts.CopyTo(closed);
        closed[^1] = pts[0];
        DrawPolyline(closed, col, 1.2f, true);
    }

    void DrawEye(Transform2D xf, int side)
    {
        var (p, f) = EyeOnSphere(side);
        float w = R * 0.36f, h = R * 0.43f;
        DrawSetTransformMatrix(xf * new Transform2D(0f, f, 0f, p));
        bool closed = _state == State.Sleep || _eyeOpen.V < 0.3f;
        bool happy = !closed && (_happy > 0f || (_state == State.Dance && DanceBounce > 0.5f));
        if (closed)
        {
            DrawArc(new Vector2(0, -h * 0.1f), w * 0.5f, 0.15f * Mathf.Pi, 0.85f * Mathf.Pi, 12, Ink, 4.5f, true);
            return;
        }
        if (happy)
        {
            DrawArc(new Vector2(0, h * 0.2f), w * 0.5f, 1.15f * Mathf.Pi, 1.85f * Mathf.Pi, 12, Ink, 4.5f, true);
            return;
        }
        float hh = Mathf.Max(h * Mathf.Clamp(_eyeOpen.V, 0f, 1.08f), w * 0.3f);
        DrawPill(Vector2.Zero, w, hh, Ink);
        if (hh > h * 0.6f)
        {
            DrawCircle(new Vector2(w * 0.16f, -hh * 0.2f), w * 0.2f, new Color(1f, 1f, 1f, 0.95f), true, -1f, true);
            DrawCircle(new Vector2(-w * 0.14f, hh * 0.2f), w * 0.09f, new Color(1f, 1f, 1f, 0.7f), true, -1f, true);
        }
    }

    void DrawMouth(Transform2D xf)
    {
        var m = MouthLocal();
        float r = R * 0.22f;
        float open = _mouthOpen.V;
        DrawSetTransformMatrix(xf * new Transform2D(0f, new Vector2(Mathf.Max(0.3f, Mathf.Cos(Yaw)), 1f), 0f, m));
        if (open < 0.08f)
        {
            float k = _happy > 0f ? 0.16f : 0.24f;
            DrawArc(new Vector2(0, -r * 0.75f), r, k * Mathf.Pi, (1f - k) * Mathf.Pi, 18, Ink, 4f, true);
        }
        else if (_mouthRound.V > 0.5f)
        {
            float rr = r * (0.3f + 0.3f * Mathf.Clamp(open, 0f, 1f));
            DrawSetTransformMatrix(xf * new Transform2D(0f, new Vector2(0.85f, 1f), 0f, m));
            DrawCircle(Vector2.Zero, rr, MouthColor, true, -1f, true);
        }
        else
        {
            var pts = new Vector2[14];
            float depth = 0.4f + Mathf.Clamp(open, 0f, 1f) * 0.8f;
            for (int i = 0; i < 14; i++)
            {
                float a = Mathf.Lerp(0.06f, 0.94f, i / 13f) * Mathf.Pi;
                pts[i] = new Vector2(Mathf.Cos(a) * r * 0.75f, -r * 0.15f + Mathf.Sin(a) * r * 0.5f * depth);
            }
            DrawColoredPolygon(pts, MouthColor);
        }
        DrawSetTransformMatrix(xf);
    }
}
