using System;
using System.Collections.Generic;
using Godot;

namespace Sapo;

public partial class Frog
{
    static readonly Color Skin = new("b6dc9b");
    static readonly Color Ink = new("1c1c1c");
    static readonly Color Cheek = new("f7a3a0");
    static readonly Color TongueColor = new("ff6b8a");
    static readonly Color MouthColor = new("7a2236");
    static readonly Color Heart = new("ff4d6d");
    static readonly Color Dust = new(1f, 1f, 1f, 0.85f);

    float DanceBounce => Mathf.Abs(Mathf.Sin(_danceT * Mathf.Pi * 1.4f));

    Vector2 Mouth() => Origin + BaseXf() * new Vector2(0, R * 0.02f);

    Transform2D BaseXf()
    {
        float breath = _state == State.Sleep ? Mathf.Sin(_time * 1.6f) * 0.035f : Grounded ? Mathf.Sin(_time * 2.4f) * 0.012f : 0f;
        float s = _stretch.V + breath;
        var scale = new Vector2(1f - s * 0.6f, 1f + s);
        float b = _jelly.Bottom;
        var foot = _pos - Origin + new Vector2(0, b - _hop.V);
        return new Transform2D(_tilt.V, scale, 0f, foot) * new Transform2D(0f, new Vector2(0, -b));
    }

    void Animate(float dt)
    {
        float st = 0f;
        if (_state == State.Air) st = Mathf.Clamp(Mathf.Abs(_vel.Y) / 3200f, 0f, 0.16f);
        else if (_state == State.Held) st = Mathf.Clamp(_cursorVel.Length() / 5000f, 0f, 0.12f);
        else if (_state == State.Crouch) st = -0.16f;
        else if (_state == State.Dance) st = -0.08f + 0.16f * DanceBounce;
        _stretch.To(st, 240f, 13f, dt);

        float tl = Mathf.Sin(_time * 0.7f) * 0.02f;
        if (_state == State.Air) tl = Mathf.Clamp(_vel.X * 0.00018f, -0.35f, 0.35f);
        else if (_state == State.Held) tl = Mathf.Clamp(_cursorVel.X * 0.00015f, -0.4f, 0.4f);
        else if (_state == State.Dance) tl = Mathf.Sin(_danceT * Mathf.Pi * 0.7f) * 0.16f;
        _tilt.To(tl, 140f, 11f, dt);

        _hop.To(_state == State.Dance ? DanceBounce * R * 0.28f : 0f, 400f, 30f, dt);

        _gazeTimer -= dt;
        var toCursor = Toward(_cursor);
        if (_tonguePhase >= 0) _gazeTarget = Toward(_tip);
        else if (_state == State.Air) _gazeTarget = new Vector2(Mathf.Sign(_vel.X) * 0.6f, _vel.Y > 0 ? 0.6f : -0.5f);
        else if (_lookAroundTimer > 0f)
        {
            _lookAroundTimer -= dt;
            if (_gazeTimer <= 0f)
            {
                _gazeTimer = _rng.RandfRange(0.25f, 0.6f);
                _gazeTarget = RandomGaze();
            }
        }
        else if (_time - _lastCursorMove < 1.8f) _gazeTarget = toCursor;
        else if (_gazeTimer <= 0f)
        {
            _gazeTimer = _rng.RandfRange(0.8f, 2.6f);
            _gazeTarget = _rng.Randf() < 0.4f ? Vector2.Zero : _rng.Randf() < 0.3f ? toCursor : RandomGaze();
        }
        _gaze.To(_gazeTarget, 200f, 26f, dt);

        _blinkTimer -= dt;
        if (_blinkTimer <= 0f)
        {
            _blinkHold = 0.08f;
            _blinkTimer = _rng.Randf() < 0.2f ? 0.22f : _rng.RandfRange(1.8f, 5.5f);
        }
        _blinkHold -= dt;
        _eyeOpen.To(_blinkHold > 0f ? 0f : 1f, 1100f, 55f, dt);

        float mo = 0f, mr = 0f;
        if (_tonguePhase >= 0) { mo = 1f; mr = 1f; }
        else if (_state == State.Dance) mo = 0.35f + 0.45f * DanceBounce;
        else if (_happy > 0f) mo = 0.6f;
        else if (_state == State.Held) { mo = 0.35f + Mathf.Clamp(_cursorVel.Length() / 3000f, 0f, 0.5f); mr = 1f; }
        else if (_state == State.Air)
        {
            if (_vel.Y > 700f) { mo = 0.7f; mr = 1f; }
            else if (_vel.Y < -300f) mo = 0.45f;
        }
        _mouthOpen.To(mo, 320f, 24f, dt);
        _mouthRound.To(mr, 320f, 24f, dt);

        StepParticles(_puffs, dt, 0.88f);
        StepParticles(_notes, dt, 1f);
    }

