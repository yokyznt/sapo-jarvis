using System;
using Godot;

namespace Sapo;

public sealed class Jelly
{
    public const int N = 40;
    const float Stiffness = 230f;
    const float Damping = 11f;
    const float Inertia = 0.03f;

    public readonly Vector2[] Rest = new Vector2[N];
    readonly Vector2[] _off = new Vector2[N];
    readonly Vector2[] _vel = new Vector2[N];
    readonly Vector2[] _tmp = new Vector2[N];
    readonly float _r;

    public Jelly(float r)
    {
        _r = r;
        float rx = r * 1.16f, ry = r * 0.86f, e = 2f / 2.7f;
        for (int i = 0; i < N; i++)
        {
            float a = Mathf.Tau * i / N;
            float c = Mathf.Cos(a), s = Mathf.Sin(a);
            var p = new Vector2(rx * Mathf.Sign(c) * Mathf.Pow(Mathf.Abs(c), e), ry * Mathf.Sign(s) * Mathf.Pow(Mathf.Abs(s), e));
            if (s < 0f)
                for (int b = -1; b <= 1; b += 2)
                {
                    float d = Mathf.AngleDifference(a, -Mathf.Pi * 0.5f + b * 0.5f);
                    p.Y -= r * 0.15f * Mathf.Exp(-(d * d) / (0.32f * 0.32f));
                }
            Rest[i] = p;
        }
        Bottom = ry;
    }

    public readonly float Bottom;

    public Vector2 Point(int i) => Rest[i] + _off[i];

    public void Step(float dt, Vector2 bodyAccel, float floorLocal)
    {
        bodyAccel = bodyAccel.LimitLength(60000f);
        const int sub = 2;
        float h = dt / sub;
        for (int s = 0; s < sub; s++)
        {
            for (int i = 0; i < N; i++)
            {
                var a = -Stiffness * _off[i] - Damping * _vel[i] - bodyAccel * Inertia;
                _vel[i] += a * h;
                _off[i] += _vel[i] * h;
            }
            for (int i = 0; i < N; i++)
            {
                var avg = (_off[(i + N - 1) % N] + _off[(i + 1) % N]) * 0.5f;
                _tmp[i] = _off[i].Lerp(avg, 0.12f).LimitLength(_r * 0.45f);
            }
            Array.Copy(_tmp, _off, N);
            if (float.IsFinite(floorLocal))
            {
                for (int i = 0; i < N; i++)
                {
                    float y = Rest[i].Y + _off[i].Y;
                    if (y <= floorLocal) continue;
                    float pen = y - floorLocal;
                    _off[i].Y -= pen;
                    _off[i].X += Mathf.Sign(Rest[i].X) * pen * 0.7f;
                    if (_vel[i].Y > 0) _vel[i].Y = 0;
                }
            }
        }
    }

    public void Squash(float amount)
    {
        for (int i = 0; i < N; i++)
        {
            if (Rest[i].Y < 0) _vel[i].Y += amount * 9f * (-Rest[i].Y / _r);
            _vel[i].X += Mathf.Sign(Rest[i].X) * amount * 3f;
        }
    }

    public void Poke(Vector2 local, float amount)
    {
        for (int i = 0; i < N; i++)
        {
            float d = Rest[i].DistanceTo(local);
            float w = Mathf.Max(0f, 1f - d / (_r * 1.2f));
            _vel[i] += -Rest[i].Normalized() * amount * w * 10f;
        }
    }

    public Vector2[] Outline(Vector2 center, Vector2 scale, int sub)
    {
        var pts = new Vector2[N * sub];
        for (int i = 0; i < N; i++)
        {
            var p0 = Point((i + N - 1) % N);
            var p1 = Point(i);
            var p2 = Point((i + 1) % N);
            var p3 = Point((i + 2) % N);
            for (int k = 0; k < sub; k++)
            {
                float t = (float)k / sub;
                float t2 = t * t, t3 = t2 * t;
                var p = 0.5f * (2f * p1 + (-p0 + p2) * t + (2f * p0 - 5f * p1 + 4f * p2 - p3) * t2 + (-p0 + 3f * p1 - 3f * p2 + p3) * t3);
                pts[i * sub + k] = center + p * scale;
            }
        }
        return pts;
    }

    public Vector2 At(float angle)
    {
        float f = Mathf.PosMod(angle, Mathf.Tau) / Mathf.Tau * N;
        int i = (int)f % N;
        return Point(i).Lerp(Point((i + 1) % N), f - Mathf.Floor(f));
    }
}
