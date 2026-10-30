import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

brain = os.path.abspath(os.path.join(SPECPATH, "..", "brain"))

datas = [(os.path.join(brain, "sapo", "prompts"), os.path.join("sapo", "prompts"))]
binaries = []
hidden = collect_submodules("sapo") + collect_submodules("websockets") + ["pycaw.pycaw", "comtypes.stream", "_cffi_backend"]
for pkg in ("sherpa_onnx", "soundcard", "sounddevice", "_sounddevice_data"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hidden += h

excludes = ["tkinter", "pytest", "_pytest", "IPython", "matplotlib"]


def program(name, script):
    a = Analysis(
        [script],
        pathex=[brain],
        binaries=binaries,
        datas=datas,
        hiddenimports=hidden,
        excludes=excludes,
        noarchive=False,
    )
    pyz = PYZ(a.pure)
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=name,
        console=True,
        icon=os.path.join(SPECPATH, "..", "pc", "icon.ico"),
        upx=False,
    )
    return a, exe


brain_a, brain_exe = program("sapo-brain", os.path.join(SPECPATH, "entry_brain.py"))
voice_a, voice_exe = program("sapo-voice", os.path.join(SPECPATH, "entry_voice.py"))

coll = COLLECT(
    brain_exe,
    brain_a.binaries,
    brain_a.datas,
    voice_exe,
    voice_a.binaries,
    voice_a.datas,
    upx=False,
    name="core",
)