    Vector2 Toward(Vector2 screen)
    {
        var d = screen - _pos;
        return d.Normalized() * Mathf.Min(1f, d.Length() / (R * 4f));
    }

    Vector2 RandomGaze()
    {
        float a = _rng.RandfRange(0f, Mathf.Tau);
        return new Vector2(Mathf.Cos(a), Mathf.Sin(a) * 0.7f) * _rng.RandfRange(0.4f, 1f);
    }

    static void StepParticles(List<Particle> list, float dt, float drag)
    {
        for (int i = list.Count - 1; i >= 0; i--)
        {
            var p = list[i];
            p.T += dt;
            p.P += p.V * dt;
            p.V *= drag;
            if (p.T >= p.Life) list.RemoveAt(i);
        }
    }

    (Vector2 l, Vector2 r, float er) Eyes()
    {
        float er = R * 0.38f;
        var l = _jelly.At(Mathf.DegToRad(-124f)) * 0.78f + new Vector2(0, -R * 0.2f);
        var r = _jelly.At(Mathf.DegToRad(-56f)) * 0.78f + new Vector2(0, -R * 0.2f);
        return (l, r, er);
    }

    void UpdateRegion()
    {
        var xf = BaseXf();
        var pts = new List<Vector2>();
        foreach (var p in _jelly.Outline(Vector2.Zero, Vector2.One, 1)) pts.Add(xf * (p * 1.14f));
        var (l, r, er) = Eyes();
        AddCircle(pts, xf * l, er + 7f);
        AddCircle(pts, xf * r, er + 7f);
        if (_tonguePhase >= 0) AddCircle(pts, _tip - Origin, R * 0.25f);
        var o = _pos - Origin;
        if (_listening) { AddCircle(pts, o + new Vector2(R * 1.25f, -R * 0.2f), R * 0.8f); AddCircle(pts, o + new Vector2(-R * 1.25f, -R * 0.2f), R * 0.8f); }
        if (_state is State.Sleep or State.Dance || _happy > 0f)
        {
            pts.Add(o + new Vector2(R * 2f, -R * 3.4f));
            pts.Add(o + new Vector2(-R * 1.4f, -R * 3.4f));
        }
        foreach (var p in _puffs) AddCircle(pts, p.P - Origin, p.Size * 2f);
        foreach (var p in _notes) AddCircle(pts, p.P - Origin + new Vector2(0, -p.Size * 2f), p.Size * 2.5f);
        if (BubbleRect(out var rect, out _, out _))
        {
            pts.Add(rect.Position - Vector2.One * 4f);
            pts.Add(new Vector2(rect.End.X + 4f, rect.Position.Y - 4f));
            pts.Add(new Vector2(rect.Position.X - 4f, rect.End.Y + 16f));
            pts.Add(new Vector2(rect.Position.X - 4f, rect.Position.Y - 4f));
            pts.Add(rect.End + new Vector2(4f, 16f));
        }
        var hull = Geometry2D.ConvexHull(pts.ToArray());
        if (SameRegion(hull)) return;
        _region = hull;
        DisplayServer.WindowSetMousePassthrough(hull);
    }

    bool SameRegion(Vector2[] h)
    {
        if (h.Length != _region.Length) return false;
        for (int i = 0; i < h.Length; i++)
            if (h[i].DistanceSquaredTo(_region[i]) > 1f) return false;
        return true;
    }

