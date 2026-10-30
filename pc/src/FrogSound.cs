using System;
using System.Collections.Generic;
using System.IO;
using Godot;

namespace Sapo;

public static class Croaks
{
    public const int Rate = 22050;
    public static readonly string[] Kinds = { "corto", "doble", "grunon", "feliz", "sueno", "sorpresa", "aterrizaje", "plop" };

    readonly struct Formant
    {
        public readonly float F, Bw, Gain;
        public Formant(float f, float bw, float gain) { F = f; Bw = bw; Gain = gain; }
    }

    static readonly Formant[] Bright = { new(780f, 260f, 1f), new(1550f, 380f, 0.55f), new(2700f, 520f, 0.22f) };
    static readonly Formant[] Round = { new(520f, 220f, 1f), new(1050f, 300f, 0.45f), new(2300f, 480f, 0.12f) };
    static readonly Formant[] Low = { new(380f, 200f, 1f), new(820f, 260f, 0.5f), new(1900f, 420f, 0.12f) };

    public static float[] Make(string kind, int seed = 7)
    {
        var rng = new Random(seed);
        var buf = new float[(int)(Rate * Length(kind))];
        switch (kind)
        {
            case "corto":
                Voice(buf, rng, 0f, 0.2f, 430f, 300f, 46f, Bright, 0.05f, 1f);
                break;
            case "doble":
                Voice(buf, rng, 0f, 0.14f, 440f, 330f, 48f, Bright, 0.05f, 1f);
                Voice(buf, rng, 0.2f, 0.17f, 400f, 280f, 44f, Bright, 0.05f, 0.9f);
                break;
            case "grunon":
                Voice(buf, rng, 0f, 0.5f, 190f, 128f, 27f, Low, 0.12f, 1f);
                break;
            case "feliz":
                Voice(buf, rng, 0f, 0.1f, 380f, 450f, 50f, Bright, 0.04f, 0.85f);
                Voice(buf, rng, 0.13f, 0.1f, 450f, 540f, 52f, Bright, 0.04f, 0.9f);
                Voice(buf, rng, 0.26f, 0.16f, 540f, 660f, 55f, Bright, 0.04f, 1f);
                break;
            case "sueno":
                Voice(buf, rng, 0f, 0.8f, 260f, 175f, 11f, Round, 0.22f, 0.55f);
                break;
            case "sorpresa":
                Voice(buf, rng, 0f, 0.24f, 320f, 640f, 58f, Bright, 0.06f, 1f);
                break;
            case "aterrizaje":
                Thud(buf, rng, 0f, 0.12f, 0.8f);
                Voice(buf, rng, 0.03f, 0.24f, 330f, 150f, 36f, Round, 0.08f, 0.9f);
                break;
            case "plop":
                Bubble(buf, 0f, 0.11f, 380f, 1100f, 1f);
                Voice(buf, rng, 0.15f, 0.12f, 420f, 340f, 48f, Bright, 0.04f, 0.45f);
                break;
        }
        Finish(buf, kind == "sueno" ? 0.5f : kind == "grunon" ? 0.72f : 0.8f);
        return buf;
    }

    static float Length(string kind) => kind switch
    {
        "corto" => 0.26f,
        "doble" => 0.43f,
        "grunon" => 0.56f,
        "feliz" => 0.48f,
        "sueno" => 0.88f,
        "sorpresa" => 0.3f,
        "aterrizaje" => 0.32f,
        "plop" => 0.32f,
        _ => 0.3f
    };

    static float Env(float t, float dur, float att, float rel)
    {
        if (t < 0f || t > dur) return 0f;
        float a = Mathf.Clamp(t / att, 0f, 1f);
        float r = Mathf.Clamp((dur - t) / rel, 0f, 1f);
        return a * a * (3f - 2f * a) * r * r * (3f - 2f * r) * (1f - 0.35f * t / dur);
    }

    static float FormantGain(float f, Formant[] fs)
    {
        float g = 0f;
        foreach (var x in fs)
        {
            float d = (f - x.F) / x.Bw;
            g += x.Gain / (1f + d * d);
        }
        return g;
    }

