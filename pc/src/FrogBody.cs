using System.Collections.Generic;
using Godot;

namespace Sapo;

public partial class Frog
{
    const int Rings = 6;

    float Rx => R * 1.04f;
    float Ry => _jelly.Bottom;
    float Yaw => Mathf.Clamp(_gaze.V.X, -1f, 1f) * 0.3f;
    float Pitch => -Mathf.Clamp(_gaze.V.Y, -1f, 1f) * 0.2f;
    Vector2 Look => new(Mathf.Sin(Yaw) * Rx * 0.55f, -Mathf.Sin(Pitch) * Ry * 0.45f);

    (Vector2 p, Vector2 f) EyeOnSphere(int side)
    {
        var p = new Vector2(side * R * 0.36f, -R * 0.18f) + Look;
        float fx = Mathf.Clamp(1f - Mathf.Abs(Mathf.Sin(Yaw)) * 0.35f * (Mathf.Sign(Yaw) == side ? 1.3f : 0.7f), 0.6f, 1f);
        return (p, new Vector2(fx, 1f));
    }

    Vector2 MouthLocal() => new Vector2(0, R * 0.22f) + Look * 0.95f;

    Color BodyAt(Vector2 v, float s)
    {
        var top = Color.FromHsv(Skin.H, Skin.S * 0.82f, Mathf.Min(1f, Skin.V * 1.06f));
        var bottom = Color.FromHsv(Skin.H, Mathf.Min(1f, Skin.S * 1.12f), Skin.V * 0.9f);
        float t = Mathf.Clamp((v.Y + Ry) / (2f * Ry), 0f, 1f);
        var c = top.Lerp(bottom, t * t);
        c = c.Lerp(bottom.Darkened(0.06f), Mathf.SmoothStep(0.75f, 1f, s) * 0.35f);
        var h = new Vector2(-Rx * 0.36f, -Ry * 0.5f);
        float hl = Mathf.Max(0f, 1f - v.DistanceTo(h) / (R * 0.38f));
        c = c.Lerp(Colors.White, 0.5f * hl * hl);
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
        for (int i = 0; i <= n; i++) edge[i] = outline[i % n];
        DrawPolyline(edge, Color.FromHsv(Skin.H, Mathf.Min(1f, Skin.S * 1.2f), Skin.V * 0.72f), 2.2f, true);
    }

    void DrawShadow()
    {
        if (_state is State.Air or State.Held) return;
        var c = new Vector2(_pos.X, _pos.Y + _jelly.Bottom + 6f) - Origin;
        float w = R * 1.0f * (1f + _stretch.V * -0.5f);
        for (int i = 0; i < 4; i++)
        {
            float k = 1f - i * 0.22f;
            DrawSetTransformMatrix(new Transform2D(0f, new Vector2(1f, 0.16f), 0f, c));
            DrawCircle(Vector2.Zero, w * k, new Color(0f, 0f, 0f, 0.05f), true, -1f, true);
        }
        DrawSetTransformMatrix(Transform2D.Identity);
    }

    static readonly Vector2[] Freckles = { new(-0.1f, -0.03f), new(0.04f, -0.07f), new(0.08f, 0.05f) };

    void DrawCheeks()
    {
        var look = Look;
        var freckle = Color.FromHsv(Skin.H, Mathf.Min(1f, Skin.S * 1.35f), Skin.V * 0.58f);
        for (int s = -1; s <= 1; s += 2)
        {
            var c = new Vector2(s * R * 0.62f, R * 0.14f) + look * 0.9f;
            float sq = Mathf.Clamp(1f - Mathf.Abs(Mathf.Sin(Yaw)) * (Mathf.Sign(Yaw) == s ? 0.5f : 0.1f), 0.4f, 1f);
            DrawSetTransformMatrix(BaseXf() * new Transform2D(0f, new Vector2(sq, 1f), 0f, c + new Vector2(0f, R * 0.0f)));
            foreach (var f in Freckles) DrawCircle(new Vector2(f.X * s * R, f.Y * R), R * 0.045f, freckle, true, -1f, true);
        }
        DrawSetTransformMatrix(BaseXf());
    }