    static void AddCircle(List<Vector2> pts, Vector2 c, float r)
    {
        for (int i = 0; i < 10; i++)
        {
            float a = Mathf.Tau * i / 10f;
            pts.Add(c + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * r);
        }
    }

    public override void _Draw()
    {
        if (_hidden) return;
        foreach (var p in _puffs)
        {
            float k = p.T / p.Life;
            DrawCircle(p.P - Origin, p.Size * (1f + k * 1.2f), new Color(Dust, Dust.A * (1f - k)), true, -1f, true);
        }

        var xf = BaseXf();
        DrawSetTransformMatrix(xf);
        var body = _jelly.Outline(Vector2.Zero, Vector2.One, 4);
        var (el, erp, er) = Eyes();
        bool valid = Geometry2D.TriangulatePolygon(body).Length > 0;
        DrawCircle(el, er + 4f, Ink, true, -1f, true);
        DrawCircle(erp, er + 4f, Ink, true, -1f, true);
        var closed = new Vector2[body.Length + 1];
        body.CopyTo(closed, 0);
        closed[^1] = body[0];
        DrawPolyline(closed, Ink, 8f, true);
        DrawCircle(el, er, Skin, true, -1f, true);
        DrawCircle(erp, er, Skin, true, -1f, true);
        if (valid) DrawColoredPolygon(body, Skin);
        else DrawCircle(Vector2.Zero, R, Skin, true, -1f, true);

        DrawEye(xf, el, er);
        DrawEye(xf, erp, er);
        for (int s = -1; s <= 1; s += 2)
        {
            DrawSetTransformMatrix(xf * new Transform2D(0f, new Vector2(1f, 0.82f), 0f, new Vector2(s * R * 0.74f, R * 0.1f)));
            DrawCircle(Vector2.Zero, R * 0.19f, Cheek, true, -1f, true);
        }
        DrawSetTransformMatrix(xf);
        DrawMouth(xf);
        if (_tonguePhase >= 0)
        {
            var tip = xf.AffineInverse() * (_tip - Origin);
            var m = new Vector2(0, R * 0.02f);
            DrawLine(m, tip, TongueColor.Darkened(0.25f), R * 0.2f + 3f, true);
            DrawLine(m, tip, TongueColor, R * 0.2f, true);
            DrawCircle(tip, R * 0.17f, TongueColor, true, -1f, true);
        }

        DrawSetTransformMatrix(Transform2D.Identity);
        var o = _pos - Origin;
        foreach (var n in _notes) DrawNote(n);
        if (_state == State.Sleep) DrawZ(o);
        if (_happy > 0f) DrawHearts(o);
        DrawListening(o);
        DrawBubble();
    }

    void DrawEye(Transform2D xf, Vector2 c, float er)
    {
        if (_state == State.Sleep || _eyeOpen.V < 0.3f)
        {
            DrawArc(c + new Vector2(0, -er * 0.1f), er * 0.42f, 0.15f * Mathf.Pi, 0.85f * Mathf.Pi, 12, Ink, 4.5f, true);
            return;
        }
        if (_happy > 0f || (_state == State.Dance && DanceBounce > 0.5f))
        {
            DrawArc(c + new Vector2(0, er * 0.25f), er * 0.42f, 1.15f * Mathf.Pi, 1.85f * Mathf.Pi, 12, Ink, 4.5f, true);
            return;
        }
        float pr = er * 0.6f;
        var pc = c + new Vector2(0, er * 0.08f) + _gaze.V * er * 0.16f;
        float open = Mathf.Clamp(_eyeOpen.V, 0.3f, 1.08f);
        DrawSetTransformMatrix(xf * new Transform2D(0f, new Vector2(1f, open), 0f, pc));
        DrawCircle(Vector2.Zero, pr, Ink, true, -1f, true);
        if (open > 0.6f) DrawCircle(new Vector2(pr * 0.32f, -pr * 0.32f), pr * 0.3f, Colors.White, true, -1f, true);
        DrawSetTransformMatrix(xf);
    }

