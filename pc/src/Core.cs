using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using Godot;

namespace Sapo;

static class JobNative
{
    [StructLayout(LayoutKind.Sequential)]
    public struct BASIC_LIMIT
    {
        public long PerProcessUserTimeLimit, PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize, MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass, SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct IO_COUNTERS { public ulong a, b, c, d, e, f; }

    [StructLayout(LayoutKind.Sequential)]
    public struct EXTENDED_LIMIT
    {
        public BASIC_LIMIT Basic;
        public IO_COUNTERS Io;
        public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr CreateJobObject(IntPtr attr, string name);
    [DllImport("kernel32.dll")] public static extern bool SetInformationJobObject(IntPtr job, int cls, ref EXTENDED_LIMIT info, int size);
    [DllImport("kernel32.dll")] public static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

    public static IntPtr KillOnClose()
    {
        var job = CreateJobObject(IntPtr.Zero, null);
        if (job == IntPtr.Zero) return job;
        var info = new EXTENDED_LIMIT { Basic = new BASIC_LIMIT { LimitFlags = 0x2000 } };
        SetInformationJobObject(job, 9, ref info, Marshal.SizeOf<EXTENDED_LIMIT>());
        return job;
    }
}

sealed class Service
{
    public string Name, Exe, Args;
    public Func<bool> External, Wanted;
    public Process Proc;
    public readonly List<DateTime> Starts = new();
    public DateTime NextTry = DateTime.MinValue;
    public bool GaveUp;
    public string Note = "";
}

public sealed class Core
{
    public const int MaxRestarts = 5;
    public static readonly TimeSpan Window = TimeSpan.FromMinutes(5);

    readonly List<Service> _services = new();
    readonly IntPtr _job;
    readonly string _logDir;
    float _tick;

    public string Dir { get; }
    public bool Active => _services.Count > 0;

    public Core(string brainUrl)
    {
        Dir = Path.Combine(Path.GetDirectoryName(OS.GetExecutablePath()) ?? ".", "core");
        _logDir = Path.Combine(Config.Dir, "logs");
        var uri = Uri.TryCreate(brainUrl, UriKind.Absolute, out var u) ? u : new Uri("ws://127.0.0.1:8765");
        string host = uri.Host, port = uri.Port.ToString();
        var brain = Path.Combine(Dir, "sapo-brain.exe");
        var voice = Path.Combine(Dir, "sapo-voice.exe");
        if (!File.Exists(brain))
        {
            GD.Print($"core: no hay {brain}, no vigilo cerebro");
            return;
        }
        _job = JobNative.KillOnClose();
        _services.Add(new Service { Name = "sapo-brain", Exe = brain, Args = $"--host {host} --port {port}", External = () => PortOpen(host, uri.Port), Wanted = () => true });
        if (File.Exists(voice))
            _services.Add(new Service { Name = "sapo-voice", Exe = voice, Args = $"--url {uri.Scheme}://{host}:{port}", External = () => Process.GetProcessesByName("sapo-voice").Length > 0, Wanted = VoiceReady });
        GD.Print($"core: vigilo {string.Join(", ", _services.ConvertAll(s => s.Name))} en {Dir}");
    }

    public static string ModelsDir()
    {
        var env = System.Environment.GetEnvironmentVariable("SAPO_MODELS");
        if (!string.IsNullOrEmpty(env)) return env;
        var appdata = System.Environment.GetEnvironmentVariable("APPDATA") ?? "";
        return Path.Combine(appdata, "Sapo", "models");
    }

    public static bool VoiceReady()
    {
        var m = ModelsDir();
        return File.Exists(Path.Combine(m, "silero_vad", "silero_vad.onnx"))
            && File.Exists(Path.Combine(m, "sherpa-onnx-nemo-fast-conformer-ctc-es-1424-int8", "model.int8.onnx"))
            && File.Exists(Path.Combine(m, "kokoro-multi-lang-v1_0", "model.onnx"));
    }

    static bool PortOpen(string host, int port)
    {
        try
        {
            using var c = new TcpClient();
            return c.ConnectAsync(host, port).Wait(150) && c.Connected;
        }
        catch (Exception) { return false; }
    }