    static void Voice(float[] buf, Random rng, float start, float dur, float f0a, float f0b, float am, Formant[] fs, float noise, float gain)
    {
        int s0 = (int)(start * Rate), n = (int)(dur * Rate);
        double ph = rng.NextDouble(), amPh = 0;
        float lp = 0f, jit = 0f;
        for (int i = 0; i < n && s0 + i < buf.Length; i++)
        {
            float t = i / (float)Rate;
            float k = t / dur;
            float f0 = f0a * Mathf.Pow(f0b / f0a, k * (2f - k));
            jit += ((float)rng.NextDouble() - 0.5f) * 0.02f - jit * 0.05f;
            f0 *= 1f + jit * 0.03f;
            ph += f0 / Rate;
            amPh += am / Rate;
            float v = 0f;
            for (int h = 1; h * f0 < 5000f && h <= 24; h++)
                v += Mathf.Sin((float)(Mathf.Tau * h * (ph - Math.Floor(ph)))) * FormantGain(h * f0, fs) / Mathf.Pow(h, 0.6f);
            float pulse = 0.5f - 0.5f * Mathf.Cos((float)(Mathf.Tau * (amPh - Math.Floor(amPh))));
            float trem = 0.35f + 0.65f * pulse * pulse;
            lp += (((float)rng.NextDouble() * 2f - 1f) - lp) * 0.18f;
            float e = Env(t, dur, 0.012f, Mathf.Min(0.06f, dur * 0.4f));
            buf[s0 + i] += gain * e * (v * 0.3f * trem + lp * noise * 2.2f * (0.6f + 0.4f * trem));
        }
    }

    static void Thud(float[] buf, Random rng, float start, float dur, float gain)
    {
        int s0 = (int)(start * Rate), n = (int)(dur * Rate);
        float lp = 0f, ph = 0f;
        for (int i = 0; i < n && s0 + i < buf.Length; i++)
        {
            float t = i / (float)Rate;
            float e = Mathf.Exp(-t * 32f) * Mathf.Clamp(t / 0.003f, 0f, 1f);
            lp += (((float)rng.NextDouble() * 2f - 1f) - lp) * 0.08f;
            ph += Mathf.Lerp(140f, 70f, t / dur) / Rate;
            buf[s0 + i] += gain * e * (lp * 1.6f + Mathf.Sin(Mathf.Tau * ph) * 0.7f);
        }
    }

    static void Bubble(float[] buf, float start, float dur, float fa, float fb, float gain)
    {
        int s0 = (int)(start * Rate), n = (int)(dur * Rate);
        float ph = 0f;
        for (int i = 0; i < n && s0 + i < buf.Length; i++)
        {
            float t = i / (float)Rate;
            float k = t / dur;
            float f = fa * Mathf.Pow(fb / fa, k * k);
            ph += f / Rate;
            float e = Mathf.Clamp(t / 0.004f, 0f, 1f) * Mathf.Exp(-k * 4f) * Mathf.Clamp((dur - t) / 0.02f, 0f, 1f);
            buf[s0 + i] += gain * e * Mathf.Sin(Mathf.Tau * ph);
        }
    }

    static void Finish(float[] buf, float peak)
    {
        float dc = 0f, prev = 0f;
        for (int i = 0; i < buf.Length; i++)
        {
            float x = buf[i];
            dc = x - prev + 0.995f * dc;
            prev = x;
            buf[i] = dc;
        }
        float lp = 0f;
        for (int i = 0; i < buf.Length; i++)
        {
            lp += (buf[i] - lp) * 0.55f;
            buf[i] = lp;
        }
        float m = 0f;
        foreach (var x in buf) m = Mathf.Max(m, Mathf.Abs(x));
        if (m < 1e-6f) return;
        float g = peak / m;
        int fade = Math.Min(buf.Length, Rate / 200);
        for (int i = 0; i < buf.Length; i++)
        {
            float x = buf[i] * g;
            buf[i] = MathF.Tanh(x * 1.1f) / MathF.Tanh(1.1f);
            if (i >= buf.Length - fade) buf[i] *= (buf.Length - 1 - i) / (float)fade;
        }
    }

    public static byte[] Pcm16(float[] buf)
    {
        var data = new byte[buf.Length * 2];
        for (int i = 0; i < buf.Length; i++)
        {
            short s = (short)Mathf.Clamp(Mathf.RoundToInt(buf[i] * 32767f), -32767, 32767);
            data[i * 2] = (byte)(s & 0xff);
            data[i * 2 + 1] = (byte)((s >> 8) & 0xff);
        }
        return data;
    }

    public static AudioStreamWav Stream(string kind) => new()
    {
        Format = AudioStreamWav.FormatEnum.Format16Bits,
        MixRate = Rate,
        Stereo = false,
        Data = Pcm16(Make(kind))
    };