    void DrawEye(Transform2D xf, int side)
    {
        var (p, f) = EyeOnSphere(side);
        float w = R * 0.22f * EyeScale, h = R * 0.32f * EyeScale;
        bool closed = _scare <= 0f && (_state == State.Sleep || _eyeOpen.V < 0.3f);
        bool happy = !closed && _scare <= 0f && _eatT < 0f && (_happy > 0f || (_state == State.Dance && DanceBounce > 0.5f));
        DrawSetTransformMatrix(xf * new Transform2D(0f, f, 0f, p));
        if (closed)
        {
            DrawArc(new Vector2(0, -h * 0.2f), w * 0.62f, 0.18f * Mathf.Pi, 0.82f * Mathf.Pi, 12, Ink, 3.6f, true);
            return;
        }
        if (happy)
        {
            DrawArc(new Vector2(0, h * 0.25f), w * 0.62f, 1.18f * Mathf.Pi, 1.82f * Mathf.Pi, 12, Ink, 3.6f, true);
            return;
        }
        float k = Mathf.Clamp(_eyeOpen.V, 0.25f, 1.05f);
        DrawSetTransformMatrix(xf * new Transform2D(0f, new Vector2(f.X * w / h, f.Y * k), 0f, p));
        DrawCircle(Vector2.Zero, h * 0.5f, Ink, true, -1f, true);
        if (_scare > 0f) DrawCircle(new Vector2(-h * 0.13f, -h * 0.16f), h * 0.12f, Colors.White, true, -1f, true);
        if (_flash > 0f) DrawCircle(new Vector2(-h * 0.1f, -h * 0.12f), h * 0.32f * (_flash / 0.55f), new Color(1f, 1f, 1f, _flash / 0.55f), true, -1f, true);
        DrawSetTransformMatrix(xf);
    }

    void DrawMouth(Transform2D xf)
    {
        var m = MouthLocal();
        float r = R * 0.26f;
        float open = _mouthOpen.V;
        float sx = Mathf.Max(0.35f, Mathf.Cos(Yaw));
        DrawSetTransformMatrix(xf * new Transform2D(0f, new Vector2(sx, 1f), 0f, m));
        if (_speaking && _tonguePhase < 0 && open >= 0.08f)
        {
            float o = Mathf.Clamp(open, 0f, 1f);
            float ew = r * (0.62f - 0.12f * o), eh = r * (0.18f + 0.62f * o);
            DrawSetTransformMatrix(xf * new Transform2D(0f, new Vector2(sx * ew / eh, 1f), 0f, m + new Vector2(0, eh * 0.25f)));
            DrawCircle(Vector2.Zero, eh, MouthColor, true, -1f, true);
            if (o > 0.35f) DrawCircle(new Vector2(0, eh * 0.45f), eh * 0.45f, TongueColor, true, -1f, true);
        }
        else if (_mouthRound.V > 0.5f && open >= 0.08f)
        {
            float rr = r * (0.3f + 0.3f * Mathf.Clamp(open, 0f, 1f));
            DrawSetTransformMatrix(xf * new Transform2D(0f, new Vector2(sx * 0.85f, 1f), 0f, m));
            DrawCircle(Vector2.Zero, rr, MouthColor, true, -1f, true);
        }
        else
        {
            float o = Mathf.Clamp(open, 0f, 1f);
            float w = r * (_happy > 0f ? 0.78f : 0.62f);
            float depth = r * (0.55f + 0.55f * o);
            const int n = 16;
            var pts = new Vector2[n + 1];
            for (int i = 0; i <= n; i++)
            {
                float a = Mathf.Pi * i / n;
                pts[i] = new Vector2(Mathf.Cos(a) * w, Mathf.Sin(a) * depth);
            }
            DrawColoredPolygon(pts, MouthColor);
            var tongue = new Vector2[24];
            float tr = w * 0.58f;
            for (int i = 0; i < 24; i++)
            {
                float a = Mathf.Tau * i / 24f;
                tongue[i] = new Vector2(Mathf.Cos(a) * tr, depth * 1.02f + Mathf.Sin(a) * tr * 0.9f);
            }
            var clip = Geometry2D.IntersectPolygons(tongue, pts);
            foreach (var poly in clip) DrawColoredPolygon(poly, TongueColor);
            DrawLine(new Vector2(-w, 0), new Vector2(w, 0), MouthColor, 2.4f, true);
        }
        DrawSetTransformMatrix(xf);
    }
}