    public void Tick(float dt)
    {
        if (!Active) return;
        _tick -= dt;
        if (_tick > 0f) return;
        _tick = 1f;
        var now = DateTime.UtcNow;
        foreach (var s in _services)
        {
            if (s.Proc != null)
            {
                if (!s.Proc.HasExited) continue;
                GD.Print($"core: {s.Name} terminó con código {s.Proc.ExitCode}");
                s.Proc.Dispose();
                s.Proc = null;
                s.NextTry = now + TimeSpan.FromSeconds(Math.Min(30, 1 << Math.Min(5, s.Starts.Count)));
            }
            if (s.GaveUp || now < s.NextTry) continue;
            if (!s.Wanted())
            {
                Say(s, "sin modelos de voz; corre sapo-voice --descargar");
                s.NextTry = now + TimeSpan.FromSeconds(30);
                continue;
            }
            if (s.External())
            {
                Say(s, "ya corre fuera de Sapo, no lo lanzo");
                s.NextTry = now + TimeSpan.FromSeconds(5);
                continue;
            }
            s.Starts.RemoveAll(t => now - t > Window);
            if (s.Starts.Count >= MaxRestarts)
            {
                s.GaveUp = true;
                GD.Print($"core: {s.Name} murió {MaxRestarts} veces en {Window.TotalMinutes} min, me rindo");
                continue;
            }
            Start(s, now);
        }
    }

    static void Say(Service s, string note)
    {
        if (s.Note == note) return;
        s.Note = note;
        GD.Print($"core: {s.Name} {note}");
    }

    void Start(Service s, DateTime now)
    {
        s.Starts.Add(now);
        s.Note = "";
        try
        {
            var psi = new ProcessStartInfo(s.Exe, s.Args)
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                WorkingDirectory = Dir,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };
            psi.Environment["PYTHONUTF8"] = "1";
            psi.Environment["PYTHONIOENCODING"] = "utf-8";
            var log = OpenLog(s.Name);
            var p = new Process { StartInfo = psi, EnableRaisingEvents = true };
            DataReceivedEventHandler write = (_, e) =>
            {
                if (e.Data == null) return;
                lock (log) { try { log.WriteLine(e.Data); } catch (Exception) { } }
            };
            p.OutputDataReceived += write;
            p.ErrorDataReceived += write;
            p.Exited += (_, _) => { lock (log) { try { log.Dispose(); } catch (Exception) { } } };
            p.Start();
            if (_job != IntPtr.Zero) JobNative.AssignProcessToJobObject(_job, p.Handle);
            p.BeginOutputReadLine();
            p.BeginErrorReadLine();
            s.Proc = p;
            GD.Print($"core: lancé {s.Name} pid {p.Id} (intento {s.Starts.Count})");
        }
        catch (Exception e)
        {
            GD.Print($"core: no pude lanzar {s.Name}: {e.Message}");
            s.NextTry = now + TimeSpan.FromSeconds(10);
        }
    }

    StreamWriter OpenLog(string name)
    {
        Directory.CreateDirectory(_logDir);
        var path = Path.Combine(_logDir, name + ".log");
        try
        {
            if (File.Exists(path) && new FileInfo(path).Length > 2_000_000) File.Move(path, path + ".1", true);
        }
        catch (Exception) { }
        var fs = new FileStream(path, FileMode.Append, System.IO.FileAccess.Write, FileShare.ReadWrite);
        return new StreamWriter(fs) { AutoFlush = true };
    }

    public IEnumerable<(string name, int pid)> Running()
    {
        foreach (var s in _services)
            if (s.Proc is { HasExited: false }) yield return (s.Name, s.Proc.Id);
    }

    public void Stop()
    {
        foreach (var s in _services)
        {
            if (s.Proc == null) continue;
            try
            {
                if (!s.Proc.HasExited)
                {
                    s.Proc.Kill(true);
                    s.Proc.WaitForExit(3000);
                }
                GD.Print($"core: cerré {s.Name}");
            }
            catch (Exception) { }
            s.Proc.Dispose();
            s.Proc = null;
        }
        _services.Clear();
    }
}