    void DrawMouth(Transform2D xf)
    {
        var m = new Vector2(0, R * 0.02f);
        float r = R * 0.22f;
        float open = _mouthOpen.V;
        var c = m + new Vector2(0, -r * 0.75f);
        if (open < 0.08f)
        {
            DrawArc(c, r, (_happy > 0f ? 0.12f : 0.22f) * Mathf.Pi, (_happy > 0f ? 0.88f : 0.78f) * Mathf.Pi, 18, Ink, 4.5f, true);
            return;
        }
        if (_mouthRound.V > 0.5f)
        {
            DrawSetTransformMatrix(xf * new Transform2D(0f, new Vector2(0.85f, 1f), 0f, m + new Vector2(0, r * 0.1f)));
            float rr = r * (0.3f + 0.35f * Mathf.Clamp(open, 0f, 1f));
            DrawCircle(Vector2.Zero, rr, MouthColor, true, -1f, true);
            DrawCircle(Vector2.Zero, rr, Ink, false, 4f, true);
            DrawSetTransformMatrix(xf);
            return;
        }
        var pts = new Vector2[15];
        float depth = 0.35f + Mathf.Clamp(open, 0f, 1f) * 0.75f;
        for (int i = 0; i < 14; i++)
        {
            float a = Mathf.Lerp(0.08f, 0.92f, i / 13f) * Mathf.Pi;
            pts[i] = c + new Vector2(Mathf.Cos(a) * r * 1.05f, r * 0.55f + Mathf.Sin(a) * r * depth);
        }
        pts[14] = pts[0];
        var poly = pts[..14];
        if (Geometry2D.TriangulatePolygon(poly).Length > 0) DrawColoredPolygon(poly, MouthColor);
        DrawPolyline(pts, Ink, 4f, true);
    }

    void DrawNote(Particle n)
    {
        float k = n.T / n.Life;
        var col = new Color(n.Size > R * 0.16f ? Heart : new Color("4caf50"), 1f - k * k);
        var p = n.P - Origin + new Vector2(Mathf.Sin(n.T * 5f) * 6f, 0);
        float s = n.Size;
        DrawSetTransformMatrix(new Transform2D(-0.35f, new Vector2(1.25f, 0.9f), 0f, p));
        DrawCircle(Vector2.Zero, s * 0.55f, col, true, -1f, true);
        DrawSetTransformMatrix(Transform2D.Identity);
        DrawLine(p + new Vector2(s * 0.6f, 0), p + new Vector2(s * 0.6f, -s * 2f), col, 2.5f, true);
        DrawLine(p + new Vector2(s * 0.6f, -s * 2f), p + new Vector2(s * 1.3f, -s * 1.4f), col, 2.5f, true);
    }

    void DrawZ(Vector2 o)
    {
        var font = ThemeDB.FallbackFont;
        for (int i = 0; i < 3; i++)
        {
            float t = Mathf.PosMod(_time * 0.6f + i / 3f, 1f);
            var p = o + new Vector2(R * (0.7f + t * 0.8f), -R * (1.3f + t * 1.6f));
            DrawString(font, p, "z", HorizontalAlignment.Left, -1, (int)(R * (0.35f + t * 0.3f)), new Color(Ink, 1f - t));
        }
    }

    void DrawHearts(Vector2 o)
    {
        float t = 1f - _happy / 1.6f;
        for (int i = -1; i <= 1; i++)
        {
            var c = o + new Vector2(i * R * 0.7f, -R * (1.6f + t * 1.2f + Mathf.Abs(i) * 0.2f));
            float s = R * 0.16f * (1f - 0.3f * t);
            var col = new Color(Heart, 1f - t);
            DrawCircle(c + new Vector2(-s * 0.5f, 0), s * 0.55f, col, true, -1f, true);
            DrawCircle(c + new Vector2(s * 0.5f, 0), s * 0.55f, col, true, -1f, true);
            DrawColoredPolygon(new[] { c + new Vector2(-s * 1.02f, s * 0.15f), c + new Vector2(s * 1.02f, s * 0.15f), c + new Vector2(0, s * 1.2f) }, col);
        }
    }
}