    public static void Dump(string dir)
    {
        Directory.CreateDirectory(dir);
        foreach (var kind in Kinds)
        {
            var pcm = Pcm16(Make(kind));
            using var w = new BinaryWriter(File.Create(Path.Combine(dir, kind + ".wav")));
            w.Write("RIFF"u8.ToArray());
            w.Write(36 + pcm.Length);
            w.Write("WAVEfmt "u8.ToArray());
            w.Write(16);
            w.Write((short)1);
            w.Write((short)1);
            w.Write(Rate);
            w.Write(Rate * 2);
            w.Write((short)2);
            w.Write((short)16);
            w.Write("data"u8.ToArray());
            w.Write(pcm.Length);
            w.Write(pcm);
        }
    }
}

public partial class Frog
{
    readonly Dictionary<string, AudioStreamWav> _croaks = new();
    AudioStreamPlayer _player;
    bool _sounds = true, _quiet, _speaking, _grabCroaked;
    float _volume = 0.6f, _croakMin = 3f, _croakMax = 10f, _croakCd, _casualTimer, _mouthLevel, _mouthAge = 9f;
    string _lastCroak = "";
    const float CroakGap = 4f;

    static bool DumpRequested(out string dir)
    {
        dir = Path.Combine(System.IO.Path.GetTempPath(), "croacs");
        foreach (var a in OS.GetCmdlineArgs()) if (a == "--dump-croaks") return true;
        foreach (var a in OS.GetCmdlineUserArgs())
        {
            if (a == "--dump-croaks") return true;
            if (a.StartsWith("--dump-croaks=")) { dir = a[14..]; return true; }
        }
        return false;
    }

    void SetupSound()
    {
        foreach (var k in Croaks.Kinds) _croaks[k] = Croaks.Stream(k);
        _player = new AudioStreamPlayer();
        AddChild(_player);
        LoadSoundPrefs();
        ResetCasual();
    }

    void LoadSoundPrefs()
    {
        _sounds = Config.GetBool("sounds", true);
        _volume = Mathf.Clamp(Config.GetFloat("volume", 0.6f), 0f, 1f);
        _croakMin = Mathf.Max(0.1f, Config.GetFloat("croak_min", 3f));
        _croakMax = Mathf.Max(_croakMin, Config.GetFloat("croak_max", 10f));
        if (_player != null) _player.VolumeDb = Mathf.LinearToDb(Mathf.Max(0.0001f, _volume));
        if (Muted && _player != null && _player.Playing) _player.Stop();
    }

    void ResetCasual() => _casualTimer = _rng.RandfRange(_croakMin, _croakMax) * 60f;

    bool Muted => !_sounds || _volume <= 0.001f || _quiet || _calm || _desk.GameRunning || _speaking || _hidden;

    void Croak(string kind)
    {
        bool replace = kind == "grunon" && _lastCroak == "sorpresa" && _croakCd > CroakGap - 2f;
        if (_player == null || Muted || (_croakCd > 0f && !replace) || !_croaks.TryGetValue(kind, out var s)) return;
        if (_state == State.Sleep && kind != "sueno") return;
        _croakCd = CroakGap;
        _lastCroak = kind;
        _player.Stream = s;
        _player.PitchScale = _rng.RandfRange(0.92f, 1.08f);
        _player.VolumeDb = Mathf.LinearToDb(Mathf.Max(0.0001f, _volume));
        _player.Play();
    }

    void UpdateSound(float dt)
    {
        _croakCd -= dt;
        if (Muted && _player != null && _player.Playing) _player.Stop();
        if (_state == State.Held && !_grabCroaked && _time - _pressTime > 0.22f)
        {
            _grabCroaked = true;
            Croak("sorpresa");
        }
        if (_state is State.Sleep or State.Held or State.Air) return;
        _casualTimer -= dt;
        if (_casualTimer > 0f) return;
        ResetCasual();
        Croak(_rng.Randf() < 0.6f ? "corto" : "doble");
    }

    void SetMouth(float level)
    {
        _mouthLevel = Mathf.Clamp(level, 0f, 1f);
        _mouthAge = 0f;
    }

    float TalkMouth(float dt)
    {
        _mouthAge += dt;
        if (!_speaking || _mouthAge > 0.3f) _mouthLevel = 0f;
        return _mouthLevel;
    }
}
